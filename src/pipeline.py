import asyncio
import aiohttp
from typing import Dict, Any, List
from pathlib import Path
import json
from datetime import datetime
from src.agents.researcher import ResearcherAgent
from src.agents.extractor import ExtractorAgent
from src.agents.scriptwriter import ScriptwriterAgent
from src.agents.fact_checker import FactCheckerAgent
from src.agents.voiceover_agent import VoiceoverAgent
from src.crawlers.web_crawler import WebCrawler
from src.media.pipeline import MediaPipeline
from src.database import get_db
from src.models import Company, Source, Claim
from sqlalchemy.orm import Session

class ResearchPipeline:
    """Main pipeline orchestrating the research process"""
    
    def __init__(self):
        self.researcher = ResearcherAgent()
        self.extractor = ExtractorAgent()
        self.scriptwriter = ScriptwriterAgent()
        self.fact_checker = FactCheckerAgent()
        self.voiceover_agent = VoiceoverAgent()
        self.crawler = None  # Will be initialized with session
        self.media_pipeline = MediaPipeline()
        self.session = None  # Will be created in async context
    
    async def run(self, company_name: str, output_dir: str = "./output") -> Dict[str, Any]:
        """Run the complete research pipeline"""
        print(f"Starting research pipeline for {company_name}")
        
        # Create aiohttp session for this pipeline run
        async with aiohttp.ClientSession() as session:
            self.session = session
            self.crawler = WebCrawler(session)  # Pass session to WebCrawler
            
            # Create output directory
            company_slug = company_name.lower().replace(" ", "_").replace(".", "")
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            run_dir = Path(output_dir) / company_slug / timestamp
            run_dir.mkdir(parents=True, exist_ok=True)
            
            results = {
                "company_name": company_name,
                "company_slug": company_slug,
                "run_id": timestamp,
                "output_dir": str(run_dir),
                "pipeline_steps": {}
            }
            
            try:
                # Step 1: Discovery
                print("Step 1: Discovering sources...")
                discovery_results = await self.researcher.process({
                    "company_name": company_name,
                    "max_sources": 30
                })
                results["pipeline_steps"]["discovery"] = discovery_results
                
                # Step 2: Crawling
                print("Step 2: Crawling sources...")
                crawl_results = await self._crawl_sources(discovery_results["sources"])
                results["pipeline_steps"]["crawling"] = crawl_results
                
                # Step 3: Extraction
                print("Step 3: Extracting facts...")
                extraction_results = await self._extract_facts(crawl_results, company_name)
                results["pipeline_steps"]["extraction"] = extraction_results
                
                # Step 4: Save to database
                print("Step 4: Saving to database...")
                await self._save_to_database(company_name, company_slug, crawl_results, extraction_results)
                
                # Step 5: Fact-checking
                print("Step 5: Fact-checking claims...")
                fact_check_results = await self.fact_checker.process({"company_slug": company_slug})
                results["pipeline_steps"]["fact_checking"] = fact_check_results
                
                # Step 6: Script generation
                print("Step 6: Generating script...")
                script_results = await self.scriptwriter.process({
                    "company_slug": company_slug,
                    "style": "storytelling",
                    "target_words": 1600
                })
                results["pipeline_steps"]["script_generation"] = script_results

                # Step 6.5: Voiceover & Timeline Generation
                if not script_results.get("error"):
                    print("Step 6.5: Generating voiceover and timeline...")
                    voiceover_results = await self.voiceover_agent.process({
                        "script_content": script_results.get("script", ""),
                        "broll_suggestions": script_results.get("broll_suggestions", []),
                        "output_dir": run_dir
                    })
                    results["pipeline_steps"]["voiceover_generation"] = voiceover_results
                
                # Step 7: Media collection
                print("Step 7: Collecting media assets...")
                if not script_results.get("error"):
                    media_results = await self.media_pipeline.collect_media_for_script({
                        "company_name": company_name,
                        "broll_suggestions": script_results.get("broll_suggestions", [])
                    }, run_dir)
                    results["pipeline_steps"]["media_collection"] = media_results
                
                # Step 8: Generate final outputs
                print("Step 8: Generating final outputs...")
                await self._generate_outputs(results, run_dir)
                
                print(f"Pipeline completed successfully. Results in: {run_dir}")
                return results
                
            except Exception as e:
                print(f"Pipeline error: {e}")
                results["error"] = str(e)
                return results   
 
    async def _crawl_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Crawl discovered sources to get content"""
        crawled_sources = []
        
        # Limit concurrent crawling
        semaphore = asyncio.Semaphore(3)
        
        async def crawl_single(source):
            async with semaphore:
                try:
                    content = await self.crawler.crawl_url(source["url"])
                    if content:
                        source["content"] = content
                        source["crawled_at"] = datetime.utcnow().isoformat()
                        crawled_sources.append(source)
                        print(f"✅ Crawled: {source['title'][:50]}...")
                except Exception as e:
                    print(f"❌ Failed to crawl {source['url']}: {e}")
        
        # Crawl sources concurrently
        tasks = [crawl_single(source) for source in sources[:15]]  # Limit to 15 sources
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return crawled_sources
    
    async def _extract_facts(self, crawled_sources: List[Dict[str, Any]], company_name: str) -> List[Dict[str, Any]]:
        """Extracts facts from crawled content by batching sources to reduce API calls."""
        all_claims = []
        batch_size = 5  # Process 5 articles at a time

        # Create batches of sources
        source_batches = [crawled_sources[i:i + batch_size] for i in range(0, len(crawled_sources), batch_size)]

        for i, batch in enumerate(source_batches):
            print(f"Processing extraction batch {i+1}/{len(source_batches)}...")
            try:
                # Filter out sources with no content before sending to the agent
                valid_sources = [s for s in batch if s.get("content")]
                if not valid_sources:
                    continue

                extraction_result = await self.extractor.process({
                    "sources": valid_sources,
                    "company_name": company_name
                })
                
                claims = extraction_result.get("claims", [])
                print(f"✅ Extracted {len(claims)} claims from batch {i+1}")
                
                # Add source metadata back to the claims for database saving
                source_map = {s["url"]: s for s in valid_sources}
                for claim in claims:
                    source_url = claim.get("source_url")
                    if source_url and source_url in source_map:
                        claim["source_title"] = source_map[source_url].get("title", "")
                        claim["source_domain"] = source_map[source_url].get("domain", "")
                
                all_claims.extend(claims)

            except Exception as e:
                print(f"❌ Failed to process extraction batch {i+1}: {e}")
        
        return all_claims
    
    async def _save_to_database(self, company_name: str, company_slug: str, 
                               crawled_sources: List[Dict[str, Any]], 
                               claims: List[Dict[str, Any]]):
        """Save results to database"""
        db = next(get_db())
        
        try:
            # Create or get company
            company = db.query(Company).filter(Company.slug == company_slug).first()
            if not company:
                company = Company(name=company_name, slug=company_slug)
                db.add(company)
                db.commit()
                db.refresh(company)
            
            # Save sources
            for source_data in crawled_sources:
                source = Source(
                    company_id=company.id,
                    url=source_data.get("url"),
                    domain=source_data.get("domain"),
                    title=source_data.get("title"),
                    content=source_data.get("content"),
                    reliability=source_data.get("authority_score", 1)
                )
                db.add(source)
            
            # Save claims
            for claim_data in claims:
                claim = Claim(
                    company_id=company.id,
                    claim=claim_data.get("claim"),
                    claim_date=claim_data.get("parsed_date"),
                    subject=claim_data.get("subject"),
                    predicate=claim_data.get("predicate"),
                    object=claim_data.get("object"),
                    confidence=claim_data.get("confidence", 0.5)
                )
                db.add(claim)
            
            db.commit()
            print(f"✅ Saved {len(crawled_sources)} sources and {len(claims)} claims to database")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Database save error: {e}")
        finally:
            db.close()
    
    async def _generate_outputs(self, results: Dict[str, Any], output_dir: Path):
        """Generate output files"""
        # Save pipeline results
        with open(output_dir / "pipeline_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        # Generate research report
        claims = results["pipeline_steps"]["extraction"]
        report = self._generate_report(results["company_name"], claims)
        with open(output_dir / "research_report.md", "w") as f:
            f.write(report)
        
        # Save script if generated
        script_data = results["pipeline_steps"].get("script_generation", {})
        if script_data.get("script"):
            with open(output_dir / "script.md", "w") as f:
                f.write(script_data["script"])
            
            # Save B-roll suggestions as CSV
            broll_suggestions = script_data.get("broll_suggestions", [])
            if broll_suggestions:
                import csv
                with open(output_dir / "shot_list.csv", "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["timestamp", "duration", "description", "visual_type", "keywords", "mood"])
                    writer.writeheader()
                    for suggestion in broll_suggestions:
                        writer.writerow({
                            "timestamp": suggestion.get("timestamp", ""),
                            "duration": suggestion.get("duration", ""),
                            "description": suggestion.get("description", ""),
                            "visual_type": suggestion.get("visual_type", ""),
                            "keywords": ", ".join(suggestion.get("keywords", [])),
                            "mood": suggestion.get("mood", "")
                        })
        
        # Save fact-check report
        fact_check_data = results["pipeline_steps"].get("fact_checking", {})
        if fact_check_data.get("report"):
            with open(output_dir / "fact_check_report.md", "w") as f:
                f.write(fact_check_data["report"])
        
        # Generate thumbnail concepts
        if script_data.get("script"):
            thumbnail_concepts = await self._generate_thumbnail_concepts(results["company_name"], script_data)
            with open(output_dir / "thumbnail_concepts.txt", "w") as f:
                f.write(thumbnail_concepts)
        
        print(f"✅ Generated outputs in {output_dir}")
    
    def _generate_report(self, company_name: str, claims: List[Dict[str, Any]]) -> str:
        """Generate a basic research report"""
        report = f"# Research Report: {company_name}\n\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += f"## Summary\n\n"
        report += f"- Total claims extracted: {len(claims)}\n"
        report += f"- High confidence claims (>0.7): {len([c for c in claims if c.get('confidence', 0) > 0.7])}\n\n"
        
        report += "## Key Facts\n\n"
        
        # Group claims by confidence
        high_conf_claims = [c for c in claims if c.get('confidence', 0) > 0.7]
        for claim in high_conf_claims[:20]:  # Top 20 high-confidence claims
            report += f"- {claim.get('claim', '')}\n"
            if claim.get('date'):
                report += f"  - Date: {claim.get('date')}\n"
            report += f"  - Confidence: {claim.get('confidence', 0):.2f}\n"
            report += f"  - Source: {claim.get('source_title', 'Unknown')}\n\n"
        
        return report    

    async def _generate_thumbnail_concepts(self, company_name: str, script_data: Dict[str, Any]) -> str:
        """Generate thumbnail and title concepts"""
        script_content = script_data.get("script", "")
        
        # Use the scriptwriter's LLM capability
        prompt = f"""Based on this script about {company_name}, generate 5 YouTube video titles and 3 thumbnail concepts. 
        
        Script excerpt: {script_content[:1000]}...
        
        Requirements:
        - Titles should be 60 characters or less
        - Titles should be clickable and engaging
        - Thumbnail concepts should include 2-3 word overlays
        - Consider what would perform well on YouTube
        
        Format:
        ## Video Titles
        1. [Title 1]
        2. [Title 2]
        ...
        
        ## Thumbnail Concepts
        1. **Concept 1**: [Description]
           - Text overlay: "[Text]"
           - Visual elements: [Description]
        
        2. **Concept 2**: [Description]
           - Text overlay: "[Text]"
           - Visual elements: [Description]
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.scriptwriter.call_llm(messages, temperature=0.6)
        
        return response or "# Thumbnail Concepts\n\nGeneration failed - create manually based on script content."
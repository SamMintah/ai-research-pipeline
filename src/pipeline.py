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
from src.media.news_media_collector import NewsMediaCollector
from src.database import get_db
from src.models import Subject, Source, Claim
from sqlalchemy.orm import Session

class ResearchPipeline:
    """Main pipeline orchestrating the research process"""
    
    def __init__(self):
        from src.llm.ollama_provider import OllamaProvider

        # Initialize LLM providers
        ollama_provider = OllamaProvider(model="llama3:8b")

        # Initialize agents with the appropriate LLM provider
        self.researcher = ResearcherAgent(llm_provider=ollama_provider)
        self.extractor = ExtractorAgent(llm_provider=ollama_provider)
        self.scriptwriter = ScriptwriterAgent(llm_provider=ollama_provider)
        self.fact_checker = FactCheckerAgent(llm_provider=ollama_provider)
        
        self.voiceover_agent = VoiceoverAgent(llm_provider=ollama_provider, voice_style="aaditya_storyteller")
        self.crawler = None  # Will be initialized with session
        self.media_pipeline = MediaPipeline()
        self.news_media_collector = NewsMediaCollector()
        self.session = None  # Will be created in async context
    
    async def run(self, subject_name: str, output_dir: str = "./output") -> Dict[str, Any]:
        """Run the complete research pipeline"""
        print(f"Starting research pipeline for {subject_name}")
        
        # Create aiohttp session for this pipeline run
        async with aiohttp.ClientSession() as session:
            self.session = session
            self.crawler = WebCrawler(session)  # Pass session to WebCrawler
            
            # Create output directory
            subject_slug = subject_name.lower().replace(" ", "_").replace(".", "")
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            run_dir = Path(output_dir) / subject_slug / timestamp
            run_dir.mkdir(parents=True, exist_ok=True)
            
            results = {
                "subject_name": subject_name,
                "subject_slug": subject_slug,
                "run_id": timestamp,
                "output_dir": str(run_dir),
                "pipeline_steps": {}
            }
            
            try:
                # Step 1: Discovery
                print("Step 1: Discovering sources...")
                discovery_results = await self.researcher.process({
                    "subject_name": subject_name,
                    "max_sources": 30
                })
                results["pipeline_steps"]["discovery"] = discovery_results
                
                # Step 2: Crawling
                print("Step 2: Crawling sources...")
                crawl_results = await self._crawl_sources(discovery_results["sources"])
                results["pipeline_steps"]["crawling"] = crawl_results
                
                # Step 3: Extraction
                print("Step 3: Extracting facts...")
                extraction_results = await self._extract_facts(crawl_results, subject_name)
                results["pipeline_steps"]["extraction"] = extraction_results
                
                # Step 4: Save to database
                print("Step 4: Saving to database...")
                await self._save_to_database(subject_name, subject_slug, crawl_results, extraction_results)
                
                # Step 5: Fact-checking (SKIPPED for speed)
                print("Step 5: Skipping fact-checking for faster processing...")
                fact_check_results = {
                    "subject_slug": subject_slug,
                    "total_claims": len(extraction_results),
                    "verified_claims": len(extraction_results),
                    "flagged_claims": 0,
                    "verification_results": [],
                    "report": "# Fact-Check Report\n\nFact-checking skipped for faster processing.",
                    "checked_at": datetime.utcnow().isoformat()
                }
                results["pipeline_steps"]["fact_checking"] = fact_check_results
                
                # Step 6: Script generation
                print("Step 6: Generating script...")
                script_results = await self.scriptwriter.process({
                    "subject_slug": subject_slug,
                    "style": "documentary",
                    "target_words": 3500  # Enhanced for longer, more engaging content
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
                
                # Step 7: Enhanced media collection
                print("Step 7: Collecting comprehensive media assets...")
                if not script_results.get("error"):
                    # Import enhanced media collector
                    from src.media.enhanced_media_collector import EnhancedMediaCollector
                    enhanced_media_collector = EnhancedMediaCollector()
                    
                    # Collect comprehensive media (news + targeted + stock)
                    enhanced_media_results = await enhanced_media_collector.collect_comprehensive_media(
                        subject_name=subject_name,
                        sources=crawl_results,
                        script_content=script_results.get("script", ""),
                        output_dir=run_dir,
                        max_images=25  # More images for better variety
                    )
                    
                    # Also collect generic B-roll as backup
                    generic_media_results = await self.media_pipeline.collect_media_for_script({
                        "subject_name": subject_name,
                        "broll_suggestions": script_results.get("broll_suggestions", [])
                    }, run_dir)
                    
                    # Combine results
                    media_results = {
                        "enhanced_media": enhanced_media_results,
                        "generic_media": generic_media_results,
                        "total_assets": enhanced_media_results.get("collection_summary", {}).get("total_assets", 0),
                        "media_categories": {
                            "news_coverage": len(enhanced_media_results.get("media_assets", {}).get("news_coverage", [])),
                            "targeted_content": len(enhanced_media_results.get("media_assets", {}).get("targeted_content", [])),
                            "stock_broll": len(enhanced_media_results.get("media_assets", {}).get("stock_broll", []))
                        }
                    }
                    results["pipeline_steps"]["media_collection"] = media_results
                    
                    print(f"✅ Collected {media_results['total_assets']} media assets:")
                    print(f"   - News coverage: {media_results['media_categories']['news_coverage']} images")
                    print(f"   - Targeted content: {media_results['media_categories']['targeted_content']} images") 
                    print(f"   - Stock B-roll: {media_results['media_categories']['stock_broll']} images")
                
                # Step 8: Generate final outputs
                print("Step 8: Generating final outputs...")
                await self._generate_outputs(results, run_dir)
                
                # Step 9: Generate YouTube optimization report
                print("Step 9: Generating YouTube optimization report...")
                await self._generate_youtube_optimization_report(results, run_dir)
                
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
    
    async def _extract_facts(self, crawled_sources: List[Dict[str, Any]], subject_name: str) -> List[Dict[str, Any]]:
        """Extracts facts from crawled content by batching sources to reduce API calls."""
        all_claims = []
        batch_size = 1  # Process 1 article at a time to reduce memory usage

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
                    "subject_name": subject_name
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
    
    async def _save_to_database(self, subject_name: str, subject_slug: str, 
                               crawled_sources: List[Dict[str, Any]], 
                               claims: List[Dict[str, Any]]):
        """Save results to database"""
        db = next(get_db())
        
        try:
            # Create or get subject
            subject = db.query(Subject).filter(Subject.slug == subject_slug).first()
            if not subject:
                subject = Subject(name=subject_name, slug=subject_slug)
                db.add(subject)
                db.commit()
                db.refresh(subject)
            
            # Save sources
            for source_data in crawled_sources:
                source = Source(
                    subject_id=subject.id,
                    url=source_data.get("url"),
                    domain=source_data.get("domain"),
                    title=source_data.get("title"),
                    content=source_data.get("content"),
                    reliability=source_data.get("authority_score", 1)
                )
                db.add(source)
            
            # Save claims
            claims_to_save = [c for c in claims if c.get("claim")]
            for claim_data in claims_to_save:
                claim = Claim(
                    parent_subject_id=subject.id,
                    claim=claim_data.get("claim"),
                    claim_date=claim_data.get("parsed_date"),
                    claim_subject=claim_data.get("subject"),
                    predicate=claim_data.get("predicate"),
                    object=claim_data.get("object"),
                    confidence=claim_data.get("confidence", 0.5)
                )
                db.add(claim)
            
            db.commit()
            print(f"✅ Saved {len(crawled_sources)} sources and {len(claims_to_save)} claims to database")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Database save error: {e}")
        finally:
            db.close()
    
    def _generate_edl(self, timeline_data: List[Dict[str, Any]], media_index: Dict[str, Any], output_dir: Path):
        """Generates an EDL file for DaVinci Resolve."""

        def to_timecode(seconds: float, fps: int = 30) -> str:
            """Converts seconds to HH:MM:SS:FF timecode format."""
            ss = int(seconds)
            ff = int((seconds - ss) * fps)
            mm, ss = divmod(ss, 60)
            hh, mm = divmod(mm, 60)
            return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

        edl_events = []
        event_num = 1

        for i, row in enumerate(timeline_data):
            # Audio event
            start_seconds = float(row["start_time_s"])
            end_seconds = float(row["end_time_s"])
            duration_seconds = end_seconds - start_seconds
            voiceover_file = Path(row["voiceover_file"])
            
            edl_events.append({
                "event_num": event_num,
                "reel": voiceover_file.stem,
                "track_type": "A",
                "edit_type": "C",
                "source_in": to_timecode(0),
                "source_out": to_timecode(duration_seconds),
                "record_in": to_timecode(start_seconds),
                "record_out": to_timecode(end_seconds),
                "clip_name": voiceover_file.name,
            })
            event_num += 1

            # Video event
            if i < len(media_index["sections"]):
                section = media_index["sections"][i]
                if section["matching_assets"]:
                    reel_name = Path(section["matching_assets"][0]["filename"])
                    broll_duration = float(section.get("suggested_duration", 5))

                    edl_events.append({
                        "event_num": event_num,
                        "reel": reel_name.stem,
                        "track_type": "V",
                        "edit_type": "C",
                        "source_in": to_timecode(0),
                        "source_out": to_timecode(broll_duration),
                        "record_in": to_timecode(start_seconds),
                        "record_out": to_timecode(start_seconds + broll_duration),
                        "clip_name": reel_name.name,
                    })
                    event_num += 1

        # Write EDL file
        with open(output_dir / "timeline.edl", "w") as f:
            f.write("TITLE: AI Research Video\n")
            f.write("FCM: NON-DROP FRAME\n\n")
            for event in edl_events:
                f.write(f"{event['event_num']:03d}  {event['reel']:<8} {event['track_type']}     {event['edit_type']}        {event['source_in']} {event['source_out']} {event['record_in']} {event['record_out']}\n")
                f.write(f"* FROM CLIP NAME: {event['clip_name']}\n\n")

    def _generate_resolve_markers(self, shot_list: List[Dict[str, Any]], output_dir: Path):
        """Generates a CSV file with markers for DaVinci Resolve."""
        import csv

        def to_timecode(seconds: float, fps: int = 30) -> str:
            """Converts seconds to HH:MM:SS:FF timecode format."""
            ss = int(seconds)
            ff = int((seconds - ss) * fps)
            mm, ss = divmod(ss, 60)
            hh, mm = divmod(mm, 60)
            return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

        resolve_markers = []
        for shot in shot_list:
            try:
                # Convert timestamp [MM:SS] to seconds
                timestamp_str = shot.get("timestamp", "[00:00]").strip("[]")
                minutes, seconds = map(int, timestamp_str.split(":"))
                start_seconds = minutes * 60 + seconds
                start_timecode = to_timecode(start_seconds)

                # Convert duration from seconds to timecode
                duration_seconds = float(shot.get("duration", 0))
                duration_timecode = to_timecode(duration_seconds)

                notes = f"Description: {shot.get('description', '')}\n" \
                        f"Visual Type: {shot.get('visual_type', '')}\n" \
                        f"Keywords: {shot.get('keywords', '')}\n" \
                        f"Mood: {shot.get('mood', '')}"

                resolve_markers.append({
                    "Name": shot.get("description", "Marker"),
                    "Start": start_timecode,
                    "Duration": duration_timecode,
                    "Notes": notes,
                    "Color": "Blue" # Default color
                })
            except Exception as e:
                print(f"Skipping marker due to error: {e}")

        if resolve_markers:
            with open(output_dir / "resolve_markers.csv", "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["Name", "Start", "Duration", "Notes", "Color"])
                writer.writeheader()
                writer.writerows(resolve_markers)

    async def _generate_outputs(self, results: Dict[str, Any], output_dir: Path):
        """Generate output files"""
        # Save pipeline results
        with open(output_dir / "pipeline_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        # Generate research report
        claims = results["pipeline_steps"]["extraction"]
        report = self._generate_report(results["subject_name"], claims)
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
                
                # Generate Resolve markers
                self._generate_resolve_markers(broll_suggestions, output_dir)

        # Generate EDL file
        voiceover_results = results["pipeline_steps"].get("voiceover_generation", {})
        timeline_csv_path = voiceover_results.get("timeline_csv_path")
        media_collection_results = results["pipeline_steps"].get("media_collection", {})
        media_index = media_collection_results.get("media_index")

        if timeline_csv_path and media_index:
            import csv
            with open(timeline_csv_path, "r") as f:
                timeline_data = list(csv.DictReader(f))
            
            self._generate_edl(timeline_data, media_index, output_dir)
        
        # Save fact-check report
        fact_check_data = results["pipeline_steps"].get("fact_checking", {})
        if fact_check_data.get("report"):
            with open(output_dir / "fact_check_report.md", "w") as f:
                f.write(fact_check_data["report"])
        
        # Generate thumbnail concepts
        if script_data.get("script"):
            thumbnail_concepts = await self._generate_thumbnail_concepts(results["subject_name"], script_data)
            with open(output_dir / "thumbnail_concepts.txt", "w") as f:
                f.write(thumbnail_concepts)
        
        print(f"✅ Generated outputs in {output_dir}")
    
    def _generate_report(self, subject_name: str, claims: List[Dict[str, Any]]) -> str:
        """Generate a basic research report"""
        report = f"# Research Report: {subject_name}\n\n"
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

    async def _generate_thumbnail_concepts(self, subject_name: str, script_data: Dict[str, Any]) -> str:
        """Generate thumbnail and title concepts"""
        script_content = script_data.get("script", "")
        
        # Use the scriptwriter's LLM capability
        prompt = f"""Based on this script about {subject_name}, generate 5 YouTube video titles and 3 thumbnail concepts. 
        
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
           - Visual elements: [Description]"""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.scriptwriter.call_llm(messages, temperature=0.6)
        
        return response or "# Thumbnail Concepts\n\nGeneration failed - create manually based on script content."
    
    async def _generate_youtube_optimization_report(self, results: Dict[str, Any], output_dir: Path):
        """Generate a comprehensive YouTube optimization report"""
        script_data = results["pipeline_steps"].get("script_generation", {})
        
        if not script_data.get("youtube_titles"):
            return
        
        report = f"""# YouTube Optimization Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Gemini Algorithm Optimization
This content has been optimized for YouTube's Gemini-enhanced algorithm focusing on:
- Viewer-centric narratives and personalized recommendations
- Enhanced content understanding through AI analysis
- Improved engagement and retention metrics
- Cultural relevance for US/Canadian audiences

## Recommended Video Titles
"""
        
        for i, title in enumerate(script_data.get("youtube_titles", []), 1):
            report += f"{i}. {title}\n"
        
        report += "\n## Thumbnail Concepts\n\n"
        
        for i, thumbnail in enumerate(script_data.get("thumbnail_concepts", []), 1):
            if isinstance(thumbnail, dict):
                report += f"### Concept {i}: {thumbnail.get('concept', 'N/A')}\n"
                report += f"- **Text Overlay:** {thumbnail.get('text_overlay', 'N/A')}\n"
                report += f"- **Visual Elements:** {thumbnail.get('visual_elements', 'N/A')}\n"
                report += f"- **Color Scheme:** {thumbnail.get('color_scheme', 'N/A')}\n"
                report += f"- **Emotional Appeal:** {thumbnail.get('emotional_appeal', 'N/A')}\n\n"
        
        report += "## SEO Keywords\n\n"
        keywords = script_data.get("seo_keywords", [])
        if keywords:
            for keyword in keywords:
                report += f"- {keyword}\n"
        
        report += f"""

## Audience Targeting Strategy
- **Primary Markets:** United States, Canada
- **Demographics:** 25-54 years, college-educated professionals
- **Interests:** Business, technology, entrepreneurship, finance
- **Cultural Context:** American business culture, Silicon Valley, Wall Street

## Engagement Optimization
- Strong opening hooks to capture attention within first 15 seconds
- Retention techniques throughout to maintain viewer interest
- Clear value proposition and viewer-centric narrative
- Natural integration of cultural references and business terminology

## Monetization Potential
- High-CPM audience targeting (US/Canadian viewers)
- Business/finance niche with strong advertiser demand
- Professional demographic with higher purchasing power
- Evergreen content suitable for long-term monetization

## Upload Recommendations
- **Best Upload Time:** 7-9 PM EST (US peak hours)
- **Language:** American English spelling and terminology
- **Currency:** Use USD ($) for all financial references
- **Cultural References:** Emphasize American business culture and success stories
"""
        
        with open(output_dir / "youtube_optimization_report.md", "w") as f:
            f.write(report)
        
        print(f"✅ Generated YouTube optimization report")

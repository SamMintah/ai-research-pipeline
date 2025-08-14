from typing import Dict, Any, List
import json
from datetime import datetime
from src.agents.base import BaseAgent
from src.models import Company, Claim, Source
from src.database import get_db
from sqlalchemy.orm import Session

class ScriptwriterAgent(BaseAgent):
    """Agent for generating YouTube-ready scripts from research data"""
    
    def __init__(self):
        super().__init__()
        self.script_templates = {
            "documentary": {
                "tone": "authoritative and informative",
                "style": "documentary narrator style with clear, measured delivery",
                "pacing": "deliberate with dramatic pauses"
            },
            "energetic": {
                "tone": "enthusiastic and engaging", 
                "style": "energetic YouTuber style with personality and excitement",
                "pacing": "fast-paced with dynamic delivery"
            },
            "storytelling": {
                "tone": "narrative and compelling",
                "style": "storytelling approach with character development",
                "pacing": "varied pacing building to climactic moments"
            }
        }
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate script from company research data"""
        company_slug = input_data.get("company_slug")
        style = input_data.get("style", "storytelling")
        target_words = input_data.get("target_words", 1600)
        
        if not company_slug:
            return {"error": "Company slug required"}
        
        # Get research data from database
        research_data = await self._get_research_data(company_slug)
        if not research_data:
            return {"error": "No research data found for company"}
        
        # Generate script outline
        outline = await self._generate_outline(research_data, style, target_words)
        
        # Generate full script
        script = await self._generate_script(research_data, outline, style)
        
        # Generate B-roll suggestions
        broll_suggestions = await self._generate_broll_suggestions(script, research_data)
        
        return {
            "script": script,
            "outline": outline,
            "broll_suggestions": broll_suggestions,
            "style": style,
            "word_count": len(script.split()),
            "estimated_duration": self._estimate_duration(script),
            "generated_at": datetime.utcnow().isoformat()
        }    
    as
ync def _get_research_data(self, company_slug: str) -> Dict[str, Any]:
        """Retrieve research data from database"""
        db = next(get_db())
        
        try:
            company = db.query(Company).filter(Company.slug == company_slug).first()
            if not company:
                return None
            
            # Get claims sorted by confidence and date
            claims = db.query(Claim).filter(
                Claim.company_id == company.id,
                Claim.confidence > 0.3  # Only include reasonably confident claims
            ).order_by(Claim.claim_date.asc(), Claim.confidence.desc()).all()
            
            # Get sources for context
            sources = db.query(Source).filter(Source.company_id == company.id).all()
            
            # Organize claims by timeline
            timeline_events = []
            founding_info = []
            business_events = []
            challenges = []
            achievements = []
            
            for claim in claims:
                claim_data = {
                    "claim": claim.claim,
                    "date": claim.claim_date.isoformat() if claim.claim_date else None,
                    "confidence": claim.confidence,
                    "subject": claim.subject,
                    "predicate": claim.predicate,
                    "object": claim.object
                }
                
                # Categorize claims
                claim_lower = claim.claim.lower()
                if any(word in claim_lower for word in ["founded", "started", "began", "launched"]):
                    founding_info.append(claim_data)
                elif any(word in claim_lower for word in ["funding", "investment", "raised", "ipo", "acquisition"]):
                    business_events.append(claim_data)
                elif any(word in claim_lower for word in ["crisis", "lawsuit", "failed", "problem", "challenge"]):
                    challenges.append(claim_data)
                elif any(word in claim_lower for word in ["success", "breakthrough", "milestone", "achievement"]):
                    achievements.append(claim_data)
                
                if claim.claim_date:
                    timeline_events.append(claim_data)
            
            return {
                "company": {
                    "name": company.name,
                    "slug": company.slug
                },
                "timeline_events": sorted(timeline_events, key=lambda x: x["date"] or "9999"),
                "founding_info": founding_info,
                "business_events": business_events,
                "challenges": challenges,
                "achievements": achievements,
                "total_claims": len(claims),
                "sources_count": len(sources)
            }
            
        finally:
            db.close()
    
    async def _generate_outline(self, research_data: Dict[str, Any], style: str, target_words: int) -> Dict[str, Any]:
        """Generate script outline based on research data"""
        company_name = research_data["company"]["name"]
        template = self.script_templates.get(style, self.script_templates["storytelling"])
        
        prompt = f"""Create a detailed outline for a {target_words}-word YouTube script about {company_name}.
        
        Style: {template['tone']} with {template['style']}
        
        Research Summary:
        - Total verified facts: {research_data['total_claims']}
        - Founding events: {len(research_data['founding_info'])}
        - Business milestones: {len(research_data['business_events'])}
        - Challenges faced: {len(research_data['challenges'])}
        - Major achievements: {len(research_data['achievements'])}
        
        Key Timeline Events:
        {json.dumps(research_data['timeline_events'][:10], indent=2)}
        
        Create a 9-section outline following this structure:
        1. Hook (120-180 words) - Start with most dramatic/surprising moment
        2. Founding (180-220 words) - Origin story and founders
        3. Early Challenges (180-220 words) - Initial struggles and obstacles
        4. Breakthrough (180-220 words) - Key pivot or breakthrough moment
        5. Scaling (180-220 words) - Growth phase and expansion
        6. Setbacks (150-200 words) - Major challenges or crises
        7. Current State (120-180 words) - Where they are now
        8. Competition (120-160 words) - Market position and rivals
        9. Lessons (220-280 words) - Key takeaways for viewers
        
        For each section, provide:
        - Target word count
        - Key points to cover
        - Suggested narrative angle
        - Transition to next section
        
        Return as JSON with sections array."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.3)
        
        try:
            return json.loads(response)
        except:
            # Fallback outline
            return {
                "sections": [
                    {"name": "Hook", "word_count": 150, "key_points": ["Most dramatic moment"]},
                    {"name": "Founding", "word_count": 200, "key_points": ["Origin story"]},
                    {"name": "Early Challenges", "word_count": 200, "key_points": ["Initial struggles"]},
                    {"name": "Breakthrough", "word_count": 200, "key_points": ["Key breakthrough"]},
                    {"name": "Scaling", "word_count": 200, "key_points": ["Growth phase"]},
                    {"name": "Setbacks", "word_count": 175, "key_points": ["Major challenges"]},
                    {"name": "Current State", "word_count": 150, "key_points": ["Present situation"]},
                    {"name": "Competition", "word_count": 140, "key_points": ["Market position"]},
                    {"name": "Lessons", "word_count": 250, "key_points": ["Key takeaways"]}
                ]
            }   
 
    async def _generate_script(self, research_data: Dict[str, Any], outline: Dict[str, Any], style: str) -> str:
        """Generate the full script based on outline and research"""
        company_name = research_data["company"]["name"]
        template = self.script_templates.get(style, self.script_templates["storytelling"])
        
        script_sections = []
        
        for i, section in enumerate(outline.get("sections", [])):
            section_name = section.get("name", f"Section {i+1}")
            word_count = section.get("word_count", 200)
            
            # Get relevant facts for this section
            relevant_facts = self._get_relevant_facts_for_section(section_name, research_data)
            
            prompt = f"""Write the {section_name} section of a YouTube script about {company_name}.
            
            Style: {template['tone']} with {template['style']}
            Target length: {word_count} words
            Section purpose: {section.get('key_points', [])}
            
            Relevant verified facts to include:
            {json.dumps(relevant_facts[:5], indent=2)}
            
            Requirements:
            - Write in {template['style']}
            - Include timestamp marker [MM:SS] at start
            - Add [B-ROLL: description] suggestions in brackets
            - End paragraphs with [ref:n] citation markers
            - Make it engaging and YouTube-friendly
            - Use clear, voiceover-ready language
            - Include smooth transition to next section
            
            Write the complete section now:"""
            
            messages = [{"role": "user", "content": prompt}]
            section_content = await self.call_llm(messages, temperature=0.4)
            
            script_sections.append(f"## {section_name}\n\n{section_content}\n")
        
        # Combine all sections
        full_script = f"# {company_name}: The Complete Story\n\n"
        full_script += f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        full_script += f"*Style: {style.title()}*\n"
        full_script += f"*Estimated Duration: {self._estimate_duration(' '.join(script_sections))} minutes*\n\n"
        full_script += "---\n\n"
        full_script += "\n".join(script_sections)
        
        # Add references section
        full_script += "\n## References\n\n"
        full_script += "*[ref:1-n] Citations will be populated from source database*\n"
        
        return full_script
    
    def _get_relevant_facts_for_section(self, section_name: str, research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get facts most relevant to a specific script section"""
        section_keywords = {
            "Hook": ["crisis", "dramatic", "surprising", "breakthrough", "failure", "success"],
            "Founding": ["founded", "started", "began", "launched", "founder", "origin"],
            "Early Challenges": ["challenge", "problem", "struggle", "difficulty", "obstacle"],
            "Breakthrough": ["breakthrough", "pivot", "success", "milestone", "achievement"],
            "Scaling": ["growth", "expansion", "scaling", "hiring", "funding", "revenue"],
            "Setbacks": ["crisis", "lawsuit", "failure", "problem", "setback", "challenge"],
            "Current State": ["now", "today", "current", "present", "recent", "latest"],
            "Competition": ["competitor", "rival", "market", "competition", "versus"],
            "Lessons": ["lesson", "insight", "takeaway", "learning", "advice"]
        }
        
        keywords = section_keywords.get(section_name, [])
        relevant_facts = []
        
        # Check all fact categories
        all_facts = (
            research_data.get("founding_info", []) +
            research_data.get("business_events", []) +
            research_data.get("challenges", []) +
            research_data.get("achievements", [])
        )
        
        for fact in all_facts:
            claim_lower = fact.get("claim", "").lower()
            if any(keyword in claim_lower for keyword in keywords):
                relevant_facts.append(fact)
        
        # Sort by confidence
        return sorted(relevant_facts, key=lambda x: x.get("confidence", 0), reverse=True)
    
    async def _generate_broll_suggestions(self, script: str, research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate B-roll suggestions for the script"""
        company_name = research_data["company"]["name"]
        
        prompt = f"""Analyze this script for {company_name} and suggest specific B-roll footage for video editing.
        
        For each major section/paragraph, suggest:
        - Visual type (stock footage, graphics, photos, etc.)
        - Specific search keywords for stock footage
        - Suggested duration in seconds
        - Visual style/mood
        
        Script excerpt:
        {script[:2000]}...
        
        Return as JSON array with format:
        [
          {{
            "timestamp": "00:30",
            "duration": 15,
            "visual_type": "stock_footage",
            "description": "Corporate office building exterior",
            "keywords": ["office building", "corporate headquarters", "business"],
            "mood": "professional"
          }}
        ]
        
        Focus on the first 5 minutes of content."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.3)
        
        try:
            return json.loads(response)
        except:
            return []
    
    def _estimate_duration(self, script: str) -> float:
        """Estimate video duration based on word count (assuming 150 words per minute)"""
        word_count = len(script.split())
        return round(word_count / 150, 1)
    
    def _extract_timestamps(self, script: str) -> List[str]:
        """Extract timestamp markers from script"""
        import re
        timestamps = re.findall(r'\[(\d{1,2}:\d{2})\]', script)
        return timestamps
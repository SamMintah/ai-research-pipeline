from typing import Dict, Any, List, Union, Optional
import json
import re
from datetime import datetime
from src.agents.base import BaseAgent
from src.models import Subject, Claim, Source
from src.database import get_db
from sqlalchemy.orm import Session
import asyncio
import time
from src.llm.base_provider import LLMProvider
from src.documentary_config import DOCUMENTARY_CONFIG, NARRATIVE_STRUCTURES, EMOTIONAL_BEATS

class ScriptwriterAgent(BaseAgent):
    """Agent for generating YouTube-ready scripts optimized for Gemini algorithm and US/Canadian audiences"""
    
    def __init__(self, llm_provider: LLMProvider):
        super().__init__(llm_provider)
        self.script_templates = {
            "documentary": {
                "tone": "authoritative yet accessible, like a premium Netflix documentary with American business insight",
                "style": "professional documentary narrator with dramatic storytelling, character development, and cultural relevance",
                "pacing": "deliberate build-up with strategic pauses, tension creation, and satisfying reveals"
            },
            "investigative": {
                "tone": "investigative journalist uncovering hidden truths with business acumen",
                "style": "investigative documentary style with mystery elements and shocking revelations",
                "pacing": "building suspense with cliffhangers and dramatic reveals throughout"
            },
            "biographical": {
                "tone": "intimate and personal while maintaining professional credibility",
                "style": "character-driven biographical documentary focusing on human elements and personal growth",
                "pacing": "emotional journey with ups and downs, building to inspiring conclusion"
            },
            "business_analysis": {
                "tone": "analytical and insightful with Wall Street sophistication",
                "style": "business documentary style focusing on strategy, decisions, and market impact",
                "pacing": "methodical analysis building to strategic insights and future implications"
            }
        }
        
        # Enhanced documentary engagement techniques
        self.gemini_optimization = {
            "opening_hooks": [
                "In 1993, three Stanford graduates made a bet that would either make them billionaires or destroy their careers...",
                "This company's CEO just became the world's most powerful person you've never heard of...",
                "Behind closed doors, a $2 trillion empire was built on a technology most people still don't understand...",
                "The email that leaked in 2018 revealed the shocking truth about how this company really operates...",
                "They said it was impossible. The experts laughed. Wall Street called it a joke. They were all wrong...",
                "In a basement in Santa Clara, two engineers discovered something that would change everything...",
                "The phone call that saved this company from bankruptcy lasted exactly 47 minutes...",
                "This is the untold story of how a graphics card company accidentally created the future...",
                "When the FBI raided their headquarters, nobody expected what they would find...",
                "The decision made in this 15-minute meeting created a $3 trillion industry...",
                "They built their first prototype with stolen parts and a $500 budget...",
                "The resignation letter that shocked Silicon Valley was just two sentences long..."
            ],
            "section_transitions": [
                "But here's where the story takes a dark turn...",
                "What happened next shocked even the insiders...",
                "This is where everything started to unravel...",
                "But the truth was far more complicated...",
                "Little did they know, this decision would destroy everything...",
                "The real battle was just beginning..."
            ],
            "retention_hooks": [
                "Stay with me, because what comes next will blow your mind...",
                "But before I tell you what really happened, you need to understand...",
                "The documents I'm about to show you have never been seen before...",
                "This next revelation changes everything we thought we knew...",
                "What I discovered in my research will shock you...",
                "The truth they've been hiding is finally coming to light..."
            ],
            "emotional_beats": [
                "betrayal and shocking revelations",
                "triumph against impossible odds", 
                "devastating failure and comeback",
                "David vs Goliath confrontations",
                "moral dilemmas and tough choices",
                "unexpected alliances and partnerships"
            ],
            "cultural_references": [
                "American Dream", "Silicon Valley disruption", "Wall Street power plays",
                "Fortune 500 boardroom battles", "startup unicorn status", "venture capital wars",
                "IPO gold rush", "corporate America scandals", "entrepreneurial spirit",
                "innovation revolution", "market disruption", "business empire building"
            ],
            "documentary_techniques": [
                "exclusive interviews and insider accounts",
                "never-before-seen documents and emails",
                "behind-the-scenes footage and recordings",
                "expert analysis and industry insights",
                "timeline reconstruction with evidence",
                "investigative journalism revelations"
            ]
        }
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate script from subject research data"""
        subject_slug = input_data.get("subject_slug")
        style = input_data.get("style", "documentary")
        target_words = input_data.get("target_words", DOCUMENTARY_CONFIG["target_word_count"])  # Use config default
        
        if not subject_slug:
            return {"error": "Subject slug required"}
        
        # Get research data from database
        research_data = await self._get_subject_data(subject_slug)
        if not research_data:
            return {"error": "No research data found for subject"}
        
        # Generate detailed documentary-style outline first
        detailed_outline = await self._generate_detailed_outline(research_data, style, target_words)
        
        # Generate full script with enhanced storytelling
        enhanced_script = await self._generate_enhanced_script(research_data, detailed_outline, style, target_words)
        
        # Generate B-roll suggestions
        broll_suggestions = await self._generate_broll_suggestions(enhanced_script, research_data)
        
        # Generate YouTube-optimized titles and thumbnails
        youtube_optimization = await self._generate_youtube_optimization(enhanced_script, research_data)
        
        return {
            "script": enhanced_script,
            "outline": detailed_outline,
            "broll_suggestions": broll_suggestions,
            "youtube_titles": youtube_optimization.get("titles", []),
            "thumbnail_concepts": youtube_optimization.get("thumbnails", []),
            "seo_keywords": youtube_optimization.get("keywords", []),
            "style": style,
            "word_count": len(enhanced_script.split()) if enhanced_script else 0,
            "estimated_duration": self._estimate_duration(enhanced_script) if enhanced_script else 0,
            "generated_at": datetime.utcnow().isoformat()
        }    

    async def _get_subject_data(self, subject_slug: str) -> Dict[str, Any]:
        """Retrieve research data from database"""
        db = next(get_db())
        
        try:
            subject = db.query(Subject).filter(Subject.slug == subject_slug).first()
            if not subject:
                return None
            
            # Get claims sorted by confidence and date
            claims = db.query(Claim).filter(
                Claim.parent_subject_id == subject.id,
                Claim.confidence > 0.3  # Only include reasonably confident claims
            ).order_by(Claim.claim_date.asc(), Claim.confidence.desc()).all()
            
            # Get sources for context
            sources = db.query(Source).filter(Source.subject_id == subject.id).all()
            
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
                    "subject": claim.claim_subject,
                    "predicate": claim.predicate,
                    "object": claim.object
                }
                
                # Categorize claims
                claim_lower = claim.claim.lower()
                if any(word in claim_lower for word in ["founded", "started", "began", "launched", "born", "created"]):
                    founding_info.append(claim_data)
                elif any(word in claim_lower for word in ["funding", "investment", "raised", "ipo", "acquisition", "elected", "appointed"]):
                    business_events.append(claim_data)
                elif any(word in claim_lower for word in ["crisis", "lawsuit", "failed", "problem", "challenge", "controversy"]):
                    challenges.append(claim_data)
                elif any(word in claim_lower for word in ["success", "breakthrough", "milestone", "achievement", "award"]):
                    achievements.append(claim_data)
                
                if claim.claim_date:
                    timeline_events.append(claim_data)
            
            return {
                "subject": {
                    "name": subject.name,
                    "slug": subject.slug
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
    
    def _extract_json_from_response(self, response: str) -> Union[Dict[str, Any], List, None]:
        """Extract JSON from LLM response, handling markdown code blocks and other formats"""
        if not response:
            return None
        
        # Remove any leading/trailing whitespace
        response = response.strip()
        
        # Try to extract JSON from markdown code blocks first
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',  # ```json { ... } ```
            r'```\s*(\{.*?\})\s*```',      # ``` { ... } ```
            r'```json\s*(\[.*?\])\s*```',  # ```json [ ... ] ```
            r'```\s*(\[.*?\])\s*```',      # ``` [ ... ] ```
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse JSON from code block: {e}")
                    continue
        
        # Try to find JSON objects or arrays directly in the response
        json_object_pattern = r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        json_array_pattern = r'(\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\])'
        
        # Try object pattern first
        matches = re.findall(json_object_pattern, response, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and parsed:  # Valid non-empty dict
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # Try array pattern
        matches = re.findall(json_array_pattern, response, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, list) and parsed:  # Valid non-empty list
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # Last resort: try parsing the entire response as JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            self.logger.error(f"Could not extract any valid JSON from response. First 500 chars: {response[:500]}")
            return None
    
    async def _generate_detailed_outline(self, research_data: Dict[str, Any], style: str, target_words: int) -> List[Dict[str, Any]]:
        """Generate a detailed documentary-style outline with proper pacing and hooks"""
        subject_name = research_data["subject"]["name"]
        template = self.script_templates.get(style, self.script_templates["documentary"])
        
        # Prepare comprehensive facts for outline planning
        all_facts = {
            "timeline_events": research_data['timeline_events'],
            "founding_info": research_data['founding_info'],
            "business_events": research_data['business_events'],
            "challenges": research_data['challenges'],
            "achievements": research_data['achievements']
        }
        
        facts_summary = json.dumps(all_facts, indent=2)[:6000]  # More comprehensive data
        
        prompt = f"""Create a detailed documentary outline for a {target_words}-word YouTube video about {subject_name}.

DOCUMENTARY STRUCTURE REQUIREMENTS:
- Target: 15-17 minutes (2400-2600 words)
- 8-10 distinct sections with clear narrative arcs
- Each section should have hooks, development, and transitions
- Include character development and emotional beats
- Build tension and release throughout the story

ENGAGEMENT STRATEGY:
- Open with a compelling hook that poses a central question
- Use the "but then..." structure to maintain interest
- Include multiple mini-cliffhangers throughout
- End sections with questions or surprising revelations
- Build to emotional climaxes and resolutions

Available Research Data:
{facts_summary}

Create an outline with these sections (adjust based on available data):
1. HOOK & TEASER (200-250 words)
2. EARLY LIFE/ORIGINS (300-350 words) 
3. THE FOUNDING MOMENT (300-350 words)
4. EARLY STRUGGLES (250-300 words)
5. THE BREAKTHROUGH (300-350 words)
6. RAPID GROWTH (300-350 words)
7. MAJOR CRISIS/CHALLENGE (300-350 words)
8. TRANSFORMATION/PIVOT (250-300 words)
9. CURRENT STATE/LEGACY (200-250 words)
10. CONCLUSION & CALL TO ACTION (150-200 words)

Return ONLY a JSON array with this structure:
[
  {{
    "section_number": 1,
    "name": "Hook & Teaser",
    "word_count": 225,
    "duration_minutes": 1.5,
    "narrative_purpose": "Grab attention and establish central mystery",
    "key_points": [
      "Shocking statistic or surprising fact",
      "Central question that drives the video",
      "Preview of what's coming"
    ],
    "emotional_beat": "curiosity and intrigue",
    "hook_technique": "Dynamic hook based on story content",
    "transition_out": "But to understand how we got here, we need to go back to the beginning...",
    "b_roll_focus": "Modern success imagery contrasted with humble beginnings"
  }}
]

Make each section compelling with clear emotional arcs, specific hooks, and smooth transitions."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.3)
        
        outline_data = self._extract_json_from_response(response)
        if outline_data and isinstance(outline_data, list):
            return outline_data
        else:
            self.logger.error("Failed to generate detailed outline, using fallback")
            return self._create_detailed_fallback_outline(subject_name, target_words)

    async def _generate_enhanced_script(self, research_data: Dict[str, Any], outline: List[Dict[str, Any]], style: str, target_words: int) -> str:
        """Generate enhanced documentary-style script with proper pacing and storytelling"""
        subject_name = research_data["subject"]["name"]
        template = self.script_templates.get(style, self.script_templates["documentary"])
        
        # Prepare all available facts organized by category
        organized_facts = {
            "timeline": research_data['timeline_events'][:15],
            "founding": research_data['founding_info'][:8],
            "business": research_data['business_events'][:10],
            "challenges": research_data['challenges'][:8],
            "achievements": research_data['achievements'][:8]
        }
        
        facts_json = json.dumps(organized_facts, indent=2)[:8000]
        outline_json = json.dumps(outline, indent=2)[:4000]
        
        cultural_refs = ", ".join(self.gemini_optimization["cultural_references"])
        engagement_hooks = ", ".join(self.gemini_optimization["opening_hooks"])
        retention_techniques = ", ".join(self.gemini_optimization["retention_hooks"])
        
        prompt = f"""Write a compelling documentary script about {subject_name} for YouTube. Target length: {target_words} words (approximately 15-17 minutes).

DOCUMENTARY STYLE: {template['tone']} with {template['pacing']}

STRUCTURE: Follow the outline provided, but expand each section with rich storytelling, specific details, and engaging narration.

KEY REQUIREMENTS:
- Include timestamps [MM:SS] every 30-45 seconds
- Add [B-ROLL: description] for visual guidance  
- Use [PAUSE] for dramatic effect
- Add [MUSIC: mood] for emotional beats
- Include [ref:n] citations for facts
- Target US/Canadian audiences with cultural context

STORYTELLING ELEMENTS:
- Open with compelling hook: {engagement_hooks[:100]}...
- Use retention techniques: {retention_techniques[:100]}...
- Include cultural references: {cultural_refs[:100]}...
- Build narrative tension and emotional connection
- End with powerful, memorable conclusion

AVAILABLE RESEARCH DATA:
Timeline Events: {len(organized_facts.get('timeline', []))} events
Founding Info: {len(organized_facts.get('founding', []))} details  
Business Events: {len(organized_facts.get('business', []))} milestones
Challenges: {len(organized_facts.get('challenges', []))} controversies
Achievements: {len(organized_facts.get('achievements', []))} successes

KEY FACTS TO WEAVE IN:
{facts_json[:2000]}...

OUTLINE STRUCTURE:
{outline_json[:1500]}...

Write a complete, engaging documentary script that tells the full {subject_name} story with proper pacing, hooks, and viewer retention techniques. Make it feel like a premium Netflix documentary."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.4)
        
        if response and len(response.split()) > 1500:  # Require minimum 1500 words for quality
            self.logger.info(f"Enhanced script generated successfully: {len(response.split())} words")
            return response
        else:
            self.logger.warning(f"Enhanced script generation produced insufficient content ({len(response.split()) if response else 0} words), using comprehensive fallback")
            return await self._generate_fallback_enhanced_script(research_data, subject_name, target_words)

    def _create_detailed_fallback_outline(self, subject_name: str, target_words: int) -> List[Dict[str, Any]]:
        """Create detailed fallback outline when LLM fails"""
        return [
            {
                "section_number": 1,
                "name": "Hook & Teaser",
                "word_count": 250,
                "duration_minutes": 1.7,
                "narrative_purpose": "Grab attention with shocking revelation",
                "key_points": [
                    f"Surprising fact about {subject_name}",
                    "Central mystery or question",
                    "Preview of dramatic story ahead"
                ],
                "emotional_beat": "curiosity and intrigue",
                "hook_technique": "Compelling story-specific opening",
                "transition_out": "But to understand this story, we need to go back...",
                "b_roll_focus": "Modern success contrasted with origins"
            },
            {
                "section_number": 2,
                "name": "Origins & Early Life",
                "word_count": 350,
                "duration_minutes": 2.3,
                "narrative_purpose": "Establish character and background",
                "key_points": [
                    "Founding story and early struggles",
                    "Key personalities and their motivations",
                    "Initial vision and challenges"
                ],
                "emotional_beat": "relatability and ambition",
                "hook_technique": "Here's what most people don't know...",
                "transition_out": "But then something happened that changed everything...",
                "b_roll_focus": "Early photos, documents, locations"
            },
            {
                "section_number": 3,
                "name": "The Breakthrough",
                "word_count": 400,
                "duration_minutes": 2.7,
                "narrative_purpose": "Show the pivotal moment",
                "key_points": [
                    "Key breakthrough or turning point",
                    "How they overcame initial obstacles",
                    "Early success and validation"
                ],
                "emotional_beat": "excitement and momentum",
                "hook_technique": "This next part will blow your mind...",
                "transition_out": "But success brought new challenges...",
                "b_roll_focus": "Growth metrics, early products, team"
            },
            {
                "section_number": 4,
                "name": "Rapid Growth & Challenges",
                "word_count": 450,
                "duration_minutes": 3.0,
                "narrative_purpose": "Show scaling challenges and conflicts",
                "key_points": [
                    "Explosive growth and its problems",
                    "Internal conflicts and external pressures",
                    "Key decisions and their consequences"
                ],
                "emotional_beat": "tension and uncertainty",
                "hook_technique": "But here's where it gets complicated...",
                "transition_out": "What happened next shocked everyone...",
                "b_roll_focus": "News coverage, protests, legal documents"
            },
            {
                "section_number": 5,
                "name": "Crisis & Transformation",
                "word_count": 450,
                "duration_minutes": 3.0,
                "narrative_purpose": "Show major crisis and how they adapted",
                "key_points": [
                    "Major crisis or setback",
                    "Leadership changes and strategic pivots",
                    "How they rebuilt and transformed"
                ],
                "emotional_beat": "drama and resilience",
                "hook_technique": "The truth about what really happened...",
                "transition_out": "This transformation led to something unprecedented...",
                "b_roll_focus": "Crisis coverage, new leadership, recovery"
            },
            {
                "section_number": 6,
                "name": "Current State & Legacy",
                "word_count": 350,
                "duration_minutes": 2.3,
                "narrative_purpose": "Show current impact and future",
                "key_points": [
                    f"Current state of {subject_name}",
                    "Impact on industry and society",
                    "Future challenges and opportunities"
                ],
                "emotional_beat": "reflection and inspiration",
                "hook_technique": "Here's what this means for you...",
                "transition_out": "So what can we learn from this story?",
                "b_roll_focus": "Current operations, statistics, future vision"
            },
            {
                "section_number": 7,
                "name": "Conclusion & Lessons",
                "word_count": 250,
                "duration_minutes": 1.7,
                "narrative_purpose": "Wrap up with key takeaways",
                "key_points": [
                    "Key lessons from the story",
                    "Broader implications for viewers",
                    "Call to action for engagement"
                ],
                "emotional_beat": "inspiration and call to action",
                "hook_technique": "The real lesson here is...",
                "transition_out": "What do you think? Let me know in the comments...",
                "b_roll_focus": "Montage of key moments, future possibilities"
            }
        ]

    async def _generate_fallback_enhanced_script(self, research_data: Dict[str, Any], subject_name: str, target_words: int) -> str:
        """Generate comprehensive fallback enhanced script when main generation fails"""
        timeline_events = research_data.get('timeline_events', [])[:15]
        founding_info = research_data.get('founding_info', [])[:8]
        business_events = research_data.get('business_events', [])[:10]
        challenges = research_data.get('challenges', [])[:8]
        achievements = research_data.get('achievements', [])[:8]
        
        # Create a comprehensive documentary-style script with varied hooks
        import random
        
        # Dynamic hook selection based on company type and available data
        hook_options = [
            f"[00:00] In 1993, three engineers in a garage had no idea their graphics card experiment would create a $2 trillion revolution. [PAUSE]\n",
            f"[00:00] The email that leaked from {subject_name}'s CEO revealed a shocking truth that changed everything we thought we knew. [PAUSE]\n",
            f"[00:00] When Wall Street called {subject_name} a 'niche graphics company,' they had no idea they were witnessing the birth of the AI age. [PAUSE]\n",
            f"[00:00] This is the untold story of how {subject_name} went from near-bankruptcy to becoming the world's most valuable company. [PAUSE]\n",
            f"[00:00] Behind the billion-dollar empire lies a story of betrayal, genius, and a bet that almost destroyed everything. [PAUSE]\n",
            f"[00:00] The phone call that saved {subject_name} from collapse lasted exactly 12 minutes and changed the course of technology forever. [PAUSE]\n"
        ]
        
        selected_hook = random.choice(hook_options)
        
        script_parts = [
            f"# {subject_name}: The Untold Story\n",
            
            "## Hook & Teaser",
            selected_hook,
            
            f"[00:15] [B-ROLL: Modern {subject_name} headquarters and usage statistics] Today, {subject_name} connects billions of people worldwide, but the journey to get here was anything but smooth. [ref:1]\n",
            
            f"[00:30] [MUSIC: Mysterious, building] From a college dorm room to congressional hearings, from privacy scandals to metaverse dreams - this is the complete story of how {subject_name} became one of the most powerful and controversial companies in the world. [PAUSE]\n",
            
            "[00:45] But here's what most people don't know about the real story behind the empire...\n",
            
            "## The Genesis: From Dorm Room to Silicon Valley",
            "[01:00] [B-ROLL: Harvard campus, early 2000s footage] Our story begins in 2004, in a Harvard dorm room where a young computer science student had an idea that would change the world forever.\n"
        ]
        
        # Add founding information with narrative
        current_time = 1.3
        if founding_info:
            script_parts.append(f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [B-ROLL: Early Facebook screenshots] {founding_info[0].get('claim', 'The founding story begins')} [ref:2]\n")
            current_time += 0.5
            
            script_parts.extend([
                f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] But this wasn't just another college project. What started as a way to connect Harvard students would soon become a global phenomenon that would reshape how humanity communicates.\n",
                f"[{int(current_time+0.5//1):02d}:{int(((current_time+0.5)%1)*60):02d}] [MUSIC: Inspirational, building] The early days were marked by rapid growth, late nights, and big dreams...\n"
            ])
            current_time += 1.0
        
        # Add early growth and challenges
        script_parts.extend([
            "\n## The Rise: Building an Empire",
            f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [B-ROLL: Silicon Valley, venture capital meetings] What happened next was unprecedented in the history of technology startups.\n"
        ])
        current_time += 0.5
        
        # Add business events with storytelling
        for i, event in enumerate(business_events[:5]):
            script_parts.append(f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] {event.get('claim', 'Major business milestone')} [ref:{i+3}]\n")
            current_time += 0.4
        
        if business_events:
            script_parts.extend([
                f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [PAUSE] But with great power came great responsibility - and great controversy.\n",
                f"[{int(current_time+0.5//1):02d}:{int(((current_time+0.5)%1)*60):02d}] [MUSIC: Tension building] The company that promised to connect the world was about to face its biggest challenges yet...\n"
            ])
            current_time += 1.0
        
        # Add major challenges and controversies
        script_parts.extend([
            "\n## The Reckoning: Scandals and Setbacks", 
            f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [B-ROLL: Congressional hearing footage, news coverage] What I'm about to tell you will change how you see {subject_name} forever.\n"
        ])
        current_time += 0.5
        
        for i, challenge in enumerate(challenges[:4]):
            script_parts.append(f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] {challenge.get('claim', 'Major challenge faced')} [ref:{len(business_events)+i+3}]\n")
            current_time += 0.6
        
        if challenges:
            script_parts.extend([
                f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [PAUSE] These weren't just business setbacks - they were existential threats that could have destroyed everything.\n",
                f"[{int(current_time+0.5//1):02d}:{int(((current_time+0.5)%1)*60):02d}] But here's where the story takes an unexpected turn...\n"
            ])
            current_time += 1.0
        
        # Add transformation and current state
        script_parts.extend([
            "\n## The Transformation: Reinventing the Future",
            f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [B-ROLL: Metaverse demos, VR technology] Instead of retreating, {subject_name} made a bold bet that would either secure its future or destroy it completely.\n"
        ])
        current_time += 0.5
        
        # Add achievements and recent developments
        for i, achievement in enumerate(achievements[:4]):
            script_parts.append(f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] {achievement.get('claim', 'Major achievement')} [ref:{len(business_events)+len(challenges)+i+3}]\n")
            current_time += 0.5
        
        # Add detailed timeline events for historical context
        if timeline_events:
            script_parts.extend([
                f"\n## The Complete Timeline: Key Moments That Shaped {subject_name}",
                f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [MUSIC: Reflective] Looking back at the timeline, the pattern becomes clear:\n"
            ])
            current_time += 0.5
            
            for i, event in enumerate(timeline_events[:8]):  # More timeline events
                script_parts.append(f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] {event.get('claim', 'Historical milestone')} [ref:{len(business_events)+len(challenges)+len(achievements)+i+3}]\n")
                
                # Add context and analysis for major events
                if i % 2 == 0:  # Every other event gets additional context
                    script_parts.append(f"[{int(current_time+0.2//1):02d}:{int(((current_time+0.2)%1)*60):02d}] [PAUSE] This moment was crucial because it demonstrated {subject_name}'s ability to adapt and evolve in a rapidly changing market.\n")
                    current_time += 0.5
                else:
                    current_time += 0.3
            
            # Add more detailed analysis
            script_parts.extend([
                f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [B-ROLL: Industry analysis charts] These events weren't isolated incidents - they were part of a larger pattern of innovation, disruption, and market transformation.\n",
                f"[{int(current_time+0.5//1):02d}:{int(((current_time+0.5)%1)*60):02d}] What makes {subject_name}'s story unique is not just what they achieved, but how they navigated the challenges that could have destroyed them.\n"
            ])
            current_time += 1.0
        
        # Add industry impact section
        script_parts.extend([
            "\n## The Ripple Effect: How This Changed Everything",
            f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [B-ROLL: Industry transformation montage] But {subject_name}'s impact extends far beyond their own success.\n",
            f"[{int(current_time+0.5//1):02d}:{int(((current_time+0.5)%1)*60):02d}] They didn't just build a company - they created an entirely new category of business that hundreds of others would follow.\n",
            f"[{int(current_time+1//1):02d}:{int(((current_time+1)%1)*60):02d}] [PAUSE] The strategies they pioneered, the mistakes they made, and the lessons they learned became the playbook for an entire generation of entrepreneurs.\n",
            f"[{int(current_time+1.5//1):02d}:{int(((current_time+1.5)%1)*60):02d}] From their approach to scaling technology to their methods of user acquisition, {subject_name} fundamentally changed how we think about building global platforms.\n"
        ])
        current_time += 2.0
        
        # Add competitive landscape analysis
        script_parts.extend([
            "\n## The Competition: David vs Goliath Stories",
            f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [B-ROLL: Competitor logos and market share charts] Of course, {subject_name} didn't operate in a vacuum.\n",
            f"[{int(current_time+0.5//1):02d}:{int(((current_time+0.5)%1)*60):02d}] The battles they fought against established players, emerging competitors, and regulatory challenges shaped not just their own destiny, but the entire industry.\n",
            f"[{int(current_time+1//1):02d}:{int(((current_time+1)%1)*60):02d}] [MUSIC: Competitive tension] Each competitive move was like a chess game played on a global scale, with billions of users and trillions of dollars at stake.\n",
            f"[{int(current_time+1.5//1):02d}:{int(((current_time+1.5)%1)*60):02d}] The strategies that worked, the ones that failed, and the unexpected moves that changed the game forever - all of this became part of the {subject_name} legacy.\n"
        ])
        current_time += 2.0
        
        # Powerful conclusion with multiple perspectives
        script_parts.extend([
            "\n## The Legacy: What It All Means",
            f"[{int(current_time//1):02d}:{int((current_time%1)*60):02d}] [B-ROLL: Global connectivity, people using technology] So what can we learn from the {subject_name} story?\n",
            f"[{int(current_time+0.5//1):02d}:{int(((current_time+0.5)%1)*60):02d}] This isn't just a story about technology - it's a story about power, responsibility, and the unintended consequences of connecting the world.\n",
            f"[{int(current_time+1//1):02d}:{int(((current_time+1)%1)*60):02d}] [PAUSE] The decisions made in Silicon Valley boardrooms don't just affect stock prices - they shape how billions of people communicate, think, and see the world.\n",
            f"[{int(current_time+1.5//1):02d}:{int(((current_time+1.5)%1)*60):02d}] For entrepreneurs, the {subject_name} story offers lessons about scaling, pivoting, and maintaining vision while adapting to reality.\n",
            f"[{int(current_time+2//1):02d}:{int(((current_time+2)%1)*60):02d}] For investors, it demonstrates both the incredible potential and the significant risks of backing transformative technologies.\n",
            f"[{int(current_time+2.5//1):02d}:{int(((current_time+2.5)%1)*60):02d}] For regulators and policymakers, it highlights the challenges of governing innovation in a rapidly evolving digital landscape.\n",
            f"[{int(current_time+3//1):02d}:{int(((current_time+3)%1)*60):02d}] And for all of us as consumers and citizens, it raises important questions about privacy, power, and the role of technology in our daily lives.\n",
            f"[{int(current_time+3.5//1):02d}:{int(((current_time+3.5)%1)*60):02d}] Whether {subject_name} succeeds or fails in its next chapter will determine not just the future of their industry, but the future of human connection itself.\n",
            f"[{int(current_time+4//1):02d}:{int(((current_time+4)%1)*60):02d}] [MUSIC: Inspirational conclusion] The story is far from over. In fact, the most important chapters may still be unwritten.\n",
            f"[{int(current_time+4.5//1):02d}:{int(((current_time+4.5)%1)*60):02d}] What do you think? Will {subject_name} successfully reinvent itself for the next generation, or will it become a cautionary tale about the dangers of unchecked power?\n",
            f"[{int(current_time+5//1):02d}:{int(((current_time+5)%1)*60):02d}] Have they learned from their mistakes, or are they destined to repeat them? And what does their story tell us about the future of innovation in America?\n",
            f"[{int(current_time+5.5//1):02d}:{int(((current_time+5.5)%1)*60):02d}] Let me know your thoughts in the comments below. And if you found this story as fascinating as I did, make sure to subscribe for more deep dives into the companies that shape our world.\n",
            f"[{int(current_time+6//1):02d}:{int(((current_time+6)%1)*60):02d}] Until next time, keep questioning the stories behind the headlines, and remember - every empire started with a single idea."
        ])
        
        return "\n\n".join(script_parts)

    async def _generate_outline_and_script(self, research_data: Dict[str, Any], style: str, target_words: int) -> Dict[str, Any]:
        """Batch generate outline and full script in one or two LLM calls to reduce API hits."""
        subject_name = research_data["subject"]["name"]
        template = self.script_templates.get(style, self.script_templates["storytelling"])
        
        # Prepare relevant facts summary (truncated for token efficiency)
        all_facts_summary = json.dumps({
            "timeline_events": research_data['timeline_events'][:10],
            "founding_info": research_data['founding_info'][:5],
            "business_events": research_data['business_events'][:5],
            "challenges": research_data['challenges'][:5],
            "achievements": research_data['achievements'][:5]
        }, indent=2)[:4000]  # Truncate to fit tokens
        
        engagement_hooks = ", ".join(self.gemini_optimization["opening_hooks"][:3])
        retention_techniques = ", ".join(self.gemini_optimization["retention_hooks"][:3])
        cultural_refs = ", ".join(self.gemini_optimization["cultural_references"][:5])
        
        prompt = f"""Create a YouTube script about {subject_name} optimized for US/Canadian audiences and YouTube's Gemini algorithm. Target: {target_words} words.

GEMINI ALGORITHM OPTIMIZATION:
- Viewer-centric narrative focusing on audience needs and interests
- Strong engagement hooks and retention techniques throughout
- Clear value proposition from the opening
- Natural integration of cultural context and business terminology
- Structured for maximum watch time and completion rates

AUDIENCE TARGETING (US/Canadian viewers):
- Use American English spelling and terminology
- Include cultural references: {cultural_refs}
- Focus on business/financial angles and market impact
- Emphasize entrepreneurship, innovation, and success stories
- Use familiar currency ($USD) and business metrics

Style Requirements:
- Tone: {template['tone']}
- Style: {template['style']}
- Pacing: {template['pacing']}

ENGAGEMENT TECHNIQUES TO INCLUDE:
- Opening hooks: {engagement_hooks}
- Retention phrases: {retention_techniques}
- Clear section transitions that maintain interest
- Questions that encourage viewer engagement

Research Data Available:
- Total verified facts: {research_data['total_claims']}
- Key founding events: {len(research_data['founding_info'])}
- Major milestones: {len(research_data['business_events'])}
- Challenges/Failures: {len(research_data['challenges'])}
- Achievements/Successes: {len(research_data['achievements'])}

Key Facts to Include:
{all_facts_summary}

IMPORTANT: Return ONLY a valid JSON object with this exact structure:
{{
  "outline": [
    {{
      "name": "Hook",
      "word_count": 100,
      "key_points": ["attention-grabbing fact with cultural relevance"],
      "narrative_angle": "compelling hook targeting US/Canadian viewers",
      "transition": "smooth transition maintaining engagement"
    }},
    {{
      "name": "Introduction/Early Life", 
      "word_count": 200,
      "key_points": ["early background with American context", "founding story with business angle"],
      "narrative_angle": "origin story emphasizing entrepreneurship",
      "transition": "leads into challenges with retention hook"
    }}
  ],
  "script": "# {subject_name}: The Complete Story\n\n## Hook\n[00:00] What if I told you that {subject_name}...\n\n## Introduction\n[01:00] More content with cultural context..."
}}

Structure: Hook, Introduction/Early Life, Major Challenge, Breakthrough, Growth/Peak, Major Setback, Current State, Legacy/Impact, Conclusion.

Include [MM:SS] timestamps, [B-ROLL: description] markers, [ref:n] citations, and natural engagement questions.

Return only the JSON - no additional text or markdown formatting."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.3)
        
        outline_and_script_data = self._extract_json_from_response(response)
        
        if (outline_and_script_data and 
            isinstance(outline_and_script_data, dict) and 
            "outline" in outline_and_script_data and 
            "script" in outline_and_script_data):
            return {
                "outline": outline_and_script_data["outline"], 
                "script": outline_and_script_data["script"]
            }
        else:
            self.logger.error(f"Failed to parse outline and script from LLM response. Attempting fallback...")
            
            # Try a simpler approach for fallback
            fallback_script = await self._generate_simple_script(research_data, subject_name, target_words)
            return {
                "outline": self._create_simple_outline(subject_name, target_words),
                "script": fallback_script
            }
    
    async def _generate_simple_script(self, research_data: Dict[str, Any], subject_name: str, target_words: int) -> str:
        """Generate a simple script as fallback when JSON parsing fails"""
        try:
            facts_summary = "\n".join([
                f"- {claim['claim']}" for claim in 
                research_data['timeline_events'][:5] + research_data['founding_info'][:3]
            ])
            
            prompt = f"""Write a {target_words}-word YouTube script about {subject_name}.

Key facts to include:
{facts_summary}

Format as markdown with ## section headers and [MM:SS] timestamps.
Make it engaging and informative. Return only the script text."""
            
            messages = [{"role": "user", "content": prompt}]
            response = await self.call_llm(messages, temperature=0.3)
            return response if response else f"# {subject_name}\n\n[00:00] Script content based on available research data."
            
        except Exception as e:
            self.logger.error(f"Fallback script generation failed: {e}")
            return f"# {subject_name}\n\n[00:00] Script content based on available research data."
    
    def _create_simple_outline(self, subject_name: str, target_words: int) -> List[Dict[str, Any]]:
        """Create a simple outline as fallback"""
        return [
            {
                "name": "Introduction",
                "word_count": target_words // 4,
                "key_points": [f"Introduction to {subject_name}"],
                "narrative_angle": "establishing context",
                "transition": "leads into main story"
            },
            {
                "name": "Main Content",
                "word_count": target_words // 2,
                "key_points": ["Key events and milestones"],
                "narrative_angle": "core narrative",
                "transition": "building to conclusion"
            },
            {
                "name": "Conclusion",
                "word_count": target_words // 4,
                "key_points": ["Impact and legacy"],
                "narrative_angle": "wrapping up the story",
                "transition": "final thoughts"
            }
        ]
    
    async def _generate_broll_suggestions(self, script: str, research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate B-roll suggestions for the script"""
        if not script:
            return []
        
        subject_name = research_data["subject"]["name"]
        
        # Truncate script for token limit
        script_excerpt = script[:2000]
        
        prompt = f"""Generate B-roll suggestions for this {subject_name} video script.

Script excerpt:
{script_excerpt}

Return ONLY a JSON array with this structure:
[
  {{
    "timestamp": "00:15",
    "duration_s": 5,
    "visual_type": "archival_footage",
    "description": "Early company office footage",
    "keywords": ["office", "startup", "early days"],
    "mood": "nostalgic"
  }}
]

Return only the JSON array - no additional text."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.3)
        
        broll_suggestions = self._extract_json_from_response(response)
        if broll_suggestions and isinstance(broll_suggestions, list):
            return broll_suggestions
        else:
            self.logger.error(f"Failed to parse B-roll suggestions. Returning default suggestions.")
            # Return some basic suggestions
            return [
                {
                    "timestamp": "00:00",
                    "duration_s": 10,
                    "visual_type": "title_card",
                    "description": f"Title card with {subject_name}",
                    "keywords": [subject_name.lower(), "introduction"],
                    "mood": "professional"
                }
            ]
    
    def _estimate_duration(self, script: str) -> float:
        """Estimate video duration based on word count (documentary style: 140 words per minute with pauses)"""
        if not script:
            return 0.0
        word_count = len(script.split())
        # Documentary style is slower with dramatic pauses and emphasis
        # Account for B-roll segments, music, and dramatic pauses
        base_duration = word_count / 140  # Slower than typical narration
        
        # Add time for pauses, B-roll, and music cues
        pause_count = script.count('[PAUSE]')
        broll_count = script.count('[B-ROLL:')
        music_count = script.count('[MUSIC:')
        
        additional_time = (pause_count * 0.1) + (broll_count * 0.05) + (music_count * 0.03)
        
        return round(base_duration + additional_time, 1)
    
    def _extract_timestamps(self, script: str) -> List[str]:
        """Extract timestamp markers from script"""
        if not script:
            return []
        timestamps = re.findall(r'\[(\d{1,2}:\d{2})\]', script)
        return timestamps
    
    async def _generate_youtube_optimization(self, script: str, research_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate YouTube-optimized titles, thumbnails, and SEO keywords for US/Canadian audiences"""
        if not script:
            return {"titles": [], "thumbnails": [], "keywords": []}
        
        subject_name = research_data["subject"]["name"]
        script_excerpt = script[:1500]  # Use first part of script for context
        
        prompt = f"""Generate YouTube optimization content for a {subject_name} documentary targeting US/Canadian audiences.

Script context:
{script_excerpt}

Generate:

1. VIDEO TITLES (5 titles, max 60 characters each):
- Clickable and engaging for US/Canadian viewers
- Include power words and emotional triggers
- Use American English spelling
- Focus on business/success angles
- Include numbers, questions, or surprising facts

2. THUMBNAIL CONCEPTS (3 concepts):
- Visual elements that appeal to North American audiences
- Text overlays (2-4 words max)
- Color schemes and design elements
- Emotional appeal and curiosity gaps

3. SEO KEYWORDS (10 keywords):
- Terms US/Canadian audiences search for
- Business and entrepreneurship related
- Include both broad and specific terms
- Consider trending topics in North America

Return ONLY a JSON object:
{{
  "titles": [
    "How {subject_name} Built a $X Billion Empire",
    "The Untold Story of {subject_name}'s Rise to Power"
  ],
  "thumbnails": [
    {{
      "concept": "Split screen comparison",
      "text_overlay": "BEFORE/AFTER",
      "visual_elements": "Early photo vs current success image",
      "color_scheme": "Bold red and blue contrast",
      "emotional_appeal": "Transformation and success"
    }}
  ],
  "keywords": [
    "{subject_name} documentary",
    "business success story",
    "entrepreneurship"
  ]
}}

Focus on high-CPM audience interests: business, technology, success stories, and American entrepreneurship culture."""
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.4)
        
        optimization_data = self._extract_json_from_response(response)
        if optimization_data and isinstance(optimization_data, dict):
            return optimization_data
        else:
            # Fallback optimization
            return {
                "titles": [
                    f"The Untold Story of {subject_name}",
                    f"How {subject_name} Changed Everything",
                    f"{subject_name}: Rise to Success",
                    f"The Real Story Behind {subject_name}",
                    f"{subject_name}'s Billion Dollar Journey"
                ],
                "thumbnails": [
                    {
                        "concept": "Portrait with success elements",
                        "text_overlay": "SUCCESS",
                        "visual_elements": f"{subject_name} photo with money/growth graphics",
                        "color_scheme": "Green and gold (success colors)",
                        "emotional_appeal": "Achievement and aspiration"
                    }
                ],
                "keywords": [
                    f"{subject_name} documentary", "business success", "entrepreneurship",
                    "startup story", "American business", "success story"
                ]
            }
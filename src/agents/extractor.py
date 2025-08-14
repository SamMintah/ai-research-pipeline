from typing import Dict, Any, List
import json
from datetime import datetime
import re
from src.agents.base import BaseAgent

class ExtractorAgent(BaseAgent):
    """Agent for extracting facts and claims from web content"""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract facts from source content"""
        content = input_data.get("content", "")
        source_url = input_data.get("source_url", "")
        company_name = input_data.get("company_name", "")
        
        if not content:
            return {"claims": [], "error": "No content provided"}
        
        # Extract claims using LLM
        claims = await self._extract_claims(content, company_name, source_url)
        
        # Extract dates and entities
        enhanced_claims = []
        for claim in claims:
            enhanced_claim = await self._enhance_claim(claim, content)
            enhanced_claims.append(enhanced_claim)
        
        return {
            "claims": enhanced_claims,
            "source_url": source_url,
            "extraction_timestamp": datetime.utcnow().isoformat()
        }
    
    async def _extract_claims(self, content: str, company_name: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract factual claims from content"""
        prompt = f"""Extract factual claims about {company_name} from this content. 
        
        Focus on:
        - Founding dates and founders
        - Funding rounds and amounts  
        - Key product launches
        - Major business events
        - Financial metrics
        - Strategic decisions
        - Leadership changes
        
        For each claim, provide:
        - claim: The factual statement
        - date: When it happened (if mentioned)
        - evidence_snippet: The exact text supporting this claim
        - confidence: 0.0-1.0 based on how clearly stated
        
        Return as JSON array. Only include verifiable facts, not opinions.
        
        Content:
        {content[:3000]}...
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.1)
        
        try:
            claims = json.loads(response)
            return claims if isinstance(claims, list) else []
        except:
            return []   
 
    async def _enhance_claim(self, claim: Dict[str, Any], content: str) -> Dict[str, Any]:
        """Enhance claim with additional metadata"""
        claim_text = claim.get("claim", "")
        
        # Extract entities (subject, predicate, object)
        entities = await self._extract_entities(claim_text)
        claim.update(entities)
        
        # Parse and normalize dates
        date_str = claim.get("date", "")
        if date_str:
            parsed_date = self._parse_date(date_str)
            claim["parsed_date"] = parsed_date
        
        # Find exact position in content
        evidence = claim.get("evidence_snippet", "")
        if evidence and evidence in content:
            start_pos = content.find(evidence)
            claim["start_char"] = start_pos
            claim["end_char"] = start_pos + len(evidence)
        
        return claim
    
    async def _extract_entities(self, claim_text: str) -> Dict[str, str]:
        """Extract subject, predicate, object from claim"""
        prompt = f"""Break down this claim into subject, predicate, and object:
        
        Claim: "{claim_text}"
        
        Return JSON with:
        - subject: Who/what the claim is about
        - predicate: The action or relationship
        - object: What happened or the target
        
        Example: "Netflix was founded in 1997" -> 
        {{"subject": "Netflix", "predicate": "was founded", "object": "1997"}}
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.1)
        
        try:
            entities = json.loads(response)
            return {
                "subject": entities.get("subject", ""),
                "predicate": entities.get("predicate", ""),
                "object": entities.get("object", "")
            }
        except:
            return {"subject": "", "predicate": "", "object": ""}
    
    def _parse_date(self, date_str: str) -> str:
        """Parse various date formats into ISO format"""
        # Common date patterns
        patterns = [
            r'\b(\d{4})\b',  # Year only
            r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',  # MM/DD/YYYY
            r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b',  # YYYY-MM-DD
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                if len(match.groups()) == 1:  # Year only
                    return f"{match.group(1)}-01-01"
                elif len(match.groups()) == 3:
                    if pattern == patterns[1]:  # MM/DD/YYYY
                        month, day, year = match.groups()
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    elif pattern == patterns[2]:  # YYYY-MM-DD
                        return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
                    elif pattern == patterns[3]:  # Month DD, YYYY
                        month_name, day, year = match.groups()
                        month_num = {
                            'january': '01', 'february': '02', 'march': '03', 'april': '04',
                            'may': '05', 'june': '06', 'july': '07', 'august': '08',
                            'september': '09', 'october': '10', 'november': '11', 'december': '12'
                        }.get(month_name.lower(), '01')
                        return f"{year}-{month_num}-{day.zfill(2)}"
        
        return ""  # Could not parse
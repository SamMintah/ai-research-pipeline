from typing import Dict, Any, List
import json
import re
from src.agents.base import BaseAgent

class ExtractorAgent(BaseAgent):
    """Agent for extracting facts and claims from web content in batches."""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts facts from a batch of source documents."""
        sources = input_data.get("sources", [])
        company_name = input_data.get("company_name", "")
        
        if not sources:
            return {"claims": [], "error": "No sources provided"}
        
        # Extract claims from the batch of sources
        claims = await self._extract_claims_from_batch(sources, company_name)
        
        # Enhance claims with entities and parsed dates
        enhanced_claims = []
        for claim in claims:
            # The content needed for enhancement is not readily available here.
            # We will simplify the enhancement for now.
            enhanced_claim = await self._enhance_claim(claim)
            enhanced_claims.append(enhanced_claim)
        
        return {
            "claims": enhanced_claims,
            "processed_sources_count": len(sources)
        }

    async def _extract_claims_from_batch(self, sources: List[Dict[str, Any]], company_name: str) -> List[Dict[str, Any]]:
        """Extracts factual claims from a batch of documents using a single API call."""
        
        # Prepare the documents for the prompt, keeping the payload reasonable
        prompt_documents = []
        for source in sources:
            prompt_documents.append({
                "source_url": source.get("url"),
                "content": source.get("content", "")[:5000] # Truncate content for the prompt
            })

        prompt = f"""Your task is to act as a meticulous fact extractor. From the provided JSON array of documents about {company_name}, extract all verifiable, factual claims.

        **Input Format:**
        You will be given a JSON array of document objects, where each object has a "source_url" and "content".

        **Output Format Rules:**
        1. The output MUST be a valid JSON array of claim objects.
        2. Each object in the array represents a single factual claim from ONE of the documents.
        3. CRITICAL: Each claim object MUST include the "source_url" from which it was extracted.
        4. If no facts are found across all documents, return an empty array: [].

        **JSON Object Schema for Each Claim:**
        - "claim": (string) The concise factual statement.
        - "date": (string) The date of the event in YYYY-MM-DD format if available, otherwise null.
        - "evidence_snippet": (string) The exact text from the source document that supports the claim.
        - "confidence": (float) Your confidence in the claim's accuracy from 0.0 to 1.0.
        - "source_url": (string) The exact URL of the source document for this claim.

        **Now, extract facts from the following documents:**

        {json.dumps(prompt_documents, indent=2)}
        """

        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.0)

        try:
            match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
            json_str = match.group(1) if match else response
            claims = json.loads(json_str)
            return claims if isinstance(claims, list) else []
        except json.JSONDecodeError:
            print(f"Failed to decode JSON from LLM batch response.")
            return []
        except Exception as e:
            print(f"An unexpected error occurred during batch claim extraction: {e}")
            return []

    async def _enhance_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance claim with additional metadata (entities, parsed date)."""
        claim_text = claim.get("claim", "")
        
        entities = await self._extract_entities(claim_text)
        claim.update(entities)
        
        date_str = claim.get("date", "")
        if date_str:
            parsed_date = self._parse_date(date_str)
            claim["parsed_date"] = parsed_date
        
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
        if not date_str: return ""
        try:
            # Attempt to use dateutil for robust parsing
            from dateutil.parser import parse
            dt = parse(date_str)
            return dt.strftime('%Y-%m-%d')
        except (ImportError, ValueError, TypeError):
            # Fallback to regex for simple cases if dateutil fails or is not available
            patterns = [
                r'\b(\d{4})\b',  # Year only
                r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b',  # YYYY-MM-DD
                r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b'
            ]
            for pattern in patterns:
                match = re.search(pattern, date_str, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 1: return f"{match.group(1)}-01-01"
                    if len(match.groups()) == 3:
                        if pattern == patterns[1]: return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
                        if pattern == patterns[2]:
                            month_name, day, year = match.groups()
                            month_num = {
                                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                                'september': '09', 'october': '10', 'november': '11', 'december': '12'
                            }.get(month_name.lower(), '01')
                            return f"{year}-{month_num}-{day.zfill(2)}"
            return ""

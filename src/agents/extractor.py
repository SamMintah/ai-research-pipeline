from typing import Dict, Any, List
import json
import re
import asyncio
from datetime import datetime, timedelta
from src.agents.base import BaseAgent
from src.llm.base_provider import LLMProvider

class RateLimiter:
    """Rate limiter to track and control API request frequency."""
    
    def __init__(self, requests_per_minute: int = 50):
        self.requests_per_minute = requests_per_minute
        self.requests = []
    
    async def wait_if_needed(self):
        """Wait if we're approaching rate limits."""
        now = datetime.now()
        
        # Remove requests older than 1 minute
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(minutes=1)]
        
        if len(self.requests) >= self.requests_per_minute:
            sleep_time = 60 - (now - self.requests[0]).total_seconds()
            if sleep_time > 0:
                print(f"Rate limiter: waiting {sleep_time:.2f}s to avoid rate limit")
                await asyncio.sleep(sleep_time)
        
        self.requests.append(now)

def estimate_tokens(text: str) -> int:
    """Simple token estimation (roughly 4 chars per token for English)."""
    return len(text) // 4

import logging

class ExtractorAgent(BaseAgent):
    """Agent for extracting facts and claims from web content with comprehensive rate limit optimization."""
    
    def __init__(self, llm_provider: LLMProvider, max_documents_per_sub_batch: int = 5, 
                 requests_per_minute: int = 50, max_concurrent_requests: int = 5):
        super().__init__(llm_provider)
        self.logger = logging.getLogger(__name__) # Initialize logger
        self.max_documents_per_sub_batch = max_documents_per_sub_batch
        self.request_delay = 0.1  # 100ms between requests
        self.max_retries = 3
        self.backoff_factor = 2
        self.max_tokens_per_request = 4000  # Conservative limit
        
        # Rate limiting components
        self.rate_limiter = RateLimiter(requests_per_minute)
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.requests_made = 0

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts facts from a batch of source documents with comprehensive rate limit handling."""
        sources = input_data.get("sources", [])
        subject_name = input_data.get("subject_name", "")
        
        if not sources:
            return {"claims": [], "error": "No sources provided"}
        
        print(f"Processing {len(sources)} sources for {company_name}")
        
        # Dynamically adjust batch size based on content length
        sources = self._optimize_batch_sizes(sources)
        
        # Extract claims from the batch of sources
        claims = await self._extract_claims_from_batch(sources, company_name)
        
        # Enhance claims in batches to reduce API calls
        enhanced_claims = await self._enhance_claims_batch(claims)
        
        print(f"Completed processing. Made {self.requests_made} API requests total")
        
        return {
            "claims": enhanced_claims,
            "processed_sources_count": len(sources),
            "api_requests_made": self.requests_made
        }

    def _optimize_batch_sizes(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimize content length and batch sizes based on token estimation."""
        optimized_sources = []
        
        for source in sources:
            content = source.get("content", "")
            
            # Estimate tokens and truncate if necessary
            estimated_tokens = estimate_tokens(content)
            if estimated_tokens > 3000:  # Leave room for prompt and response
                # Truncate but try to keep complete sentences
                truncated_content = content[:3000 * 4]  # Rough char limit
                
                # Find the last complete sentence
                last_period = truncated_content.rfind('.')
                if last_period > len(truncated_content) * 0.8:  # If we're close to the end
                    truncated_content = truncated_content[:last_period + 1]
                
                source["content"] = truncated_content
                source["was_truncated"] = True
            
            optimized_sources.append(source)
        
        return optimized_sources
        
    async def _extract_claims_from_batch(self, sources: List[Dict[str, Any]], company_name: str) -> List[Dict[str, Any]]:
        """Extracts factual claims with enhanced prompt to include entities in one call."""
        
        all_extracted_claims = []
        
        # Dynamically adjust sub-batch size based on content
        for i in range(0, len(sources), self.max_documents_per_sub_batch):
            sub_batch_sources = sources[i:i + self.max_documents_per_sub_batch]
            
            # Check total token estimate for this sub-batch
            total_content_length = sum(len(s.get("content", "")) for s in sub_batch_sources)
            
            # If sub-batch is too large, reduce it
            if estimate_tokens(str(total_content_length)) > 2500:
                # Reduce sub-batch size
                actual_batch_size = max(1, len(sub_batch_sources) // 2)
                sub_batch_sources = sub_batch_sources[:actual_batch_size]
            
            # Prepare the documents for the prompt
            prompt_documents = []
            for source in sub_batch_sources:
                prompt_documents.append({
                    "source_url": source.get("url"),
                    "content": source.get("content", "")
                })

            # Enhanced prompt to extract claims AND entities in one call
            prompt = f"""Your response MUST be a valid JSON array, and contain ONLY the JSON array. Do NOT include any other text, preambles, or explanations.

            Your task is to act as a meticulous fact extractor. From the provided JSON array of documents about {company_name}, extract all verifiable, factual claims WITH their semantic components.

            **Input Format:**
            You will be given a JSON array of document objects, where each object has a "source_url" and "content".

            **Output Format Rules:**
            1. The output MUST be a valid JSON array of claim objects.
            2. Each object in the array represents a single factual claim from ONE of the documents.
            3. CRITICAL: Each claim object MUST include the "source_url" from which it was extracted.
            4. If no facts are found across all documents, return an empty array: [].

            **Enhanced JSON Object Schema for Each Claim:**
            - "claim": (string) The concise factual statement.
            - "date": (string) The date of the event in YYYY-MM-DD format if available, otherwise null.
            - "evidence_snippet": (string) The exact text from the source document that supports the claim.
            - "confidence": (float) Your confidence in the claim's accuracy from 0.0 to 1.0.
            - "source_url": (string) The exact URL of the source document for this claim.
            - "subject": (string) Who/what the claim is about.
            - "predicate": (string) The action or relationship.
            - "object": (string) What happened or the target.

            **Example:**
            For claim "Netflix was founded in 1997":
            - "subject": "Netflix"
            - "predicate": "was founded"
            - "object": "1997"

            **Now, extract facts from the following documents:**

            {json.dumps(prompt_documents, indent=2)}
            """

            messages = [{"role": "user", "content": prompt}]
            
            # Make API call with comprehensive rate limiting
            response = await self._call_llm_with_comprehensive_backoff(messages, temperature=0.0)
            
            if response is not None:
                try:
                    # Use robust JSON parsing instead of direct json.loads
                    claims = self._parse_llm_json_response(response, list)
                    if claims:  # Check if we got a non-empty list
                        # Parse dates for each claim
                        for claim in claims:
                            date_str = claim.get("date", "")
                            if date_str:
                                parsed_date = self._parse_date(date_str)
                                if parsed_date:  # Only set if valid
                                    claim["parsed_date"] = parsed_date
                        
                        all_extracted_claims.extend(claims)
                        print(f"Extracted {len(claims)} claims from sub-batch {i//self.max_documents_per_sub_batch + 1}")
                    else:
                        print(f"No claims extracted from sub-batch {i//self.max_documents_per_sub_batch + 1}")
                except Exception as e:
                    print(f"An unexpected error occurred during sub-batch claim extraction: {e}")
            else:
                print(f"LLM call returned None for sub-batch {i//self.max_documents_per_sub_batch + 1}")
                print("This usually indicates API failures, rate limiting, or authentication issues")
        
        return all_extracted_claims

    async def _enhance_claims_batch(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance multiple claims in a single API call if needed (fallback for missing entities)."""
        
        # Check if claims already have entity information
        claims_needing_enhancement = []
        enhanced_claims = []
        
        for claim in claims:
            if not all(key in claim for key in ["subject", "predicate", "object"]):
                claims_needing_enhancement.append(claim)
            else:
                enhanced_claims.append(claim)
        
        # If no claims need enhancement, return as-is
        if not claims_needing_enhancement:
            return claims
        
        # Process in batches of 10 claims at a time
        batch_size = 10
        for i in range(0, len(claims_needing_enhancement), batch_size):
            batch_claims = claims_needing_enhancement[i:i + batch_size]
            
            # Create batch enhancement prompt
            claims_text = []
            for idx, claim in enumerate(batch_claims):
                claims_text.append(f"{idx}: {claim.get('claim', '')}")
            
            prompt = f"""Break down these claims into subject, predicate, and object components:

            Claims:
            {chr(10).join(claims_text)}

            Return a JSON array where each object corresponds to the claim at the same index, with:
            - "subject": Who/what the claim is about
            - "predicate": The action or relationship  
            - "object": What happened or the target

            Example format: [{{"subject": "Netflix", "predicate": "was founded", "object": "1997"}}]
            """
            
            messages = [{"role": "user", "content": prompt}]
            response = await self._call_llm_with_comprehensive_backoff(messages, temperature=0.1)
            
            if response:
                try:
                    entities_batch = json.loads(response)
                    if isinstance(entities_batch, list) and len(entities_batch) == len(batch_claims):
                        for claim, entities in zip(batch_claims, entities_batch):
                            claim.update({
                                "subject": entities.get("subject", ""),
                                "predicate": entities.get("predicate", ""),
                                "object": entities.get("object", "")
                            })
                            enhanced_claims.append(claim)
                    else:
                        # Fallback: add empty entities
                        for claim in batch_claims:
                            claim.update({"subject": "", "predicate": "", "object": ""})
                            enhanced_claims.append(claim)
                except json.JSONDecodeError:
                    # Fallback: add empty entities
                    for claim in batch_claims:
                        claim.update({"subject": "", "predicate": "", "object": ""})
                        enhanced_claims.append(claim)
            else:
                    # Fallback: add empty entities
                    for claim in batch_claims:
                        claim.update({"subject": "", "predicate": "", "object": ""})
                        enhanced_claims.append(claim)
            
            # Add delay between enhancement batches
            if i + batch_size < len(claims_needing_enhancement):
                await asyncio.sleep(self.request_delay)
        
        return enhanced_claims

    async def _call_llm_with_comprehensive_backoff(self, messages: List[Dict], temperature: float = 0.0) -> str:
        """Make LLM call with comprehensive rate limiting including semaphores and rate limiter."""
        
        async with self.semaphore:  # Limit concurrent requests
            await self.rate_limiter.wait_if_needed()  # Check rate limits
            
            for attempt in range(self.max_retries + 1):
                try:
                    # Add debug logging
                    print(f"Making LLM call (attempt {attempt + 1}/{self.max_retries + 1})")
                    response = await self.call_llm(messages, temperature=temperature)
                    self.requests_made += 1
                    print(f"LLM call successful. Total requests: {self.requests_made}")
                    return response
                    
                except Exception as e:
                    error_str = str(e).lower()
                    print(f"LLM call failed on attempt {attempt + 1}: {e}")
                    
                    # Check if it's a rate limit error
                    if any(term in error_str for term in ["rate limit", "429", "quota", "too many requests"]):
                        if attempt < self.max_retries:
                            wait_time = self.request_delay * (self.backoff_factor ** attempt) * 10  # Longer waits for rate limits
                            print(f"Rate limit hit. Waiting {wait_time:.2f}s before retry {attempt + 1}/{self.max_retries}")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"Max retries reached for rate limit error: {e}")
                            return None
                    
                    # Check for context length errors
                    elif any(term in error_str for term in ["context length", "token limit", "maximum context"]):
                        print(f"Context length error - prompt too long: {e}")
                        return None
                    
                    # Check for authentication errors
                    elif any(term in error_str for term in ["authentication", "api key", "unauthorized", "401", "403"]):
                        print(f"Authentication error: {e}")
                        return None
                    
                    # Other errors
                    else:
                        print(f"Non-rate-limit error: {e}")
                        if attempt < self.max_retries:
                            wait_time = self.request_delay * (self.backoff_factor ** attempt)
                            print(f"Retrying in {wait_time:.2f}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"Max retries reached for error: {e}")
                            return None
            
            print("All retry attempts exhausted")
            return None

    def _parse_date(self, date_str: str) -> str:
        """Parse various date formats into ISO format with validation."""
        if not date_str or date_str.lower() in ['null', 'none', 'n/a']:
            return ""

        # Handle YYYY-MM-00 format by correcting to YYYY-MM-01
        if re.fullmatch(r'\d{4}-\d{2}-00', date_str):
            date_str = date_str.replace('-00', '-01')
            self.logger.warning(f"Corrected malformed date from LLM: {date_str} to {date_str}")
    
        # Quick regex patterns for common formats with validation
        patterns = [
            (r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', self._validate_ymd_date),
            (r'\b(\d{4})\b', lambda m: f"{m.group(1)}-01-01"),
            (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', self._parse_month_date)
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                try:
                    result = formatter(match)
                    # Validate the result is a proper date
                    if result and self._is_valid_date(result):
                        return result
                except:
                    continue
        
        # Fallback to dateutil if available
        try:
            from dateutil.parser import parse
            dt = parse(date_str)
            return dt.strftime('%Y-%m-%d')
        except (ImportError, ValueError, TypeError):
            return ""
    
    def _parse_llm_json_response(self, response: str, expected_type: type = list) -> Any:
        """Parse LLM JSON response with robust error handling, including markdown code blocks."""
        if not response:
            self.logger.warning("LLM response is empty.")
            return [] if expected_type == list else {}

        cleaned_response = response.strip()

        # 1. Try to extract JSON from markdown code blocks (```json ... ```)
        json_block_match = re.search(r'```json\s*(.*?)\s*```', cleaned_response, re.DOTALL)
        if json_block_match:
            json_content = json_block_match.group(1)
            try:
                result = json.loads(json_content)
                if isinstance(result, expected_type):
                    self.logger.info("Successfully parsed JSON from markdown block.")
                    return result
                else:
                    self.logger.warning(f"JSON from markdown block is not of expected type {expected_type.__name__}.")
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse JSON from markdown block: {e}. Content: {json_content[:200]}...")

        # 2. Try direct JSON parsing (if no markdown block or parsing failed)
        try:
            result = json.loads(cleaned_response)
            if isinstance(result, expected_type):
                self.logger.info("Successfully parsed direct JSON response.")
                return result
            else:
                self.logger.warning(f"Direct JSON response is not of expected type {expected_type.__name__}.")
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse direct JSON response: {e}. Content: {cleaned_response[:200]}...")

        # 3. Fallback: Try to extract JSON by finding the first and last delimiters
        start_idx = -1
        end_idx = -1

        if expected_type == list:
            start_idx = cleaned_response.find('[')
            end_idx = cleaned_response.rfind(']')
        elif expected_type == dict:
            start_idx = cleaned_response.find('{')
            end_idx = cleaned_response.rfind('}')

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_substring = cleaned_response[start_idx : end_idx + 1]
            try:
                result = json.loads(json_substring)
                if isinstance(result, expected_type):
                    self.logger.info("Successfully parsed JSON by finding delimiters.")
                    return result
                else:
                    self.logger.warning(f"JSON from delimiters is not of expected type {expected_type.__name__}.")
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse JSON from delimiters: {e}. Content: {json_substring[:200]}...")
        else:
            self.logger.warning("Could not find valid JSON delimiters in response.")

        self.logger.error(f"Could not parse JSON from LLM response. Returning empty {expected_type.__name__}. Raw response: {response[:500]}...")
        return [] if expected_type == list else {}
    
    from typing import Dict, Any, List
import json
import re
import asyncio
from datetime import datetime, timedelta
from src.agents.base import BaseAgent
from src.llm.base_provider import LLMProvider

class RateLimiter:
    """Rate limiter to track and control API request frequency."""
    
    def __init__(self, requests_per_minute: int = 50):
        self.requests_per_minute = requests_per_minute
        self.requests = []
    
    async def wait_if_needed(self):
        """Wait if we're approaching rate limits."""
        now = datetime.now()
        
        # Remove requests older than 1 minute
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(minutes=1)]
        
        if len(self.requests) >= self.requests_per_minute:
            sleep_time = 60 - (now - self.requests[0]).total_seconds()
            if sleep_time > 0:
                print(f"Rate limiter: waiting {sleep_time:.2f}s to avoid rate limit")
                await asyncio.sleep(sleep_time)
        
        self.requests.append(now)

def estimate_tokens(text: str) -> int:
    """Simple token estimation (roughly 4 chars per token for English)."""
    return len(text) // 4

import logging

class ExtractorAgent(BaseAgent):
    """Agent for extracting facts and claims from web content with comprehensive rate limit optimization."""
    
    def __init__(self, llm_provider: LLMProvider, max_documents_per_sub_batch: int = 5, 
                 requests_per_minute: int = 50, max_concurrent_requests: int = 5):
        super().__init__(llm_provider)
        self.max_documents_per_sub_batch = max_documents_per_sub_batch
        self.request_delay = 0.1  # 100ms between requests
        self.max_retries = 3
        self.backoff_factor = 2
        self.max_tokens_per_request = 4000  # Conservative limit
        
        # Rate limiting components
        self.rate_limiter = RateLimiter(requests_per_minute)
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.requests_made = 0

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts facts from a batch of source documents with comprehensive rate limit handling."""
        sources = input_data.get("sources", [])
        subject_name = input_data.get("subject_name", "")
        
        if not sources:
            return {"claims": [], "error": "No sources provided"}
        
        self.logger.info(f"Processing {len(sources)} sources for {subject_name}")
        
        # Dynamically adjust batch size based on content length
        sources = self._optimize_batch_sizes(sources)
        
        # Extract claims from the batch of sources
        claims = await self._extract_claims_from_batch(sources, subject_name)
        
        # Enhance claims in batches to reduce API calls
        enhanced_claims = await self._enhance_claims_batch(claims)
        
        self.logger.info(f"Completed processing. Made {self.requests_made} API requests total")
        
        return {
            "claims": enhanced_claims,
            "processed_sources_count": len(sources),
            "api_requests_made": self.requests_made
        }

    def _optimize_batch_sizes(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimize content length and batch sizes based on token estimation."""
        optimized_sources = []
        
        for source in sources:
            content = source.get("content", "")
            
            # Estimate tokens and truncate if necessary
            estimated_tokens = estimate_tokens(content)
            if estimated_tokens > 3000:  # Leave room for prompt and response
                # Truncate but try to keep complete sentences
                truncated_content = content[:3000 * 4]  # Rough char limit
                
                # Find the last complete sentence
                last_period = truncated_content.rfind('.')
                if last_period > len(truncated_content) * 0.8:  # If we're close to the end
                    truncated_content = truncated_content[:last_period + 1]
                
                source["content"] = truncated_content
                source["was_truncated"] = True
            
            optimized_sources.append(source)
        
        return optimized_sources
        
    async def _extract_claims_from_batch(self, sources: List[Dict[str, Any]], subject_name: str) -> List[Dict[str, Any]]:
        """Extracts factual claims with enhanced prompt to include entities in one call."""
        
        all_extracted_claims = []
        
        # Dynamically adjust sub-batch size based on content
        for i in range(0, len(sources), self.max_documents_per_sub_batch):
            sub_batch_sources = sources[i:i + self.max_documents_per_sub_batch]
            
            # Check total token estimate for this sub-batch
            total_content_length = sum(len(s.get("content", "")) for s in sub_batch_sources)
            
            # If sub-batch is too large, reduce it
            if estimate_tokens(str(total_content_length)) > 2500:
                # Reduce sub-batch size
                actual_batch_size = max(1, len(sub_batch_sources) // 2)
                sub_batch_sources = sub_batch_sources[:actual_batch_size]
            
            # Prepare the documents for the prompt
            prompt_documents = []
            for source in sub_batch_sources:
                prompt_documents.append({
                    "source_url": source.get("url"),
                    "content": source.get("content", "")
                })

            # Enhanced prompt to extract claims AND entities in one call
            prompt = f"""Your response MUST be a valid JSON array, and contain ONLY the JSON array. Do NOT include any other text, preambles, or explanations.

            Your task is to act as a meticulous fact extractor. From the provided JSON array of documents about the subject '{subject_name}', extract all verifiable, factual claims WITH their semantic components.

            **Input Format:**
            You will be given a JSON array of document objects, where each object has a "source_url" and "content".

            **Output Format Rules:**
            1. The output MUST be a valid JSON array of claim objects.
            2. Each object in the array represents a single factual claim from ONE of the documents.
            3. CRITICAL: Each claim object MUST include the "source_url" from which it was extracted.
            4. If no facts are found across all documents, return an empty array: [].

            **Enhanced JSON Object Schema for Each Claim:**
            - "claim": (string) The concise factual statement.
            - "date": (string) The date of the event in YYYY-MM-DD format if available, otherwise null.
            - "evidence_snippet": (string) The exact text from the source document that supports the claim.
            - "confidence": (float) Your confidence in the claim's accuracy from 0.0 to 1.0.
            - "source_url": (string) The exact URL of a source document for this claim.
            - "subject": (string) Who/what the claim is about (should be related to '{subject_name}').
            - "predicate": (string) The action or relationship.
            - "object": (string) What happened or the target.

            **Example:**
            For claim "Netflix was founded in 1997":
            - "subject": "Netflix"
            - "predicate": "was founded"
            - "object": "1997"

            **Now, extract facts from the following documents:**

            {json.dumps(prompt_documents, indent=2)}
            """

            messages = [{"role": "user", "content": prompt}]
            
            # Make API call with comprehensive rate limiting
            response = await self._call_llm_with_comprehensive_backoff(messages, temperature=0.0)
            
            if response is not None:
                claims = self._parse_json_from_response(response)
                if claims and isinstance(claims, list):
                    # Parse dates for each claim
                    for claim in claims:
                        date_str = claim.get("date", "")
                        if date_str:
                            parsed_date = self._parse_date(date_str)
                            if parsed_date:  # Only set if valid
                                claim["parsed_date"] = parsed_date
                    
                    all_extracted_claims.extend(claims)
                    self.logger.info(f"Extracted {len(claims)} claims from sub-batch {i//self.max_documents_per_sub_batch + 1}")
                else:
                    self.logger.warning(f"No claims extracted or parsed from sub-batch {i//self.max_documents_per_sub_batch + 1}")
            else:
                self.logger.error(f"LLM call returned None for sub-batch {i//self.max_documents_per_sub_batch + 1}")
        
        return all_extracted_claims

    async def _enhance_claims_batch(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance multiple claims in a single API call if needed (fallback for missing entities)."""
        
        claims_needing_enhancement = [c for c in claims if not all(k in c for k in ["subject", "predicate", "object"])]
        enhanced_claims = [c for c in claims if all(k in c for k in ["subject", "predicate", "object"])]
        
        if not claims_needing_enhancement:
            return claims
        
        batch_size = 10
        for i in range(0, len(claims_needing_enhancement), batch_size):
            batch_claims = claims_needing_enhancement[i:i + batch_size]
            
            claims_text = [f"{idx}: {claim.get('claim', '')}" for idx, claim in enumerate(batch_claims)]
            
            prompt = f"""Break down these claims into subject, predicate, and object components:

            Claims:
            {chr(10).join(claims_text)}

            Return a JSON array where each object corresponds to the claim at the same index, with:
            - "subject": Who/what the claim is about
            - "predicate": The action or relationship  
            - "object": What happened or the target

            Example format: [{{"subject": "Netflix", "predicate": "was founded", "object": "1997"}}]
            """
            
            messages = [{"role": "user", "content": prompt}]
            response = await self._call_llm_with_comprehensive_backoff(messages, temperature=0.1)
            
            entities_batch = self._parse_json_from_response(response)
            if entities_batch and isinstance(entities_batch, list) and len(entities_batch) == len(batch_claims):
                for claim, entities in zip(batch_claims, entities_batch):
                    claim.update({
                        "subject": entities.get("subject", ""),
                        "predicate": entities.get("predicate", ""),
                        "object": entities.get("object", "")
                    })
                    enhanced_claims.append(claim)
            else:
                self.logger.warning("Failed to enhance batch, falling back for claims.")
                for claim in batch_claims:
                    claim.update({"subject": "", "predicate": "", "object": ""})
                    enhanced_claims.append(claim)
            
            if i + batch_size < len(claims_needing_enhancement):
                await asyncio.sleep(self.request_delay)
        
        return enhanced_claims

    async def _call_llm_with_comprehensive_backoff(self, messages: List[Dict], temperature: float = 0.0) -> str:
        """Make LLM call with comprehensive rate limiting including semaphores and rate limiter."""
        
        async with self.semaphore:
            await self.rate_limiter.wait_if_needed()
            
            for attempt in range(self.max_retries + 1):
                try:
                    self.logger.info(f"Making LLM call (attempt {attempt + 1}/{self.max_retries + 1})")
                    response = await self.call_llm(messages, temperature=temperature)
                    self.requests_made += 1
                    self.logger.info(f"LLM call successful. Total requests: {self.requests_made}")
                    return response
                    
                except Exception as e:
                    error_str = str(e).lower()
                    self.logger.error(f"LLM call failed on attempt {attempt + 1}: {e}")
                    
                    if any(term in error_str for term in ["rate limit", "429", "quota", "too many requests"]):
                        if attempt < self.max_retries:
                            wait_time = self.request_delay * (self.backoff_factor ** attempt) * 10
                            self.logger.warning(f"Rate limit hit. Waiting {wait_time:.2f}s before retry {attempt + 1}/{self.max_retries}")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            self.logger.error(f"Max retries reached for rate limit error: {e}")
                            return None
                    
                    elif any(term in error_str for term in ["context length", "token limit", "maximum context"]):
                        self.logger.error(f"Context length error - prompt too long: {e}")
                        return None
                    
                    elif any(term in error_str for term in ["authentication", "api key", "unauthorized", "401", "403"]):
                        self.logger.error(f"Authentication error: {e}")
                        return None
                    
                    else:
                        if attempt < self.max_retries:
                            wait_time = self.request_delay * (self.backoff_factor ** attempt)
                            self.logger.warning(f"Retrying in {wait_time:.2f}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            self.logger.error(f"Max retries reached for error: {e}")
                            return None
            
            self.logger.error("All retry attempts exhausted")
            return None

    def _parse_date(self, date_str: str) -> str:
        """Parse various date formats into ISO format with validation."""
        if not date_str or date_str.lower() in ['null', 'none', 'n/a']:
            return ""

        if re.fullmatch(r'\d{4}-\d{2}-00', date_str):
            date_str = date_str.replace('-00', '-01')
            self.logger.warning(f"Corrected malformed date from LLM: {date_str} to {date_str}")
    
        patterns = [
            (r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', self._validate_ymd_date),
            (r'\b(\d{4})\b', lambda m: f"{m.group(1)}-01-01"),
            (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', self._parse_month_date)
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                try:
                    result = formatter(match)
                    if result and self._is_valid_date(result):
                        return result
                except:
                    continue
        
        try:
            from dateutil.parser import parse
            dt = parse(date_str)
            return dt.strftime('%Y-%m-%d')
        except (ImportError, ValueError, TypeError):
            return ""
    
    def _validate_ymd_date(self, match) -> str:
        """Validate and format YYYY-MM-DD date."""
        try:
            year, month, day = map(int, match.groups())
            if 1800 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                # Further validation for days in month could be added here
                return f"{year}-{month:02d}-{day:02d}"
        except (ValueError, TypeError):
            pass
        return ""
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string represents a valid date."""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _parse_month_date(self, match) -> str:
        """Helper to parse month name dates with validation."""
        try:
            month_name, day, year = match.groups()
            month_map = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            month = month_map[month_name.lower()]
            return f"{year}-{month:02d}-{int(day):02d}"
        except (ValueError, KeyError):
            return ""

    
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string represents a valid date."""
        try:
            parts = date_str.split('-')
            if len(parts) != 3:
                return False
            
            year, month, day = map(int, parts)
            
            # Basic range checks
            if year < 1800 or year > 2100:
                return False
            if month < 1 or month > 12:
                return False
            if day < 1 or day > 31:
                return False
            
            # Try to create a date to validate
            from datetime import date
            date(year, month, day)
            return True
        except (ValueError, ImportError):
            return False
    
    def _parse_month_date(self, match) -> str:
        """Helper to parse month name dates with validation."""
        month_name, day, year = match.groups()
        
        try:
            day_int = int(day)
            year_int = int(year)
            
            # Validate ranges
            if year_int < 1800 or year_int > 2100:
                return ""
            if day_int < 1 or day_int > 31:
                day_int = 1
            
            month_num = {
                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                'september': '09', 'october': '10', 'november': '11', 'december': '12'
            }.get(month_name.lower(), '01')
            
            # Additional month-specific day validation
            if month_num in ['04', '06', '09', '11'] and day_int > 30:
                day_int = 30
            elif month_num == '02' and day_int > 29:
                day_int = 28  # Conservative for February
            
            result = f"{year_int}-{month_num}-{day_int:02d}"
            return result if self._is_valid_date(result) else ""
            
        except ValueError:
            return ""
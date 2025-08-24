from typing import Dict, Any, List
import json
import aiohttp
from src.agents.base import BaseAgent
from src.config import config
from src.llm.base_provider import LLMProvider

class ResearcherAgent(BaseAgent):
    """Agent for discovering and gathering information sources about a subject, optimized for US/Canadian audiences and YouTube's Gemini algorithm."""
    
    def __init__(self, llm_provider: LLMProvider):
        super().__init__(llm_provider)
        # Enhanced search categories optimized for high-CPM audiences and engagement
        self.search_categories = [
            "history and origin story",
            "key events and timeline", 
            "cultural impact and significance",
            "controversies and criticisms",
            "public reception and media coverage",
            "key people involved or associated",
            "in-depth analysis and documentaries",
            "technical details or composition",
            "legacy and modern relevance"
        ]
        
        # High-authority sources preferred by US/Canadian audiences
        self.preferred_sources = [
            "wsj.com", "nytimes.com", "bloomberg.com", "ft.com", "reuters.com",
            "techcrunch.com", "forbes.com", "businessinsider.com", "cnbc.com",
            "cnn.com", "bbc.com", "theguardian.com", "washingtonpost.com",
            "harvard.edu", "stanford.edu", "mit.edu", "sec.gov", "crunchbase.com",
            "wikipedia.org", "wired.com", "theatlantic.com", "newyorker.com"
        ]
        
        # US/Canadian cultural context keywords to prioritize
        self.cultural_keywords = [
            "Silicon Valley", "Wall Street", "Fortune 500", "NYSE", "NASDAQ",
            "American Dream", "startup culture", "venture capital", "IPO",
            "innovation", "disruption", "entrepreneurship", "corporate America"
        ]
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Discover sources for a subject."""
        subject_name = input_data.get("subject_name")
        max_sources = input_data.get("max_sources", 50)
        
        # Generate search queries
        queries = await self._generate_search_queries(subject_name)
        
        # Search for sources
        sources = []
        for query in queries[:10]:  # Limit initial queries
            search_results = await self._search_web(query)
            sources.extend(search_results)
        
        # Rank and filter sources
        ranked_sources = await self._rank_sources(sources, subject_name)
        
        return {
            "sources": ranked_sources[:max_sources],
            "total_found": len(sources),
            "queries_used": queries
        }  
  
    async def _generate_search_queries(self, subject_name: str) -> List[str]:
        """Generate targeted search queries optimized for US/Canadian audiences and high-engagement content."""
        categories_str = ", ".join(self.search_categories)
        cultural_context = ", ".join(self.cultural_keywords)
        
        prompt = f"""Generate 15 specific search queries for '{subject_name}' targeting US/Canadian audiences for a YouTube documentary.

        OPTIMIZATION REQUIREMENTS:
        - Focus on US/Canadian perspectives and cultural relevance
        - Include business/financial angles (IPOs, valuations, market impact)
        - Emphasize stories that resonate with North American viewers
        - Include controversy and human interest angles for engagement
        - Target sources from major US/Canadian media outlets
        
        Categories to cover: {categories_str}
        
        Cultural context to include: {cultural_context}
        
        Return as a JSON array of strings. Make queries specific and engaging.
        
        Example for 'Apple': ["Apple IPO 1980 Wall Street reaction", "Steve Jobs Stanford commencement speech", "Apple vs FBI encryption controversy", "Silicon Valley garage startup myth Apple", "Apple market cap trillion dollar milestone"]
        Example for 'Netflix': ["Netflix vs Blockbuster disruption story", "Netflix Silicon Valley startup culture", "Reed Hastings Stanford MBA background", "Netflix stock market performance IPO", "Netflix content spending Hollywood impact"]
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.4)
        
        queries = self._parse_json_from_response(response)
        if queries and isinstance(queries, list):
            return queries
        else:
            self.logger.warning("Failed to parse search queries from LLM, using fallback.")
            # Combined generic and specific fallback queries for better coverage
            return [
                f"{subject_name} history",
                f"{subject_name} origin story",
                f"{subject_name} timeline",
                f"{subject_name} biography",
                f"{subject_name} documentary",
                f"{subject_name} analysis",
                f"{subject_name} impact and legacy",
                f"{subject_name} significance",
                f"{subject_name} controversies and challenges",
                f"{subject_name} major achievements",
                f"{subject_name} interviews",
                f"{subject_name} career"
            ]
    
    async def _search_web(self, query: str) -> List[Dict[str, Any]]:
        """Search web using configured search engine"""
        if config.get("engines", {}).get("web_search") == "serper":
            return await self._search_serper(query)
        else:
            return []  # Add other search engines as needed
    
    async def _search_serper(self, query: str) -> List[Dict[str, Any]]:
        """Search using Serper API"""
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": config.get("search", {}).get("serper_api_key", ""),
            "Content-Type": "application/json"
        }
        
        payload = {
            "q": query,
            "num": 10
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []
                        
                        for item in data.get("organic", []):
                            results.append({
                                "url": item.get("link"),
                                "title": item.get("title"),
                                "snippet": item.get("snippet"),
                                "domain": item.get("link", "").split("/")[2] if item.get("link") else "",
                                "query": query
                            })
                        
                        return results
        except Exception as e:
            print(f"Search error: {e}")
        
        return []
    
    async def _rank_sources(self, sources: List[Dict[str, Any]], subject_name: str) -> List[Dict[str, Any]]:
        """Rank sources by relevance, authority, and US/Canadian audience appeal"""
        # Enhanced ranking system prioritizing high-CPM audience sources
        authority_domains = {
            # Tier 1: Premium US/Canadian sources (highest authority)
            "wsj.com": 6, "nytimes.com": 6, "bloomberg.com": 6, "ft.com": 6,
            "reuters.com": 6, "sec.gov": 6, "harvard.edu": 6, "stanford.edu": 6,
            
            # Tier 2: Major business/tech sources
            "forbes.com": 5, "businessinsider.com": 5, "cnbc.com": 5,
            "techcrunch.com": 5, "crunchbase.com": 5, "wired.com": 5,
            
            # Tier 3: Established media
            "cnn.com": 4, "bbc.com": 4, "theguardian.com": 4, 
            "washingtonpost.com": 4, "theatlantic.com": 4, "newyorker.com": 4,
            
            # Tier 4: Reference sources
            "wikipedia.org": 4, "mit.edu": 4,
            
            # Lower priority sources
            "medium.com": 2, "linkedin.com": 2
        }
        
        for source in sources:
            domain = source.get("domain", "")
            source["authority_score"] = authority_domains.get(domain, 1)
            
            # Boost for subject name in title
            if subject_name.lower() in source.get("title", "").lower():
                source["authority_score"] += 1
            
            # Boost for US/Canadian cultural keywords
            title_snippet = (source.get("title", "") + " " + source.get("snippet", "")).lower()
            for keyword in self.cultural_keywords:
                if keyword.lower() in title_snippet:
                    source["authority_score"] += 0.5
                    break
            
            # Boost for engagement-driving content
            engagement_keywords = ["controversy", "scandal", "failure", "success", "breakthrough", 
                                 "behind the scenes", "untold story", "secret", "revealed"]
            for keyword in engagement_keywords:
                if keyword in title_snippet:
                    source["authority_score"] += 0.3
                    break
            
            # Prioritize preferred sources
            if domain in self.preferred_sources:
                source["authority_score"] += 1
        
        # Sort by authority score
        return sorted(sources, key=lambda x: x.get("authority_score", 0), reverse=True)
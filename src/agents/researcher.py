from typing import Dict, Any, List
import json
import aiohttp
from src.agents.base import BaseAgent
from src.config import config

class ResearcherAgent(BaseAgent):
    """Agent for discovering and gathering company information sources"""
    
    def __init__(self):
        super().__init__()
        self.search_categories = [
            "founding history",
            "funding rounds",
            "founder interviews", 
            "company crises",
            "product launches",
            "acquisitions",
            "lawsuits",
            "pivots",
            "competition"
        ]
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Discover sources for a company"""
        company_name = input_data.get("company_name")
        max_sources = input_data.get("max_sources", 50)
        
        # Generate search queries
        queries = await self._generate_search_queries(company_name)
        
        # Search for sources
        sources = []
        for query in queries[:10]:  # Limit initial queries
            search_results = await self._search_web(query)
            sources.extend(search_results)
        
        # Rank and filter sources
        ranked_sources = await self._rank_sources(sources, company_name)
        
        return {
            "sources": ranked_sources[:max_sources],
            "total_found": len(sources),
            "queries_used": queries
        }  
  
    async def _generate_search_queries(self, company_name: str) -> List[str]:
        """Generate targeted search queries for the company"""
        prompt = f"""Generate 15 specific search queries to research {company_name} for a company story video.
        
        Include queries for: founding story, funding history, founder interviews, major pivots, 
        crises/challenges, product launches, acquisitions, lawsuits, competition, recent news.
        
        Return as JSON array of strings. Make queries specific and varied.
        
        Example format: ["Netflix founding story Reed Hastings", "Netflix Blockbuster rejection 2000"]
        """
        
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm(messages, temperature=0.3)
        
        try:
            queries = json.loads(response)
            return queries if isinstance(queries, list) else []
        except:
            # Fallback queries
            return [
                f"{company_name} founding story",
                f"{company_name} founder interview",
                f"{company_name} funding history",
                f"{company_name} IPO",
                f"{company_name} crisis challenge",
                f"{company_name} pivot strategy",
                f"{company_name} acquisition",
                f"{company_name} lawsuit legal",
                f"{company_name} competition rivals"
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
    
    async def _rank_sources(self, sources: List[Dict[str, Any]], company_name: str) -> List[Dict[str, Any]]:
        """Rank sources by relevance and authority"""
        # Simple ranking - can be enhanced with ML
        authority_domains = {
            "wikipedia.org": 5,
            "sec.gov": 5,
            "wsj.com": 4,
            "nytimes.com": 4,
            "bloomberg.com": 4,
            "ft.com": 4,
            "reuters.com": 4,
            "techcrunch.com": 3,
            "forbes.com": 3,
            "businessinsider.com": 3,
            "crunchbase.com": 4
        }
        
        for source in sources:
            domain = source.get("domain", "")
            source["authority_score"] = authority_domains.get(domain, 1)
            
            # Boost score if company name in title
            if company_name.lower() in source.get("title", "").lower():
                source["authority_score"] += 1
        
        # Sort by authority score
        return sorted(sources, key=lambda x: x.get("authority_score", 0), reverse=True)
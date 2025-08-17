import aiohttp
import asyncio
from bs4 import BeautifulSoup
from typing import Optional
import time
from urllib.parse import urljoin, urlparse

class WebCrawler:
    """Web crawler for extracting content from URLs"""
    
    def __init__(self, session: aiohttp.ClientSession, delay: float = 1.0):
        self.session = session
        self.delay = delay
        self.last_request_time = {}
    
    async def crawl_url(self, url: str) -> Optional[str]:
        """Crawl a single URL and extract text content"""
        try:
            # Rate limiting per domain
            domain = urlparse(url).netloc
            if domain in self.last_request_time:
                elapsed = time.time() - self.last_request_time[domain]
                if elapsed < self.delay:
                    await asyncio.sleep(self.delay - elapsed)
            
            self.last_request_time[domain] = time.time()
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._extract_text(html)
                else:
                    print(f"HTTP {response.status} for {url}")
                    return None
                    
        except Exception as e:
            print(f"Crawl error for {url}: {e}")
            return None
    
    def _extract_text(self, html: str) -> str:
        """Extract clean text from HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text from main content areas
            content_selectors = [
                'article', 'main', '.content', '.post-content', 
                '.entry-content', '.article-body', '.story-body'
            ]
            
            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = elements[0].get_text()
                    break
            
            # Fallback to body if no content area found
            if not content:
                body = soup.find('body')
                if body:
                    content = body.get_text()
            
            # Clean up text
            lines = (line.strip() for line in content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:10000]  # Limit to 10k chars
            
        except Exception as e:
            print(f"Text extraction error: {e}")
            return ""
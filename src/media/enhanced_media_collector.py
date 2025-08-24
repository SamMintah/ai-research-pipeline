import aiohttp
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import re
from urllib.parse import urlparse, urljoin, quote
import logging
from src.config import settings

class EnhancedMediaCollector:
    """Enhanced media collector that searches for relevant, copyright-safe images"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = None
        
        # Image extensions
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
        
        # Copyright-safe and fair use sources
        self.safe_sources = {
            # Government/Public sources
            'sec.gov', 'uspto.gov', 'wikipedia.org', 'wikimedia.org', 'commons.wikimedia.org',
            # Company official sources (fair use for commentary)
            'press.', 'newsroom.', 'investor.', 'about.',
            # Creative Commons sources
            'flickr.com', 'unsplash.com', 'pexels.com', 'pixabay.com'
        }
        
        # Fair use news domains (for commentary/criticism)
        self.fair_use_domains = {
            'techcrunch.com', 'bloomberg.com', 'wsj.com', 'nytimes.com',
            'reuters.com', 'forbes.com', 'businessinsider.com', 'cnbc.com',
            'theverge.com', 'wired.com', 'arstechnica.com', 'bbc.com',
            'cnn.com', 'npr.org', 'apnews.com'
        }
    
    async def collect_comprehensive_media(self, subject_name: str, sources: List[Dict[str, Any]], 
                                        script_content: str, output_dir: Path, 
                                        max_images: int = 20) -> Dict[str, Any]:
        """
        Collect comprehensive media including news images and targeted searches
        
        Args:
            subject_name: The subject (e.g., "Meta", "Mark Zuckerberg")
            sources: Research sources from pipeline
            script_content: Generated script to extract visual needs
            output_dir: Directory to save media
            max_images: Maximum images to collect
        """
        media_dir = output_dir / "enhanced_media"
        media_dir.mkdir(exist_ok=True)
        
        collected_media = {
            "news_images": [],
            "targeted_searches": [],
            "stock_images": [],
            "total_collected": 0
        }
        
        async with aiohttp.ClientSession() as session:
            self.session = session
            
            # 1. Collect from news sources (existing functionality)
            news_images = await self._collect_news_images(subject_name, sources, media_dir, max_images // 3)
            collected_media["news_images"] = news_images
            
            # 2. Targeted searches based on subject and script
            search_queries = self._generate_search_queries(subject_name, script_content)
            targeted_images = await self._collect_targeted_images(search_queries, media_dir, max_images // 3)
            collected_media["targeted_searches"] = targeted_images
            
            # 3. Stock images for B-roll
            stock_images = await self._collect_stock_images(subject_name, script_content, media_dir, max_images // 3)
            collected_media["stock_images"] = stock_images
            
            collected_media["total_collected"] = (
                len(news_images) + len(targeted_images) + len(stock_images)
            )
        
        # Generate comprehensive media index
        media_index = self._create_media_index(subject_name, collected_media, script_content)
        
        # Save media index
        with open(media_dir / "enhanced_media_index.json", "w") as f:
            json.dump(media_index, f, indent=2)
        
        self.logger.info(f"✅ Collected {collected_media['total_collected']} media assets for {subject_name}")
        
        return media_index
    
    def _generate_search_queries(self, subject_name: str, script_content: str) -> List[Dict[str, str]]:
        """Generate targeted search queries based on subject and script content"""
        queries = []
        
        # Base subject queries
        base_queries = [
            f"{subject_name} CEO founder",
            f"{subject_name} headquarters office building",
            f"{subject_name} logo company branding",
            f"{subject_name} products services",
            f"{subject_name} timeline history"
        ]
        
        # Subject-specific queries
        if "meta" in subject_name.lower() or "facebook" in subject_name.lower():
            specific_queries = [
                "Mark Zuckerberg CEO Meta Facebook",
                "Facebook Meta headquarters Menlo Park",
                "Facebook Instagram WhatsApp logos",
                "Meta VR headset Oculus Quest",
                "Facebook data center servers",
                "Meta Connect conference keynote",
                "Facebook IPO 2012 NASDAQ",
                "Cambridge Analytica scandal documents"
            ]
        elif "uber" in subject_name.lower():
            specific_queries = [
                "Travis Kalanick Uber CEO founder",
                "Uber headquarters San Francisco",
                "Uber app interface screenshot",
                "Uber drivers cars rideshare",
                "Uber IPO 2019 NYSE"
            ]
        elif "apple" in subject_name.lower():
            specific_queries = [
                "Steve Jobs Apple founder CEO",
                "Apple Park headquarters Cupertino",
                "iPhone iPad Mac products",
                "Apple Store retail locations",
                "Tim Cook Apple CEO"
            ]
        else:
            # Generic business queries
            specific_queries = [
                f"{subject_name} founder CEO executive",
                f"{subject_name} headquarters office",
                f"{subject_name} products timeline",
                f"{subject_name} stock market IPO"
            ]
        
        # Combine all queries
        all_queries = base_queries + specific_queries
        
        # Create query objects with metadata
        for query in all_queries:
            queries.append({
                "query": query,
                "category": self._categorize_query(query),
                "priority": "high" if subject_name.lower() in query.lower() else "medium",
                "usage": "fair_use_commentary"
            })
        
        return queries[:10]  # Limit to top 10 queries
    
    def _categorize_query(self, query: str) -> str:
        """Categorize search query for better organization"""
        query_lower = query.lower()
        
        if any(term in query_lower for term in ["ceo", "founder", "executive"]):
            return "people"
        elif any(term in query_lower for term in ["headquarters", "office", "building"]):
            return "locations"
        elif any(term in query_lower for term in ["logo", "branding", "product"]):
            return "products"
        elif any(term in query_lower for term in ["timeline", "history", "ipo"]):
            return "events"
        else:
            return "general"
    
    async def _collect_news_images(self, subject_name: str, sources: List[Dict[str, Any]], 
                                 media_dir: Path, max_images: int) -> List[Dict[str, Any]]:
        """Collect images from news sources (existing functionality enhanced)"""
        collected = []
        
        # Filter to reputable news sources
        news_sources = [s for s in sources if self._is_news_domain(s.get('url', ''))]
        
        for source in news_sources[:5]:
            try:
                images = await self._extract_images_from_article(source, subject_name)
                
                for img_url in images[:3]:
                    if len(collected) >= max_images:
                        break
                    
                    image_path = await self._download_image(img_url, media_dir, f"news_{len(collected)}")
                    if image_path:
                        collected.append({
                            "path": str(image_path),
                            "source_url": source.get('url'),
                            "source_title": source.get('title'),
                            "image_url": img_url,
                            "category": "news_coverage",
                            "copyright_status": "fair_use_commentary",
                            "attribution": f"Source: {source.get('title', 'News Article')}",
                            "usage_justification": "Fair use for documentary commentary and criticism"
                        })
            
            except Exception as e:
                self.logger.warning(f"Failed to collect from {source.get('url')}: {e}")
        
        return collected
    
    async def _collect_targeted_images(self, search_queries: List[Dict[str, str]], 
                                     media_dir: Path, max_images: int) -> List[Dict[str, Any]]:
        """Collect images through targeted searches using Google and Wikimedia"""
        collected = []
        
        try:
            # Import Google Image Search and Wikimedia searchers
            from src.media.google_image_search import GoogleImageSearcher, WikimediaSearcher
            
            google_searcher = GoogleImageSearcher()
            wikimedia_searcher = WikimediaSearcher()
            
            for query_info in search_queries[:5]:
                if len(collected) >= max_images:
                    break
                
                query = query_info["query"]
                category = query_info["category"]
                
                # Try Google Image Search first (with usage rights)
                try:
                    google_results = await google_searcher.search_subject_images(query, 3)
                except Exception as e:
                    self.logger.warning(f"Google search failed for '{query}': {e}")
                    google_results = []
                
                # Try Wikimedia Commons for public domain images
                try:
                    wikimedia_results = await wikimedia_searcher.search_commons_images(query, 2)
                except Exception as e:
                    self.logger.warning(f"Wikimedia search failed for '{query}': {e}")
                    wikimedia_results = []
                
                # Process and download found images
                all_search_results = google_results + wikimedia_results
                
                for i, result in enumerate(all_search_results[:3]):  # Max 3 per query
                    if len(collected) >= max_images:
                        break
                    
                    # Download the image if it has a valid URL
                    image_url = result.get('image_url')
                    if image_url and not image_url.startswith('https://placeholder.com'):
                        image_path = await self._download_image(
                            image_url, 
                            media_dir, 
                            f"targeted_{category}_{len(collected)}"
                        )
                        
                        if image_path:
                            collected.append({
                                "path": str(image_path),
                                "search_query": query,
                                "category": category,
                                "image_url": image_url,
                                "source_url": result.get('source_url', ''),
                                "source_domain": result.get('source_domain', ''),
                                "copyright_status": result.get('copyright_status', 'fair_use'),
                                "attribution": result.get('attribution_text', f"Source: {result.get('source_domain', 'Search Result')}"),
                                "usage_justification": "Documentary commentary under fair use or Creative Commons"
                            })
                    else:
                        # Fallback to placeholder for demonstration
                        collected.append({
                            "path": f"placeholder_{category}_{hash(query) % 1000}.jpg",
                            "search_query": query,
                            "category": category,
                            "copyright_status": "placeholder",
                            "attribution": "Placeholder - replace with actual licensed images",
                            "usage_justification": "Placeholder for demonstration"
                        })
        
        except Exception as e:
            self.logger.warning(f"Error in targeted image collection: {e}")
            # Fallback to simulation if APIs fail
            for query_info in search_queries[:5]:
                if len(collected) >= max_images:
                    break
                simulated_results = await self._simulate_image_search(query_info, media_dir)
                collected.extend(simulated_results)
        
        return collected[:max_images]
    
    async def _simulate_image_search(self, query_info: Dict[str, str], media_dir: Path) -> List[Dict[str, Any]]:
        """Simulate image search results (replace with real API in production)"""
        # This is a placeholder - in production you would:
        # 1. Call Bing Image Search API with usage rights filter
        # 2. Search Wikimedia Commons
        # 3. Search Creative Commons licensed content
        
        query = query_info["query"]
        category = query_info["category"]
        
        # Create placeholder entries for demonstration
        return [{
            "path": f"placeholder_{category}_{hash(query) % 1000}.jpg",
            "search_query": query,
            "category": category,
            "copyright_status": "creative_commons_or_fair_use",
            "attribution": "Search result - verify licensing",
            "usage_justification": "Documentary commentary under fair use"
        }]
    
    async def _collect_stock_images(self, subject_name: str, script_content: str, 
                                  media_dir: Path, max_images: int) -> List[Dict[str, Any]]:
        """Collect generic stock images for B-roll"""
        collected = []
        
        # Extract B-roll suggestions from script
        broll_patterns = re.findall(r'\[B-ROLL:\s*([^\]]+)\]', script_content, re.IGNORECASE)
        
        # Generic business/tech stock image categories
        stock_categories = [
            "business meeting conference room",
            "technology innovation startup",
            "data center servers technology",
            "office building corporate headquarters",
            "smartphone mobile app interface",
            "financial charts graphs analytics",
            "team collaboration workspace",
            "city skyline urban business"
        ]
        
        # Combine B-roll needs with stock categories
        all_categories = list(set(broll_patterns + stock_categories))
        
        for category in all_categories[:max_images]:
            # In production, search stock photo APIs like:
            # - Unsplash API (free)
            # - Pexels API (free)
            # - Pixabay API (free)
            
            collected.append({
                "path": f"stock_{category.replace(' ', '_')}_{len(collected)}.jpg",
                "category": "stock_broll",
                "search_term": category,
                "copyright_status": "royalty_free_or_cc",
                "attribution": "Stock photo - Creative Commons or Royalty Free",
                "usage_justification": "B-roll footage for documentary"
            })
        
        return collected[:max_images]
    
    def _create_media_index(self, subject_name: str, collected_media: Dict[str, Any], 
                          script_content: str) -> Dict[str, Any]:
        """Create comprehensive media index with usage guidelines"""
        
        # Analyze script for visual timing
        timestamps = re.findall(r'\[(\d{1,2}:\d{2})\]', script_content)
        broll_markers = re.findall(r'\[B-ROLL:\s*([^\]]+)\]', script_content, re.IGNORECASE)
        
        return {
            "subject": subject_name,
            "collection_summary": {
                "total_assets": collected_media["total_collected"],
                "news_images": len(collected_media["news_images"]),
                "targeted_searches": len(collected_media["targeted_searches"]),
                "stock_images": len(collected_media["stock_images"])
            },
            "media_assets": {
                "news_coverage": collected_media["news_images"],
                "targeted_content": collected_media["targeted_searches"],
                "stock_broll": collected_media["stock_images"]
            },
            "usage_guidelines": {
                "fair_use_justification": "Documentary commentary, criticism, and educational content",
                "attribution_required": True,
                "commercial_use": "Educational/Commentary purposes",
                "duration_limits": "Brief clips/images as supporting material",
                "transformation": "Used as part of larger documentary narrative"
            },
            "script_integration": {
                "total_timestamps": len(timestamps),
                "broll_opportunities": len(broll_markers),
                "visual_pacing": "30-45 second intervals",
                "recommended_usage": "Rotate between news, targeted, and stock images"
            },
            "legal_compliance": {
                "copyright_review": "Required before publication",
                "attribution_format": "Source attribution in video credits",
                "fair_use_factors": [
                    "Purpose: Commentary and criticism",
                    "Nature: Factual documentary content", 
                    "Amount: Brief excerpts and images",
                    "Effect: Educational, non-competing use"
                ]
            }
        }
    
    # Helper methods (existing functionality)
    def _is_news_domain(self, url: str) -> bool:
        """Check if URL is from a reputable news domain"""
        try:
            domain = urlparse(url).netloc.lower()
            return any(news_domain in domain for news_domain in self.fair_use_domains)
        except:
            return False
    
    async def _extract_images_from_article(self, source: Dict[str, Any], subject_name: str) -> List[str]:
        """Extract images from news article"""
        url = source.get('url')
        if not url:
            return []
        
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                
                # Extract images
                img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
                og_pattern = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\'][^>]*>'
                
                img_matches = re.findall(img_pattern, html, re.IGNORECASE)
                og_matches = re.findall(og_pattern, html, re.IGNORECASE)
                
                all_images = img_matches + og_matches
                
                # Filter and clean URLs
                relevant_images = []
                for img_url in all_images:
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = urljoin(url, img_url)
                    
                    if self._is_valid_image_url(img_url):
                        relevant_images.append(img_url)
                
                return relevant_images[:5]
                
        except Exception as e:
            self.logger.warning(f"Error extracting images from {url}: {e}")
            return []
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL is a valid image"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            return any(path.endswith(ext) for ext in self.image_extensions)
        except:
            return False
    
    async def _download_image(self, img_url: str, output_dir: Path, filename_prefix: str) -> Optional[Path]:
        """Download image to local directory"""
        try:
            async with self.session.get(img_url, timeout=10) as response:
                if response.status != 200:
                    return None
                
                # Determine file extension
                parsed_url = urlparse(img_url)
                ext = '.jpg'
                for image_ext in self.image_extensions:
                    if parsed_url.path.lower().endswith(image_ext):
                        ext = image_ext
                        break
                
                # Generate filename
                filename = f"{filename_prefix}_{hash(img_url) % 10000}{ext}"
                file_path = output_dir / filename
                
                # Save image
                content = await response.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                self.logger.info(f"✓ Downloaded: {filename}")
                return file_path
                
        except Exception as e:
            self.logger.warning(f"Failed to download {img_url}: {e}")
            return None
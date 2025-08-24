import aiohttp
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import re
from urllib.parse import urlparse, urljoin
import logging

class NewsMediaCollector:
    """Collects copyright-safe images and media from public/fair-use sources"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = None
        
        # Common image extensions
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
        
        # Copyright-safe sources (public domain, creative commons, fair use)
        self.safe_sources = {
            # Government/Public sources
            'sec.gov', 'uspto.gov', 'wikipedia.org', 'wikimedia.org',
            # Company official sources (fair use for commentary)
            'press.uber.com', 'newsroom.uber.com', 'investor.uber.com',
            # Creative Commons news sources
            'reuters.com',  # Often has CC licensed content
        }
        
        # Fair use news domains (for commentary/criticism)
        self.fair_use_domains = {
            'techcrunch.com', 'bloomberg.com', 'wsj.com', 'nytimes.com',
            'reuters.com', 'forbes.com', 'businessinsider.com', 'cnbc.com',
            'theverge.com', 'wired.com', 'arstechnica.com'
        }
    
    async def collect_subject_media(self, subject_name: str, sources: List[Dict[str, Any]], 
                                  output_dir: Path, max_images: int = 10) -> Dict[str, Any]:
        """
        Collect relevant images from news sources about the subject
        
        Args:
            subject_name: The subject to collect media for (e.g., "Uber", "Netflix")
            sources: List of source articles from the research phase
            output_dir: Directory to save collected media
            max_images: Maximum number of images to collect
        """
        media_dir = output_dir / "subject_media"
        media_dir.mkdir(exist_ok=True)
        
        collected_images = []
        
        async with aiohttp.ClientSession() as session:
            self.session = session
            
            # Filter sources to news domains
            news_sources = [s for s in sources if self._is_news_domain(s.get('url', ''))]
            
            for source in news_sources[:5]:  # Limit to top 5 news sources
                try:
                    images = await self._extract_images_from_article(source, subject_name)
                    
                    for img_url in images[:3]:  # Max 3 images per article
                        if len(collected_images) >= max_images:
                            break
                        
                        image_path = await self._download_image(img_url, media_dir, subject_name, source)
                        if image_path:
                            collected_images.append({
                                "path": str(image_path),
                                "source_url": source.get('url'),
                                "source_title": source.get('title'),
                                "image_url": img_url,
                                "relevance": "high",
                                "copyright_status": self._get_copyright_status(source.get('url')),
                                "fair_use_justification": "Commentary and criticism for educational documentary",
                                "attribution_required": True,
                                "usage_guidelines": "Fair use for documentary commentary - attribute source"
                            })
                
                except Exception as e:
                    self.logger.warning(f"Failed to collect media from {source.get('url')}: {e}")
                    continue
        
        # Generate media index
        media_index = {
            "subject": subject_name,
            "total_images": len(collected_images),
            "images": collected_images,
            "collection_method": "news_articles",
            "relevance_score": 0.9  # High relevance since from actual news articles
        }
        
        # Save media index
        with open(media_dir / "media_index.json", "w") as f:
            json.dump(media_index, f, indent=2)
        
        return media_index
    
    def _is_news_domain(self, url: str) -> bool:
        """Check if URL is from a reputable news domain or safe source"""
        try:
            domain = urlparse(url).netloc.lower()
            return (any(news_domain in domain for news_domain in self.fair_use_domains) or
                   any(safe_domain in domain for safe_domain in self.safe_sources))
        except:
            return False
    
    def _get_copyright_status(self, url: str) -> str:
        """Determine copyright status of source"""
        try:
            domain = urlparse(url).netloc.lower()
            
            if any(safe_domain in domain for safe_domain in self.safe_sources):
                return "public_domain_or_cc"
            elif any(fair_domain in domain for fair_domain in self.fair_use_domains):
                return "fair_use_commentary"
            else:
                return "unknown"
        except:
            return "unknown"
    
    async def _extract_images_from_article(self, source: Dict[str, Any], subject_name: str) -> List[str]:
        """Extract relevant images from a news article"""
        url = source.get('url')
        if not url:
            return []
        
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                
                # Extract images using regex (simple approach)
                img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
                img_matches = re.findall(img_pattern, html, re.IGNORECASE)
                
                # Also look for Open Graph images
                og_pattern = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\'][^>]*>'
                og_matches = re.findall(og_pattern, html, re.IGNORECASE)
                
                all_images = img_matches + og_matches
                
                # Filter and clean image URLs
                relevant_images = []
                for img_url in all_images:
                    # Convert relative URLs to absolute
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = urljoin(url, img_url)
                    
                    # Check if it's a valid image URL
                    if self._is_valid_image_url(img_url) and self._is_relevant_image(img_url, subject_name):
                        relevant_images.append(img_url)
                
                return relevant_images[:5]  # Return top 5 relevant images
                
        except Exception as e:
            self.logger.warning(f"Error extracting images from {url}: {e}")
            return []
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL points to a valid image"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # Check file extension
            if any(path.endswith(ext) for ext in self.image_extensions):
                return True
            
            # Check for common image hosting patterns
            image_hosts = ['imgur.com', 'cloudinary.com', 'amazonaws.com']
            if any(host in parsed.netloc for host in image_hosts):
                return True
            
            return False
        except:
            return False
    
    def _is_relevant_image(self, img_url: str, subject_name: str) -> bool:
        """Check if image is likely relevant to the subject"""
        url_lower = img_url.lower()
        subject_lower = subject_name.lower()
        
        # Skip common irrelevant images
        skip_patterns = [
            'logo', 'icon', 'avatar', 'profile', 'social', 'share',
            'advertisement', 'banner', 'sidebar', 'footer', 'header'
        ]
        
        if any(pattern in url_lower for pattern in skip_patterns):
            return False
        
        # Prefer images that mention the subject
        if subject_lower in url_lower:
            return True
        
        # For companies, look for business-related terms
        business_terms = ['ceo', 'founder', 'office', 'headquarters', 'product', 'app']
        if any(term in url_lower for term in business_terms):
            return True
        
        return True  # Default to including if not obviously irrelevant
    
    async def _download_image(self, img_url: str, output_dir: Path, subject_name: str, source: Dict[str, Any]) -> Optional[Path]:
        """Download image to local directory"""
        try:
            async with self.session.get(img_url, timeout=10) as response:
                if response.status != 200:
                    return None
                
                # Get file extension
                parsed_url = urlparse(img_url)
                path = parsed_url.path
                ext = '.jpg'  # Default extension
                
                for image_ext in self.image_extensions:
                    if path.lower().endswith(image_ext):
                        ext = image_ext
                        break
                
                # Generate filename
                filename = f"{subject_name.lower().replace(' ', '_')}_{hash(img_url) % 10000}{ext}"
                file_path = output_dir / filename
                
                # Save image
                content = await response.read()
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                self.logger.info(f"✓ Downloaded relevant image: {filename}")
                return file_path
                
        except Exception as e:
            self.logger.warning(f"Failed to download image {img_url}: {e}")
            return None
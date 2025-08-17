import aiohttp
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import hashlib
from urllib.parse import urlparse
from src.config import config

class MediaCollector:
    """Base class for media collection from various APIs"""
    
    def __init__(self, session: aiohttp.ClientSession, api_key: str = ""):
        self.api_key = api_key
        self.session = session
    
    async def collect_media(self, keywords: List[str], media_type: str = "photo", 
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Collect media from API based on keywords"""
        raise NotImplementedError
    
    async def download_media(self, media_item: Dict[str, Any], 
                           output_dir: Path) -> Optional[str]:
        """Download media file and return local path"""
        try:
            url = media_item.get("download_url") or media_item.get("url")
            if not url:
                return None
            
            # Generate filename
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            extension = self._get_file_extension(url)
            filename = f"{media_item.get('id', url_hash)}{extension}"
            filepath = output_dir / filename
            
            # Download file
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    # Save license info
                    license_info = {
                        "source_url": media_item.get("source_url", url),
                        "license": media_item.get("license", {}),
                        "attribution": media_item.get("attribution", ""),
                        "downloaded_at": media_item.get("downloaded_at"),
                        "safe_for_commercial_use": media_item.get("safe_for_commercial_use", False)
                    }
                    
                    license_file = filepath.with_suffix('.license.json')
                    with open(license_file, 'w') as f:
                        json.dump(license_info, f, indent=2)
                    
                    return str(filepath)
        
        except Exception as e:
            print(f"Download error for {url}: {e}")
        
        return None
    
    def _get_file_extension(self, url: str) -> str:
        """Extract file extension from URL"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        if path.endswith(('.jpg', '.jpeg')):
            return '.jpg'
        elif path.endswith('.png'):
            return '.png'
        elif path.endswith('.gif'):
            return '.gif'
        elif path.endswith('.mp4'):
            return '.mp4'
        else:
            return '.jpg'  # Default

class UnsplashCollector(MediaCollector):
    """Collect photos from Unsplash API"""
    
    def __init__(self, session: aiohttp.ClientSession):
        api_key = config.get("media", {}).get("unsplash_api_key", "")
        super().__init__(session, api_key)
        self.base_url = "https://api.unsplash.com"
    
    async def collect_media(self, keywords: List[str], media_type: str = "photo", 
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Search Unsplash for photos"""
        if not self.api_key:
            return []
        
        media_items = []
        
        for keyword in keywords[:3]:  # Limit keyword searches
            try:
                url = f"{self.base_url}/search/photos"
                headers = {"Authorization": f"Client-ID {self.api_key}"}
                params = {
                    "query": keyword,
                    "per_page": min(limit, 30),
                    "orientation": "landscape"
                }
                
                async with self.session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for photo in data.get("results", []):
                            media_items.append({
                                "id": photo.get("id"),
                                "url": photo.get("urls", {}).get("regular"),
                                "download_url": photo.get("urls", {}).get("full"),
                                "source_url": photo.get("links", {}).get("html"),
                                "width": photo.get("width"),
                                "height": photo.get("height"),
                                "description": photo.get("description") or photo.get("alt_description"),
                                "keywords": [keyword],
                                "license": {
                                    "type": "Unsplash License",
                                    "url": "https://unsplash.com/license",
                                    "commercial_use": True
                                },
                                "attribution": f"Photo by {photo.get('user', {}).get('name', 'Unknown')} on Unsplash",
                                "safe_for_commercial_use": True,
                                "source": "unsplash"
                            })
                
            except Exception as e:
                print(f"Unsplash search error for '{keyword}': {e}")
        
        return media_items[:limit]

class PexelsCollector(MediaCollector):
    """Collect photos and videos from Pexels API"""
    
    def __init__(self, session: aiohttp.ClientSession):
        api_key = config.get("media", {}).get("pexels_api_key", "")
        super().__init__(session, api_key)
        self.base_url = "https://api.pexels.com/v1"
    
    async def collect_media(self, keywords: List[str], media_type: str = "photo", 
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Search Pexels for photos or videos"""
        if not self.api_key:
            return []
        
        media_items = []
        endpoint = "search" if media_type == "photo" else "videos/search"
        
        for keyword in keywords[:3]:
            try:
                url = f"{self.base_url}/{endpoint}"
                headers = {"Authorization": self.api_key}
                params = {
                    "query": keyword,
                    "per_page": min(limit, 80),
                    "orientation": "landscape"
                }
                
                async with self.session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        items = data.get("photos" if media_type == "photo" else "videos", [])
                        for item in items:
                            if media_type == "photo":
                                media_items.append({
                                    "id": item.get("id"),
                                    "url": item.get("src", {}).get("large"),
                                    "download_url": item.get("src", {}).get("original"),
                                    "source_url": item.get("url"),
                                    "width": item.get("width"),
                                    "height": item.get("height"),
                                    "description": item.get("alt"),
                                    "keywords": [keyword],
                                    "license": {
                                        "type": "Pexels License",
                                        "url": "https://www.pexels.com/license/",
                                        "commercial_use": True
                                    },
                                    "attribution": f"Photo by {item.get('photographer', 'Unknown')} from Pexels",
                                    "safe_for_commercial_use": True,
                                    "source": "pexels"
                                })
                            else:  # video
                                video_files = item.get("video_files", [])
                                if video_files:
                                    best_quality = max(video_files, key=lambda x: x.get("width", 0))
                                    media_items.append({
                                        "id": item.get("id"),
                                        "url": best_quality.get("link"),
                                        "download_url": best_quality.get("link"),
                                        "source_url": item.get("url"),
                                        "width": best_quality.get("width"),
                                        "height": best_quality.get("height"),
                                        "duration": item.get("duration"),
                                        "description": f"Video about {keyword}",
                                        "keywords": [keyword],
                                        "license": {
                                            "type": "Pexels License",
                                            "url": "https://www.pexels.com/license/",
                                            "commercial_use": True
                                        },
                                        "attribution": f"Video by {item.get('user', {}).get('name', 'Unknown')} from Pexels",
                                        "safe_for_commercial_use": True,
                                        "source": "pexels"
                                    })
                
            except Exception as e:
                print(f"Pexels search error for '{keyword}': {e}")
        
        return media_items[:limit]

class WikimediaCollector(MediaCollector):
    """Collect images from Wikimedia Commons"""
    
    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        self.base_url = "https://commons.wikimedia.org/w/api.php"
    
    async def collect_media(self, keywords: List[str], media_type: str = "photo", 
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Search Wikimedia Commons for images"""
        media_items = []
        
        for keyword in keywords[:2]:  # Limit searches
            try:
                params = {
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": f"filetype:bitmap {keyword}",
                    "srnamespace": 6,  # File namespace
                    "srlimit": min(limit, 20)
                }
                
                async with self.session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for item in data.get("query", {}).get("search", []):
                            title = item.get("title", "")
                            if title.startswith("File:"):
                                # Get image info
                                image_info = await self._get_image_info(title)
                                if image_info:
                                    media_items.append(image_info)
                
            except Exception as e:
                print(f"Wikimedia search error for '{keyword}': {e}")
        
        return media_items[:limit]
    
    async def _get_image_info(self, title: str) -> Optional[Dict[str, Any]]:
        """Get detailed info for a Wikimedia image"""
        try:
            params = {
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata"
            }
            
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    pages = data.get("query", {}).get("pages", {})
                    
                    for page in pages.values():
                        imageinfo = page.get("imageinfo", [])
                        if imageinfo:
                            info = imageinfo[0]
                            extmetadata = info.get("extmetadata", {})
                            
                            return {
                                "id": title.replace("File:", "").replace(" ", "_"),
                                "url": info.get("url"),
                                "download_url": info.get("url"),
                                "source_url": f"https://commons.wikimedia.org/wiki/{title}",
                                "width": info.get("width"),
                                "height": info.get("height"),
                                "description": extmetadata.get("ImageDescription", {}).get("value", ""),
                                "keywords": [title],
                                "license": {
                                    "type": extmetadata.get("LicenseShortName", {}).get("value", "Unknown"),
                                    "url": extmetadata.get("LicenseUrl", {}).get("value", ""),
                                    "commercial_use": True  # Most Wikimedia content is CC licensed
                                },
                                "attribution": extmetadata.get("Attribution", {}).get("value", "Wikimedia Commons"),
                                "safe_for_commercial_use": True,
                                "source": "wikimedia"
                            }
        
        except Exception as e:
            print(f"Error getting image info for {title}: {e}")
        
        return None
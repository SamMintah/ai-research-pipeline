import aiohttp
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import re
from urllib.parse import quote, urlparse
import logging
from src.config import settings

class GoogleImageSearcher:
    """Search for copyright-safe images using Google Custom Search API"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = settings.google_api_key if hasattr(settings, 'google_api_key') else None
        self.search_engine_id = settings.google_search_engine_id if hasattr(settings, 'google_search_engine_id') else None
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        
        # Usage rights filters for copyright-safe images
        self.usage_rights = {
            'free_to_use': 'cc_publicdomain,cc_attribute,cc_sharealike,cc_noncommercial,cc_nonderived',
            'fair_use': 'cc_publicdomain,cc_attribute,cc_sharealike'
        }
    
    async def search_subject_images(self, subject_name: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for images related to the subject with usage rights filtering"""
        
        if not self.api_key or not self.search_engine_id:
            self.logger.info("Google API credentials not configured, using fallback method")
            return await self._fallback_image_search(subject_name, max_results)
        
        search_queries = self._generate_subject_queries(subject_name)
        all_results = []
        
        async with aiohttp.ClientSession() as session:
            for query in search_queries:
                if len(all_results) >= max_results:
                    break
                
                results = await self._search_images_with_rights(session, query, 5)
                all_results.extend(results)
        
        return all_results[:max_results]
    
    def _generate_subject_queries(self, subject_name: str) -> List[str]:
        """Generate targeted search queries for the subject"""
        base_queries = [
            f"{subject_name} CEO founder official",
            f"{subject_name} headquarters office building",
            f"{subject_name} logo official branding",
            f"{subject_name} products services"
        ]
        
        # Subject-specific queries
        subject_lower = subject_name.lower()
        
        if "meta" in subject_lower or "facebook" in subject_lower:
            specific_queries = [
                "Mark Zuckerberg Meta CEO official photo",
                "Facebook Meta headquarters Menlo Park campus",
                "Meta logo Facebook Instagram WhatsApp",
                "Meta Quest VR headset product",
                "Facebook data center technology"
            ]
        elif "uber" in subject_lower:
            specific_queries = [
                "Travis Kalanick Uber founder CEO",
                "Uber headquarters San Francisco office",
                "Uber app logo rideshare",
                "Uber cars drivers transportation"
            ]
        elif "apple" in subject_lower:
            specific_queries = [
                "Steve Jobs Apple founder CEO official",
                "Apple Park headquarters Cupertino campus",
                "iPhone iPad Mac Apple products",
                "Apple Store retail locations"
            ]
        else:
            specific_queries = [
                f"{subject_name} executive team leadership",
                f"{subject_name} corporate office building",
                f"{subject_name} business operations"
            ]
        
        return base_queries + specific_queries
    
    async def _search_images_with_rights(self, session: aiohttp.ClientSession, 
                                       query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """Search for images with usage rights filtering"""
        
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'searchType': 'image',
            'num': min(num_results, 10),  # Max 10 per request
            'rights': self.usage_rights['free_to_use'],
            'safe': 'active',
            'imgSize': 'medium',
            'imgType': 'photo'
        }
        
        try:
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._process_search_results(data, query)
                elif response.status == 403:
                    error_data = await response.json()
                    self.logger.warning(f"Google API permission error for query '{query}': {error_data.get('error', {}).get('message', 'Permission denied')}")
                    return []
                elif response.status == 429:
                    self.logger.warning(f"Google API quota exceeded for query '{query}' - using fallback")
                    return []
                else:
                    error_text = await response.text()
                    self.logger.warning(f"Google API error {response.status} for query '{query}': {error_text}")
                    return []
        
        except Exception as e:
            self.logger.error(f"Error searching for '{query}': {e}")
            return []
    
    def _process_search_results(self, data: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        """Process Google search results into standardized format"""
        results = []
        
        items = data.get('items', [])
        for item in items:
            try:
                result = {
                    'image_url': item.get('link'),
                    'title': item.get('title', ''),
                    'source_url': item.get('image', {}).get('contextLink', ''),
                    'source_domain': self._extract_domain(item.get('image', {}).get('contextLink', '')),
                    'thumbnail_url': item.get('image', {}).get('thumbnailLink', ''),
                    'width': item.get('image', {}).get('width', 0),
                    'height': item.get('image', {}).get('height', 0),
                    'file_format': item.get('fileFormat', ''),
                    'search_query': query,
                    'copyright_status': 'usage_rights_filtered',
                    'usage_justification': 'Creative Commons or usage rights verified',
                    'attribution_required': True
                }
                
                # Additional metadata
                if 'pagemap' in item:
                    pagemap = item['pagemap']
                    if 'cse_image' in pagemap:
                        cse_image = pagemap['cse_image'][0]
                        result['alt_text'] = cse_image.get('alt', '')
                
                results.append(result)
                
            except Exception as e:
                self.logger.warning(f"Error processing search result: {e}")
                continue
        
        return results
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            return urlparse(url).netloc
        except:
            return ""
    
    async def _fallback_image_search(self, subject_name: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback method when Google API is not available"""
        self.logger.info(f"Using fallback image search for {subject_name}")
        
        # Return placeholder results that indicate where real images would be found
        fallback_results = []
        
        search_terms = [
            f"{subject_name} CEO founder",
            f"{subject_name} headquarters office",
            f"{subject_name} logo branding",
            f"{subject_name} products"
        ]
        
        for i, term in enumerate(search_terms[:max_results]):
            fallback_results.append({
                'image_url': f'https://placeholder.com/600x400?text={quote(term)}',
                'title': f'{term} - Stock Photo',
                'source_url': 'https://placeholder.com',
                'source_domain': 'placeholder.com',
                'search_query': term,
                'copyright_status': 'placeholder',
                'usage_justification': 'Placeholder - replace with actual licensed images',
                'attribution_required': False,
                'note': 'This is a placeholder. In production, use Google Custom Search API with usage rights filtering.'
            })
        
        return fallback_results

class WikimediaSearcher:
    """Search Wikimedia Commons for public domain images"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://commons.wikimedia.org/w/api.php"
    
    async def search_commons_images(self, subject_name: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search Wikimedia Commons for public domain images"""
        
        search_queries = [
            f"{subject_name} CEO",
            f"{subject_name} headquarters",
            f"{subject_name} logo",
            f"{subject_name} building"
        ]
        
        all_results = []
        
        async with aiohttp.ClientSession() as session:
            for query in search_queries:
                if len(all_results) >= max_results:
                    break
                
                results = await self._search_wikimedia(session, query, 3)
                all_results.extend(results)
        
        return all_results[:max_results]
    
    async def _search_wikimedia(self, session: aiohttp.ClientSession, 
                              query: str, num_results: int) -> List[Dict[str, Any]]:
        """Search Wikimedia Commons API"""
        
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': f'filetype:bitmap {query}',
            'srnamespace': 6,  # File namespace
            'srlimit': num_results
        }
        
        try:
            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._process_wikimedia_results(data, query)
                else:
                    return []
        
        except Exception as e:
            self.logger.error(f"Error searching Wikimedia for '{query}': {e}")
            return []
    
    def _process_wikimedia_results(self, data: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        """Process Wikimedia search results"""
        results = []
        
        search_results = data.get('query', {}).get('search', [])
        
        for item in search_results:
            try:
                title = item.get('title', '')
                if title.startswith('File:'):
                    # Construct Wikimedia Commons URLs
                    filename = title.replace('File:', '').replace(' ', '_')
                    image_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
                    page_url = f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}"
                    
                    result = {
                        'image_url': image_url,
                        'title': title,
                        'source_url': page_url,
                        'source_domain': 'commons.wikimedia.org',
                        'search_query': query,
                        'copyright_status': 'public_domain_or_cc',
                        'usage_justification': 'Wikimedia Commons - Public domain or Creative Commons',
                        'attribution_required': True,
                        'attribution_text': f"Source: Wikimedia Commons - {title}"
                    }
                    
                    results.append(result)
            
            except Exception as e:
                self.logger.warning(f"Error processing Wikimedia result: {e}")
                continue
        
        return results
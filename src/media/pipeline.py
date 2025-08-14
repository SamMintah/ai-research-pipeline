import asyncio
from pathlib import Path
from typing import Dict, Any, List
import json
from datetime import datetime
from src.media.collectors import UnsplashCollector, PexelsCollector, WikimediaCollector

class MediaPipeline:
    """Pipeline for collecting and organizing media assets"""
    
    def __init__(self):
        self.collectors = {
            "unsplash": UnsplashCollector(),
            "pexels": PexelsCollector(), 
            "wikimedia": WikimediaCollector()
        }
    
    async def collect_media_for_script(self, script_data: Dict[str, Any], 
                                     output_dir: Path) -> Dict[str, Any]:
        """Collect media assets based on script content and B-roll suggestions"""
        
        # Create assets directory
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        
        # Extract keywords from B-roll suggestions
        broll_suggestions = script_data.get("broll_suggestions", [])
        keywords = self._extract_keywords_from_broll(broll_suggestions)
        
        # Add company-specific keywords
        company_name = script_data.get("company_name", "")
        if company_name:
            keywords.extend([
                company_name,
                f"{company_name} logo",
                f"{company_name} office",
                f"{company_name} headquarters"
            ])
        
        # Collect from multiple sources
        all_media = []
        
        for source_name, collector in self.collectors.items():
            try:
                print(f"Collecting from {source_name}...")
                
                # Collect photos
                photos = await collector.collect_media(
                    keywords=keywords[:5], 
                    media_type="photo", 
                    limit=15
                )
                all_media.extend(photos)
                
                # Collect videos if supported
                if source_name == "pexels":
                    videos = await collector.collect_media(
                        keywords=keywords[:3],
                        media_type="video",
                        limit=5
                    )
                    all_media.extend(videos)
                
            except Exception as e:
                print(f"Error collecting from {source_name}: {e}")
        
        # Download media files
        downloaded_media = []
        download_tasks = []
        
        for media_item in all_media[:30]:  # Limit downloads
            task = self._download_with_metadata(media_item, assets_dir)
            download_tasks.append(task)
        
        # Execute downloads concurrently
        download_results = await asyncio.gather(*download_tasks, return_exceptions=True)
        
        for result in download_results:
            if isinstance(result, dict) and result.get("success"):
                downloaded_media.append(result)
        
        # Create media index mapping to script sections
        media_index = self._create_media_index(downloaded_media, broll_suggestions)
        
        # Save media index
        index_file = assets_dir / "media_index.json"
        with open(index_file, 'w') as f:
            json.dump(media_index, f, indent=2)
        
        # Close collectors
        for collector in self.collectors.values():
            await collector.close()
        
        return {
            "total_collected": len(all_media),
            "successfully_downloaded": len(downloaded_media),
            "assets_directory": str(assets_dir),
            "media_index": media_index,
            "keywords_used": keywords
        }    
  
  def _extract_keywords_from_broll(self, broll_suggestions: List[Dict[str, Any]]) -> List[str]:
        """Extract search keywords from B-roll suggestions"""
        keywords = []
        
        for suggestion in broll_suggestions:
            # Add keywords from suggestion
            suggestion_keywords = suggestion.get("keywords", [])
            keywords.extend(suggestion_keywords)
            
            # Add description as keyword
            description = suggestion.get("description", "")
            if description:
                keywords.append(description)
        
        # Add generic business keywords
        keywords.extend([
            "business meeting",
            "office building", 
            "corporate",
            "technology",
            "startup",
            "entrepreneur",
            "success",
            "growth",
            "innovation"
        ])
        
        # Remove duplicates and return
        return list(set(keywords))
    
    async def _download_with_metadata(self, media_item: Dict[str, Any], 
                                    assets_dir: Path) -> Dict[str, Any]:
        """Download media item and return metadata"""
        try:
            # Determine collector
            source = media_item.get("source", "unknown")
            collector = self.collectors.get(source)
            
            if not collector:
                return {"success": False, "error": "Unknown source"}
            
            # Download file
            local_path = await collector.download_media(media_item, assets_dir)
            
            if local_path:
                return {
                    "success": True,
                    "local_path": local_path,
                    "filename": Path(local_path).name,
                    "source": source,
                    "original_url": media_item.get("url"),
                    "description": media_item.get("description"),
                    "keywords": media_item.get("keywords", []),
                    "license": media_item.get("license", {}),
                    "attribution": media_item.get("attribution", ""),
                    "width": media_item.get("width"),
                    "height": media_item.get("height"),
                    "safe_for_commercial_use": media_item.get("safe_for_commercial_use", False)
                }
            else:
                return {"success": False, "error": "Download failed"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _create_media_index(self, downloaded_media: List[Dict[str, Any]], 
                          broll_suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create index mapping media to script sections"""
        
        media_index = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_assets": len(downloaded_media),
            "sections": [],
            "assets": downloaded_media
        }
        
        # Map media to B-roll suggestions
        for suggestion in broll_suggestions:
            timestamp = suggestion.get("timestamp", "00:00")
            description = suggestion.get("description", "")
            keywords = suggestion.get("keywords", [])
            
            # Find matching media
            matching_media = []
            for media in downloaded_media:
                media_keywords = media.get("keywords", [])
                media_desc = media.get("description", "").lower()
                
                # Check for keyword matches
                if any(keyword.lower() in media_desc or 
                      any(keyword.lower() in mk.lower() for mk in media_keywords) 
                      for keyword in keywords):
                    matching_media.append({
                        "filename": media.get("filename"),
                        "local_path": media.get("local_path"),
                        "description": media.get("description"),
                        "attribution": media.get("attribution"),
                        "match_score": self._calculate_match_score(keywords, media)
                    })
            
            # Sort by match score
            matching_media.sort(key=lambda x: x.get("match_score", 0), reverse=True)
            
            media_index["sections"].append({
                "timestamp": timestamp,
                "description": description,
                "suggested_duration": suggestion.get("duration", 5),
                "visual_type": suggestion.get("visual_type", "stock_footage"),
                "mood": suggestion.get("mood", "neutral"),
                "matching_assets": matching_media[:3]  # Top 3 matches
            })
        
        return media_index
    
    def _calculate_match_score(self, target_keywords: List[str], 
                             media_item: Dict[str, Any]) -> float:
        """Calculate how well media matches target keywords"""
        media_keywords = media_item.get("keywords", [])
        media_desc = media_item.get("description", "").lower()
        
        score = 0.0
        
        for keyword in target_keywords:
            keyword_lower = keyword.lower()
            
            # Exact keyword match
            if any(keyword_lower == mk.lower() for mk in media_keywords):
                score += 1.0
            
            # Partial keyword match
            elif any(keyword_lower in mk.lower() for mk in media_keywords):
                score += 0.5
            
            # Description match
            elif keyword_lower in media_desc:
                score += 0.3
        
        return score
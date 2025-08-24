import aiohttp
import asyncio
from pathlib import Path
from typing import Optional
import logging
from src.config import settings

class ElevenLabsProvider:
    """ElevenLabs TTS provider for high-quality voiceover generation"""
    
    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.logger = logging.getLogger(__name__)
        
        # Voice settings optimized for Aaditya K - Soothing Midnight Storyteller
        self.voice_settings = {
            "stability": 0.80,  # High stability for smooth documentary narration
            "similarity_boost": 0.90,  # Very high similarity to maintain voice consistency
            "style": 0.70,  # Enhanced style for engaging storytelling
            "use_speaker_boost": True
        }
    
    async def generate_speech(self, text: str, output_file: Path, voice_id: str = "qWdiyiWdNPlPyVCOLW0h") -> bool:
        """
        Generate speech using ElevenLabs API
        
        Args:
            text: Text to convert to speech
            output_file: Path to save the audio file
            voice_id: ElevenLabs voice ID (default: qWdiyiWdNPlPyVCOLW0h - Aaditya K Soothing Midnight Storyteller)
                     Alternative: "jxfeh5OWvJvK2Sr33eAI" (SAMUEL-research - previous custom voice)
                     Alternative: "29vD33N1CtxCmqQRPOHJ" (Drew - engaging male voice)
                     Alternative: "pNInz6obpgDQGcFmaJgB" (Adam - authoritative male)
        """
        if not self.api_key:
            self.logger.error("ElevenLabs API key not found")
            return False
        
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",  # High quality model
            "voice_settings": self.voice_settings
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        audio_content = await response.read()
                        
                        # Save as MP3 first, then convert to WAV if needed
                        mp3_file = output_file.with_suffix('.mp3')
                        with open(mp3_file, 'wb') as f:
                            f.write(audio_content)
                        
                        # Convert to WAV for compatibility
                        await self._convert_to_wav(mp3_file, output_file)
                        
                        self.logger.info(f"✓ Generated high-quality voiceover: {output_file.name}")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"ElevenLabs API error {response.status}: {error_text}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Error generating speech with ElevenLabs: {e}")
            return False
    
    async def _convert_to_wav(self, mp3_file: Path, wav_file: Path):
        """Convert MP3 to WAV using ffmpeg if available, otherwise keep as MP3"""
        try:
            import subprocess
            subprocess.run([
                'ffmpeg', '-i', str(mp3_file), '-acodec', 'pcm_s16le', 
                '-ar', '44100', str(wav_file), '-y'
            ], check=True, capture_output=True)
            
            # Remove MP3 file after successful conversion
            mp3_file.unlink()
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            # If ffmpeg not available, rename MP3 to WAV (most players will handle it)
            mp3_file.rename(wav_file)
            self.logger.warning("ffmpeg not found, saved as MP3 with WAV extension")
    
    def get_available_voices(self):
        """Return recommended voice IDs for different styles"""
        return {
            "aaditya_storyteller": "qWdiyiWdNPlPyVCOLW0h",  # Aaditya K - Soothing Midnight Storyteller (NEW DEFAULT)
            "samuel_research": "jxfeh5OWvJvK2Sr33eAI",  # SAMUEL-research - previous custom voice
            "professional_male": "29vD33N1CtxCmqQRPOHJ",  # Drew - engaging male
            "authoritative_male": "pNInz6obpgDQGcFmaJgB",  # Adam - deep, authoritative
            "documentary_male": "VR6AewLTigWG4xSOukaG",  # Josh - clear, professional
            "energetic_male": "TxGEqnHWrfWFTfGW9XjX",  # Josh (alternative)
            "professional_female": "21m00Tcm4TlvDq8ikWAM",  # Rachel - clear, professional
            "warm_female": "AZnzlk1XvdvUeBnXmlld"  # Domi - warm, engaging
        }
import asyncio
import re
import wave
import csv
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.agents.base import BaseAgent
from src.llm.base_provider import LLMProvider
from src.tts.elevenlabs_provider import ElevenLabsProvider

class VoiceoverAgent(BaseAgent):
    """Agent for generating voiceover and timeline data from a script."""

    def __init__(self, llm_provider: LLMProvider, voice_style: str = "aaditya_storyteller"):
        super().__init__(llm_provider)
        self.silence_padding_s = 1.0  # 1 second of silence between clips
        self.max_text_length = 500  # Reduced to stay within ElevenLabs quota limits
        
        # Initialize ElevenLabs provider
        self.tts_provider = ElevenLabsProvider()
        self.voice_style = voice_style
        # Use the new Aaditya K voice ID for documentary storytelling
        self.voice_id = "qWdiyiWdNPlPyVCOLW0h"  # Aaditya K - Soothing Midnight Storyteller

    # Removed unused _initialize_tts_models method since we're using ElevenLabs

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrates the voiceover and timeline generation process."""
        script_content = input_data.get("script_content")
        output_dir = input_data.get("output_dir")
        broll_suggestions = input_data.get("broll_suggestions", [])

        if not script_content:
            return {"error": "Script content is required"}
        
        if not output_dir:
            return {"error": "Output directory is required"}

        # Validate output directory
        try:
            output_path = Path(output_dir)
            voiceover_dir = output_path / "voiceover"
            voiceover_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"error": f"Could not create output directory: {e}"}

        # Parse the script into sections
        sections = self._parse_script_into_sections(script_content)
        if not sections:
            return {"error": "Could not parse script into sections. Check script format."}

        # Generate TTS audio for each section
        self.logger.info(f"Generating voiceover audio for {len(sections)} script sections...")
        audio_metadata = []
        
        for section_name, text in sections.items():
            output_file = voiceover_dir / f"{section_name}.wav"
            result = await self._create_and_measure_audio(text, output_file)
            if result:
                audio_metadata.append(result)
            else:
                self.logger.warning(f"Failed to generate audio for section: {section_name}")

        if not audio_metadata:
            return {"error": "No audio files were generated successfully"}

        # Generate the timeline CSV for DaVinci Resolve
        self.logger.info("Generating timeline CSV...")
        try:
            timeline_csv_path = self._generate_timeline_csv(
                audio_metadata, broll_suggestions, output_path
            )
        except Exception as e:
            return {"error": f"Failed to generate timeline CSV: {e}"}

        total_duration = sum(audio["duration"] for audio in audio_metadata)
        
        return {
            "voiceover_directory": str(voiceover_dir),
            "timeline_csv_path": str(timeline_csv_path),
            "audio_files_generated": len(audio_metadata),
            "total_duration_seconds": round(total_duration, 2),
            "sections_processed": len(sections),
            "success": True
        }

    def _parse_script_into_sections(self, script_content: str) -> Dict[str, str]:
        """Parses a markdown script into a dictionary of {section_name: text}."""
        if not script_content or not script_content.strip():
            self.logger.error("Empty script content provided")
            return {}

        try:
            # More robust regex to find ## Headings and their content
            # This handles both ## and # headers and captures everything until the next header
            pattern = r'^#{1,2}\s+(.*?)\n(.*?)(?=^#{1,2}\s+|\Z)'
            matches = re.findall(pattern, script_content, re.MULTILINE | re.DOTALL)
            
            if not matches:
                # Fallback: treat entire script as one section if no headers found
                self.logger.warning("No section headers found, treating entire script as one section")
                return {"01_full_script": self._clean_text_for_tts(script_content)}
            
            sections = {}
            for i, (title, content) in enumerate(matches):
                # Sanitize title for filename (more robust)
                clean_title = re.sub(r'[^\w\s-]', '', title.strip())
                clean_title = re.sub(r'\s+', '_', clean_title.lower())
                clean_title = clean_title[:50]  # Limit length
                
                if not clean_title:
                    clean_title = f"section_{i+1}"
                
                filename = f"{i+1:02d}_{clean_title}"
                
                # Clean up content for TTS
                clean_content = self._clean_text_for_tts(content)
                
                if clean_content.strip():  # Only add non-empty sections
                    sections[filename] = clean_content
                else:
                    self.logger.warning(f"Empty content for section: {title}")
            
            self.logger.info(f"Parsed {len(sections)} sections from script")
            return sections
            
        except Exception as e:
            self.logger.error(f"Error parsing script into sections: {e}")
            return {}

    def _clean_text_for_tts(self, text: str) -> str:
        """Clean text for TTS processing"""
        if not text:
            return ""
        
        # Remove timestamps like [00:30], [MM:SS]
        text = re.sub(r'\[\d{1,2}:\d{2}\]', '', text)
        
        # Remove B-roll markers like [B-ROLL: description]
        text = re.sub(r'\[B-ROLL:.*?\]', '', text, flags=re.IGNORECASE)
        
        # Remove reference markers like [ref:1]
        text = re.sub(r'\[ref:\d+\]', '', text)
        
        # Remove other markdown markers
        text = re.sub(r'\[.*?\]', '', text)  # Any remaining [content]
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold markdown
        text = re.sub(r'\*(.*?)\*', r'\1', text)  # Italic markdown
        text = re.sub(r'`(.*?)`', r'\1', text)  # Code markdown
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    def _split_long_text(self, text: str) -> List[str]:
        """Split long text into chunks suitable for TTS"""
        if len(text) <= self.max_text_length:
            return [text]
        
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk + " " + sentence) <= self.max_text_length:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    async def _create_and_measure_audio(self, text: str, output_file: Path) -> Optional[Dict[str, Any]]:
        """Uses ElevenLabs to create high-quality audio file and measures its duration."""
        if not text or not text.strip():
            self.logger.warning(f"Empty text provided for {output_file.name}")
            return None
        
        try:
            # Clean and prepare text for TTS
            clean_text = self._clean_text_for_tts(text)
            
            # Generate speech using ElevenLabs
            success = await self.tts_provider.generate_speech(
                text=clean_text,
                output_file=output_file,
                voice_id=self.voice_id
            )
            
            if not success:
                self.logger.error(f"Failed to generate audio for {output_file.name}")
                return None
            
            # Measure duration
            duration = self._get_audio_duration(output_file)
            
            self.logger.info(f"✓ Generated high-quality voiceover: {output_file.name} ({duration:.2f}s)")
            return {
                "voiceover_file": str(output_file),
                "duration": duration,
                "text": clean_text,
                "section_name": output_file.stem
            }
            
        except Exception as e:
            self.logger.error(f"Error generating TTS for {output_file.name}: {e}")
            return None
    
    def _get_audio_duration(self, audio_file: Path) -> float:
        """Get duration of audio file"""
        try:
            with wave.open(str(audio_file), 'r') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / float(sample_rate)
                return duration
        except Exception as e:
            self.logger.warning(f"Could not read audio duration from {audio_file}: {e}")
            # Fallback: estimate 3 seconds per section (conservative estimate)
            return 3.0

    def _generate_timeline_csv(self, audio_metadata: List[Dict[str, Any]], 
                             broll_suggestions: List[Dict[str, Any]], 
                             output_dir: Path) -> Path:
        """Generates a DaVinci Resolve-compatible timeline CSV file."""
        timeline_csv_path = output_dir / "timeline.csv"
        
        header = ["start_time_s", "end_time_s", "duration_s", "voiceover_file", 
                 "section_name", "shot_reference", "broll_suggestion", "text"]
        
        current_time_s = 0.0
        rows = []

        for i, audio in enumerate(audio_metadata):
            start_time = current_time_s
            end_time = start_time + audio["duration"]
            
            # Find a matching b-roll suggestion (improved matching)
            broll_suggestion = ""
            if i < len(broll_suggestions):
                broll_data = broll_suggestions[i]
                if isinstance(broll_data, dict):
                    broll_suggestion = broll_data.get("description", "")
                else:
                    broll_suggestion = str(broll_data)
            
            # Create timeline entry
            rows.append({
                "start_time_s": round(start_time, 2),
                "end_time_s": round(end_time, 2),
                "duration_s": round(audio["duration"], 2),
                "voiceover_file": Path(audio["voiceover_file"]).name,
                "section_name": audio.get("section_name", f"section_{i+1}"),
                "shot_reference": f"shot_{i+1:02d}",
                "broll_suggestion": broll_suggestion,
                "text": audio["text"][:100] + "..." if len(audio["text"]) > 100 else audio["text"],
            })
            
            # Add silence padding for the next clip
            current_time_s = end_time + self.silence_padding_s

        # Write CSV with proper error handling
        try:
            with open(timeline_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)
                
            self.logger.info(f"Timeline CSV generated: {timeline_csv_path}")
            return timeline_csv_path
            
        except Exception as e:
            self.logger.error(f"Error writing timeline CSV: {e}")
            raise

    def get_total_estimated_duration(self, script_content: str) -> float:
        """Estimate total duration without generating audio"""
        sections = self._parse_script_into_sections(script_content)
        
        # Rough estimate: 150 words per minute
        total_words = 0
        for text in sections.values():
            clean_text = self._clean_text_for_tts(text)
            total_words += len(clean_text.split())
        
        # Add silence padding between sections
        silence_time = (len(sections) - 1) * self.silence_padding_s
        estimated_speech_time = (total_words / 150) * 60  # Convert to seconds
        
        return estimated_speech_time + silence_time
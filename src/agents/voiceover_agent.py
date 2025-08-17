import asyncio
import re
import wave
import csv
from pathlib import Path
from typing import Dict, Any, List

from src.agents.base import BaseAgent

class VoiceoverAgent(BaseAgent):
    """Agent for generating voiceover and timeline data from a script."""

    def __init__(self, model: str = "gpt-4o-mini"):
        # Note: The TTS model is specified directly in the API call.
        super().__init__(model)
        self.silence_padding_s = 1.0  # 1 second of silence between clips

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrates the voiceover and timeline generation process."""
        script_content = input_data.get("script_content")
        output_dir = input_data.get("output_dir")
        broll_suggestions = input_data.get("broll_suggestions", [])

        if not script_content or not output_dir:
            return {"error": "Script content and output directory are required."}

        voiceover_dir = Path(output_dir) / "voiceover"
        voiceover_dir.mkdir(parents=True, exist_ok=True)

        # 1. Parse the script into sections
        sections = self._parse_script_into_sections(script_content)
        if not sections:
            return {"error": "Could not parse script into sections."}

        # 2. Generate TTS audio for each section and get metadata
        print("Generating voiceover audio for each script section...")
        audio_metadata = await self._generate_tts_for_sections(sections, voiceover_dir)

        # 3. Generate the timeline CSV for DaVinci Resolve
        print("Generating timeline CSV...")
        timeline_csv_path = self._generate_timeline_csv(
            audio_metadata, broll_suggestions, output_dir
        )

        return {
            "voiceover_directory": str(voiceover_dir),
            "timeline_csv_path": str(timeline_csv_path),
            "audio_files_generated": len(audio_metadata),
        }

    def _parse_script_into_sections(self, script_content: str) -> Dict[str, str]:
        """Parses a markdown script into a dictionary of {section_name: text}."""
        # Regex to find ## Headings and their content
        matches = re.findall(r"^##\s*(.*?)\n(.*?)(?=(?:^##\s*)|$)", script_content, re.S | re.M)
        
        sections = {}
        for i, (title, content) in enumerate(matches):
            # Sanitize title for filename
            clean_title = re.sub(r'[^\w\s-]', '', title.strip().lower()).replace(' ', '_')
            filename = f"{i+1:02d}_{clean_title}"
            # Clean up content for TTS
            clean_content = re.sub(r'\s*\[.*?\]\s*', ' ', content).strip()
            sections[filename] = clean_content
        
        return sections

    async def _generate_tts_for_sections(self, sections: Dict[str, str], voiceover_dir: Path) -> List[Dict[str, Any]]:
        """Generates a .wav file for each section and returns metadata including duration."""
        tasks = []
        for name, text in sections.items():
            output_file = voiceover_dir / f"{name}.wav"
            task = self._create_and_measure_audio(text, output_file)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return [res for res in results if res] # Filter out any None results from errors

    async def _create_and_measure_audio(self, text: str, output_file: Path) -> Dict[str, Any]:
        """Uses OpenAI TTS to create an audio file and then measures its duration."""
        try:
            response = await self.client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice="alloy",
                input=text,
            )
            response.stream_to_file(str(output_file))

            # Measure duration
            with wave.open(str(output_file), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
            
            print(f"✓ Generated: {output_file.name} ({duration:.2f}s)")
            return {
                "voiceover_file": str(output_file),
                "duration": duration,
                "text": text,
            }
        except Exception as e:
            print(f"Error generating TTS for {output_file.name}: {e}")
            return None

    def _generate_timeline_csv(self, audio_metadata: List[Dict[str, Any]], broll_suggestions: List[Dict[str, Any]], output_dir: Path) -> Path:
        """Generates a DaVinci Resolve-compatible timeline CSV file."""
        timeline_csv_path = output_dir / "timeline.csv"
        
        header = ["start_time_s", "end_time_s", "voiceover_file", "shot_reference", "broll_suggestion", "text"]
        
        current_time_s = 0.0
        rows = []

        for i, audio in enumerate(audio_metadata):
            start_time = current_time_s
            end_time = start_time + audio["duration"]
            
            # Find a matching b-roll suggestion (this is a simple match)
            broll_suggestion = broll_suggestions[i]["description"] if i < len(broll_suggestions) else ""

            rows.append({
                "start_time_s": start_time,
                "end_time_s": end_time,
                "voiceover_file": Path(audio["voiceover_file"]).name,
                "shot_reference": f"shot_{i+1}",
                "broll_suggestion": broll_suggestion,
                "text": audio["text"],
            })
            
            # Add silence padding for the next clip
            current_time_s = end_time + self.silence_padding_s

        with open(timeline_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
            
        return timeline_csv_path

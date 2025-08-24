from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging
import json
import re
from src.llm.base_provider import LLMProvider

class BaseAgent(ABC):
    """Base class for all AI agents"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(level=logging.INFO)
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return results"""
        pass

    async def call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """Call the LLM provider."""
        self.logger.info(f"Making LLM call with temperature {temperature}")
        response = await self.llm_provider.call_llm(messages, temperature)
        self.logger.info("LLM call successful.")
        return response

    def _parse_json_from_response(self, response: str) -> Optional[Any]:
        """Robustly parse JSON from a string, handling markdown, multiple objects, and other text."""
        if not response:
            self.logger.warning("Cannot parse JSON from empty response.")
            return None

        # Regex to find JSON within a markdown code block (more flexible)
        # It looks for ``` optionally followed by 'json', then any characters (non-greedy)
        # until the next ```. It captures the content between the backticks.
        json_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
        if json_block_match:
            json_str = json_block_match.group(1).strip()
            try:
                self.logger.info(f"Attempting to parse JSON from markdown block: {json_str[:200]}...")
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON from markdown block (content: {json_str[:200]}...): {e}")
                # If parsing from block fails, try parsing the whole response as a fallback
                pass # Fall through to general parsing attempts

        # Try to parse the entire response as a single JSON object or array
        try:
            self.logger.info(f"Attempting to parse entire response as JSON: {response[:200]}...")
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            self.logger.warning(f"Could not parse entire response as single JSON object/array: {e}")

        # Fallback: Try to find the first and last brackets of an array
        try:
            json_start = response.find('[')
            if json_start != -1:
                json_end = response.rfind(']')
                if json_end != -1:
                    json_str = response[json_start:json_end+1]
                    self.logger.info(f"Attempting to parse JSON from array brackets: {json_str[:200]}...")
                    return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Could not parse as a single JSON array from brackets: {e}")

        # Fallback: Find all individual JSON objects in the string and return as a list
        found_objects = []
        # More robust regex for finding objects/arrays that might be scattered
        for match in re.finditer(r"(\{.*?\}|\[.*?\])", response, re.DOTALL):
            try:
                obj = json.loads(match.group(1))
                found_objects.append(obj)
            except json.JSONDecodeError:
                continue # Ignore non-json parts
        
        if found_objects:
            self.logger.info(f"Successfully parsed {len(found_objects)} individual JSON objects/arrays from response.")
            # If multiple objects are found, and the request was for a single object/array,
            # this might still be problematic. For now, return the list.
            # A more advanced solution might try to combine them or pick the most relevant.
            return found_objects

        self.logger.error(f"Could not find or parse any JSON in response. Raw response: {response[:500]}...")
        return None

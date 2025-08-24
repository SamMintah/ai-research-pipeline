
import aiohttp
import json
from typing import List, Dict, Any
from src.llm.base_provider import LLMProvider

class OllamaProvider(LLMProvider):
    """Provider for interacting with the Ollama API."""

    def __init__(self, model: str = "llama3:8b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host

    async def call_llm(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """
        Call the Ollama API with the given messages and temperature.

        Args:
            messages: A list of messages to send to the LLM.
            temperature: The temperature to use for the LLM call.

        Returns:
            The response from the LLM.
        """
        prompt = self._format_prompt(messages)
        api_url = f"{self.host}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        try:
            timeout = aiohttp.ClientTimeout(total=600)  # 10-minute timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(api_url, json=payload) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    return response_json.get("response", "")
        except aiohttp.ClientError as e:
            print(f"Error calling Ollama API: {e}")
            return ""

    def _format_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Formats a list of messages into a single prompt string."""
        prompt = ""
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            prompt += f"<{role}>\n{content}\n"
        return prompt

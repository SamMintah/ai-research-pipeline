from abc import ABC, abstractmethod
from typing import Any, Dict, List
import openai
from src.config import settings

class BaseAgent(ABC):
    """Base class for all AI agents"""
    
    def __init__(self, model: str = "gpt-4-turbo-preview"):
        self.model = model
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return results"""
        pass
    
    async def call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """Make LLM API call"""
        try:
            response = await self.client.chat.completions.acreate(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM API error: {e}")
            return ""
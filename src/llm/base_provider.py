from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def call_llm(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """
        Call the LLM with the given messages and temperature.

        Args:
            messages: A list of messages to send to the LLM.
            temperature: The temperature to use for the LLM call.

        Returns:
            The response from the LLM.
        """
        pass

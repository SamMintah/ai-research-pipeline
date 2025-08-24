from typing import List, Dict, Any
import httpx
from openai import AsyncOpenAI, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.config import settings
from src.llm.base_provider import LLMProvider

class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        http_client = httpx.AsyncClient()
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            http_client=http_client
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=20),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(RateLimitError),
        before_sleep=lambda retry_state: print(f"Rate limit hit. Retrying in {retry_state.next_action.sleep:.2f} seconds...")
    )
    async def call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """Make LLM API call with exponential backoff for rate limits."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            print(f"Rate limit error after multiple retries: {e}")
            raise  # Re-raise the exception to be caught by tenacity
        except Exception as e:
            print(f"An unexpected LLM API error occurred: {e}")
            return ""

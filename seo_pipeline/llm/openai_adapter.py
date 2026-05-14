"""OpenAI structured output adapter."""
from __future__ import annotations

from openai import OpenAI, OpenAIError, RateLimitError
from pydantic import BaseModel

from seo_pipeline.llm.base import StructuredGenerationRequest, T
from seo_pipeline.utils.logging import logger


class OpenAIAdapter:
    provider = "openai"

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def generate_structured(self, request: StructuredGenerationRequest, response_model: type[T]) -> T:
        try:
            completion = self.client.beta.chat.completions.parse(
                model=request.model,
                temperature=request.temperature,
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                response_format=response_model,
            )
            parsed = completion.choices[0].message.parsed
            if not isinstance(parsed, BaseModel):
                raise TypeError("OpenAI structured output did not return a Pydantic model")
            return parsed
        except RateLimitError:
            logger.error("Rate limit alcanzado con OpenAI")
            raise
        except OpenAIError as exc:
            logger.error(f"OpenAI error generando structured output: {exc}")
            raise

"""Provider gateway for structured briefing generation."""
from __future__ import annotations

from seo_pipeline.llm.base import StructuredGenerationRequest, T
from seo_pipeline.llm.openai_adapter import OpenAIAdapter


def generate_structured_briefing(
    *,
    provider: str = "openai",
    api_key: str,
    model: str,
    temperature: float,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
) -> T:
    provider_name = provider.strip().lower()
    request = StructuredGenerationRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
    )
    if provider_name == "openai":
        return OpenAIAdapter(api_key=api_key).generate_structured(request, response_model)
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}")

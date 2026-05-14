"""LLM provider selection from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    model: str | None
    base_url: str | None


def get_llm_settings() -> LlmSettings:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower() or "openai"
    model = os.getenv("LLM_MODEL", "").strip() or None
    if provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", "").strip() or model
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    else:
        base_url = None
    return LlmSettings(provider=provider, model=model, base_url=base_url)

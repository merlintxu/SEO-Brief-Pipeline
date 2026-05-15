"""LLM provider selection from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass

from seo_pipeline.config import ProjectConfig


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    model: str | None
    base_url: str | None
    api_key: str | None = None
    prompt_version: str = "v1"


def get_llm_settings(project: ProjectConfig | None = None) -> LlmSettings:
    project_llm = project.runtime.llm if project else None
    provider = (project_llm.provider if project_llm else os.getenv("LLM_PROVIDER", "openai")).strip().lower() or "openai"
    model = (project_llm.model if project_llm else None) or os.getenv("LLM_MODEL", "").strip() or None
    base_url = project_llm.base_url if project_llm else None
    prompt_version = (project_llm.prompt_version if project_llm else os.getenv("BRIEFING_PROMPT_VERSION", "v1")).strip() or "v1"
    if provider == "ollama":
        model = model or os.getenv("OLLAMA_MODEL", "").strip() or None
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
        api_key = None
    elif provider == "anthropic":
        model = model or os.getenv("ANTHROPIC_MODEL", "").strip() or "claude-3-5-sonnet-latest"
        base_url = base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").strip()
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or None
    else:
        base_url = base_url
        api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    return LlmSettings(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        prompt_version=prompt_version,
    )

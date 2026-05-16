"""Operator-selectable runtime options.

These lists intentionally constrain Gradio inputs to provider-supported values
instead of accepting arbitrary free text for common settings.
"""
from __future__ import annotations

from dataclasses import dataclass


SEMRUSH_DATABASES = [
    "us",
    "uk",
    "ca",
    "au",
    "es",
    "mx",
    "ar",
    "co",
    "cl",
    "pe",
    "fr",
    "de",
    "it",
    "pt",
    "br",
    "nl",
    "be",
    "se",
    "no",
    "dk",
    "fi",
    "pl",
    "tr",
    "in",
    "jp",
]

GOOGLE_GL_OPTIONS = [
    "us",
    "gb",
    "ca",
    "au",
    "es",
    "mx",
    "ar",
    "co",
    "cl",
    "pe",
    "fr",
    "de",
    "it",
    "pt",
    "br",
    "nl",
    "be",
    "se",
    "no",
    "dk",
    "fi",
    "pl",
    "tr",
    "in",
    "jp",
]

GOOGLE_HL_OPTIONS = [
    "en",
    "en-us",
    "en-gb",
    "es",
    "es-es",
    "es-419",
    "fr",
    "fr-fr",
    "de",
    "de-de",
    "it",
    "it-it",
    "pt",
    "pt-br",
    "nl",
    "sv",
    "no",
    "da",
    "fi",
    "pl",
    "tr",
    "hi",
    "ja",
]

LLM_PROVIDER_OPTIONS = ["ollama", "openai", "anthropic"]

OPENAI_MODEL_OPTIONS = [
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-mini",
]

ANTHROPIC_MODEL_OPTIONS = [
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-opus-4-5",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-5-20251101",
]

OLLAMA_MODEL_OPTIONS = [
    "gemma4:26b",
    "gemma4:e4b",
    "gemma4:31b-cloud",
    "gemma4:26b-nvfp4",
    "gemma4:26b-a4b-it-q4_K_M",
    "gemma4",
    "gemma3:27b",
    "gemma3:12b",
    "gemma3:4b",
    "llama3.1",
    "llama3.2",
    "qwen3",
    "mistral",
]

DEFAULT_LLM_PROVIDER = "ollama"
DEFAULT_LLM_MODEL = "gemma4:26b"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
PROJECT_TYPE_OPTIONS = ["content", "ecommerce", "local", "saas", "marketplace"]

SERP_PROVIDER_OPTIONS = ["serpapi", "dataforseo"]


@dataclass(frozen=True)
class LlmModelOption:
    provider: str
    model: str


def llm_models_for_provider(provider: str) -> list[str]:
    provider = provider.strip().lower()
    if provider == "openai":
        return OPENAI_MODEL_OPTIONS
    if provider == "anthropic":
        return ANTHROPIC_MODEL_OPTIONS
    return OLLAMA_MODEL_OPTIONS


def validate_choice(value: str, allowed: list[str], field_name: str) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise ValueError(f"{field_name} must be one of: {', '.join(allowed)}")
    return normalized

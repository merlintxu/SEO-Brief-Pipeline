"""LLM provider gateway for structured briefing generation."""
from seo_pipeline.llm.gateway import generate_structured_briefing
from seo_pipeline.llm.ollama_adapter import OllamaAdapter
from seo_pipeline.llm.openai_adapter import OpenAIAdapter

__all__ = ["OllamaAdapter", "OpenAIAdapter", "generate_structured_briefing"]

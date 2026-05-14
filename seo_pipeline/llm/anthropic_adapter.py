"""Anthropic structured output adapter via Messages API."""
from __future__ import annotations

import json
from typing import Any

import requests

from seo_pipeline.llm.base import StructuredGenerationRequest, T


class AnthropicAdapter:
    provider = "anthropic"

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com"):
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for LLM_PROVIDER=anthropic")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def generate_structured(self, request: StructuredGenerationRequest, response_model: type[T]) -> T:
        response = requests.post(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": request.model,
                "system": request.system_prompt,
                "messages": [{"role": "user", "content": request.user_prompt}],
                "temperature": request.temperature,
                "max_tokens": 4096,
            },
            timeout=180,
        )
        response.raise_for_status()
        raw = _extract_text(response.json())
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Anthropic returned invalid JSON") from exc
        return response_model.model_validate(parsed)


def _extract_text(payload: dict[str, Any]) -> str:
    content = payload.get("content", [])
    if not isinstance(content, list):
        raise ValueError("Anthropic response missing content list")
    text_parts = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    text = "\n".join(part for part in text_parts if part).strip()
    if not text:
        raise ValueError("Anthropic response missing text content")
    return text

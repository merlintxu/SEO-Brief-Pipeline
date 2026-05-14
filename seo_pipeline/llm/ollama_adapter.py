"""Ollama adapter for local structured briefing generation."""
from __future__ import annotations

import json
from typing import Any

import requests

from seo_pipeline.llm.base import StructuredGenerationRequest, T


class OllamaAdapter:
    provider = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def generate_structured(self, request: StructuredGenerationRequest, response_model: type[T]) -> T:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": request.model,
                "prompt": _build_prompt(request.system_prompt, request.user_prompt),
                "stream": False,
                "format": "json",
                "options": {"temperature": request.temperature},
            },
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        raw = payload.get("response")
        if not isinstance(raw, str):
            raise ValueError("Ollama response missing JSON text in 'response'")
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Ollama returned invalid JSON") from exc
        return response_model.model_validate(parsed)


def _build_prompt(system_prompt: str, user_prompt: str) -> str:
    return (
        f"{system_prompt.strip()}\n\n"
        f"{user_prompt.strip()}\n\n"
        "Return only valid JSON matching the requested schema."
    )

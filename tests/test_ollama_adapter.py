import json as json_module

import pytest
import requests

from seo_pipeline.llm.base import StructuredGenerationRequest
from seo_pipeline.llm.ollama_adapter import OllamaAdapter
from seo_pipeline.models import SEOBriefing


def _payload() -> dict:
    return {
        "meta_title": "Meta title",
        "meta_description": "Meta description",
        "h1": "Brief H1",
        "tone_style": "professional",
        "unique_angle": "unique",
        "headings": [{"title": f"H2 {i}", "content": "content"} for i in range(8)],
    }


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError("failed")

    def json(self):
        return self._payload


def test_ollama_adapter_validates_json_response(monkeypatch):
    observed = {}

    def fake_post(url, json, timeout):
        observed["url"] = url
        observed["json"] = json
        observed["timeout"] = timeout
        return _Response({"response": json_module.dumps(_payload())})

    monkeypatch.setattr(requests, "post", fake_post)

    result = OllamaAdapter("http://localhost:11434").generate_structured(
        StructuredGenerationRequest(
            system_prompt="system",
            user_prompt="user",
            model="llama3.1",
            temperature=0.1,
        ),
        SEOBriefing,
    )

    assert result.h1 == "Brief H1"
    assert observed["url"] == "http://localhost:11434/api/generate"
    assert observed["json"]["format"] == "json"
    assert observed["json"]["stream"] is False


def test_ollama_adapter_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _Response({"response": "not-json"}))

    with pytest.raises(ValueError, match="invalid JSON"):
        OllamaAdapter().generate_structured(
            StructuredGenerationRequest(
                system_prompt="system",
                user_prompt="user",
                model="llama3.1",
                temperature=0.1,
            ),
            SEOBriefing,
        )

import json as json_module

import pytest
import requests

from seo_pipeline.llm.anthropic_adapter import AnthropicAdapter
from seo_pipeline.llm.base import StructuredGenerationRequest
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


def test_anthropic_adapter_validates_json_response(monkeypatch):
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["url"] = url
        observed["headers"] = headers
        observed["json"] = json
        observed["timeout"] = timeout
        return _Response({"content": [{"type": "text", "text": json_module.dumps(_payload())}]})

    monkeypatch.setattr(requests, "post", fake_post)

    result = AnthropicAdapter("key", "https://anthropic.test").generate_structured(
        StructuredGenerationRequest(
            system_prompt="system",
            user_prompt="user",
            model="claude-test",
            temperature=0.1,
        ),
        SEOBriefing,
    )

    assert result.h1 == "Brief H1"
    assert observed["url"] == "https://anthropic.test/v1/messages"
    assert observed["headers"]["x-api-key"] == "key"
    assert observed["json"]["model"] == "claude-test"


def test_anthropic_adapter_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _Response({"content": [{"type": "text", "text": "not-json"}]}),
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        AnthropicAdapter("key").generate_structured(
            StructuredGenerationRequest(
                system_prompt="system",
                user_prompt="user",
                model="claude-test",
                temperature=0.1,
            ),
            SEOBriefing,
        )


def test_anthropic_adapter_requires_api_key():
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicAdapter("")

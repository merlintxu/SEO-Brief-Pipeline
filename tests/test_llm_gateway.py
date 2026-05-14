from seo_pipeline.llm.base import StructuredGenerationRequest
from seo_pipeline.llm.gateway import generate_structured_briefing
from seo_pipeline.llm.ollama_adapter import OllamaAdapter
from seo_pipeline.llm.openai_adapter import OpenAIAdapter
from seo_pipeline.models import SEOBriefing


def _briefing() -> SEOBriefing:
    return SEOBriefing(
        meta_title="Meta title",
        meta_description="Meta description",
        h1="Brief H1",
        tone_style="professional",
        unique_angle="unique",
        headings=[{"title": f"H2 {i}", "content": "content"} for i in range(8)],
    )


def test_gateway_routes_to_openai_adapter(monkeypatch):
    observed = {}

    def fake_generate(self, request, response_model):
        observed["provider"] = self.provider
        observed["request"] = request
        observed["response_model"] = response_model
        return _briefing()

    monkeypatch.setattr(OpenAIAdapter, "generate_structured", fake_generate)

    result = generate_structured_briefing(
        provider="openai",
        api_key="test-key",
        model="gpt-4o",
        temperature=0.2,
        system_prompt="system",
        user_prompt="user",
        response_model=SEOBriefing,
    )

    assert result.h1 == "Brief H1"
    assert observed["provider"] == "openai"
    assert observed["response_model"] is SEOBriefing
    assert isinstance(observed["request"], StructuredGenerationRequest)
    assert observed["request"].model == "gpt-4o"


def test_gateway_rejects_unknown_provider():
    try:
        generate_structured_briefing(
            provider="unknown",
            api_key="test-key",
            model="model",
            temperature=0.0,
            system_prompt="system",
            user_prompt="user",
            response_model=SEOBriefing,
        )
    except RuntimeError as exc:
        assert "Unsupported LLM_PROVIDER" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_gateway_routes_to_ollama_adapter(monkeypatch):
    observed = {}

    def fake_generate(self, request, response_model):
        observed["base_url"] = self.base_url
        observed["request"] = request
        observed["response_model"] = response_model
        return _briefing()

    monkeypatch.setattr(OllamaAdapter, "generate_structured", fake_generate)

    result = generate_structured_briefing(
        provider="ollama",
        model="llama3.1",
        temperature=0.1,
        system_prompt="system",
        user_prompt="user",
        response_model=SEOBriefing,
        base_url="http://ollama.test",
    )

    assert result.h1 == "Brief H1"
    assert observed["base_url"] == "http://ollama.test"
    assert observed["request"].model == "llama3.1"

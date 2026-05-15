import pytest

from seo_pipeline.config import ProjectConfig
from seo_pipeline.llm.config import get_llm_settings
from seo_pipeline.vendors.capabilities import resolve_serp_provider_plan


def make_project(**runtime_overrides) -> ProjectConfig:
    runtime = {
        "llm": {
            "provider": "ollama",
            "model": "llama3.1",
            "base_url": "http://ollama.local:11434",
            "prompt_version": "v1",
        },
        "providers": {
            "serp": {
                "provider_order": ["dataforseo", "serpapi"],
            }
        },
    }
    runtime.update(runtime_overrides)
    return ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="p1",
        base_domain="example.com",
        gsc_property="https://example.com/",
        sheets_id="",
        runtime=runtime,
    )


def test_project_runtime_config_resolves_llm_settings(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    project = make_project()

    settings = get_llm_settings(project)

    assert settings.provider == "ollama"
    assert settings.model == "llama3.1"
    assert settings.base_url == "http://ollama.local:11434"
    assert settings.prompt_version == "v1"


def test_project_runtime_config_drives_serp_provider_order(monkeypatch):
    monkeypatch.delenv("SERP_PROVIDER_ORDER", raising=False)
    project = make_project()
    client = type(
        "Client",
        (),
        {
            "serpapi_key": "serp",
            "dataforseo_login": "user",
            "dataforseo_password": "pass",
        },
    )()

    plan = resolve_serp_provider_plan(client, project)

    assert plan.provider_order == ("dataforseo", "serpapi")


def test_project_runtime_config_does_not_fallback_outside_requested_serp_provider(monkeypatch):
    monkeypatch.delenv("SERP_PROVIDER_ORDER", raising=False)
    project = make_project(providers={"serp": {"provider_order": ["dataforseo"]}})
    client = type(
        "Client",
        (),
        {
            "serpapi_key": "serp",
            "dataforseo_login": None,
            "dataforseo_password": None,
        },
    )()

    plan = resolve_serp_provider_plan(client, project)

    assert plan.provider_order == ()
    assert plan.use_serpapi is False
    assert plan.use_dataforseo is False


def test_project_runtime_config_rejects_unknown_llm_provider():
    with pytest.raises(ValueError, match="llm.provider"):
        make_project(llm={"provider": "unknown", "model": "x"})


def test_project_runtime_config_rejects_unknown_serp_provider():
    with pytest.raises(ValueError, match="serp.provider_order"):
        make_project(providers={"serp": {"provider_order": ["unsupported"]}})

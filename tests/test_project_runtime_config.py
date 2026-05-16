import pytest

from seo_pipeline.config import ClientConfig, ProjectConfig, RuntimeSettings, get_config
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


def test_default_project_runtime_is_local_ollama_gemma():
    project = ProjectConfig(
        project_id="p-default",
        client_id="c1",
        name="Default",
        base_domain="example.com",
        gsc_property="",
        sheets_id="",
    )

    assert project.runtime.llm.provider == "ollama"
    assert project.runtime.llm.model == "gemma4:26b"


def test_global_runtime_settings_are_applied_to_active_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = get_config()
    cfg.runtime_settings = RuntimeSettings(semrush_token="global-semrush", serpapi_key="global-serp")
    client = ClientConfig(client_id="c1", name="Client")

    effective = cfg.apply_effective_client_defaults(client)

    assert effective.semrush_token == "global-semrush"
    assert effective.serpapi_key == "global-serp"


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

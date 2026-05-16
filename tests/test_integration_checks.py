from seo_pipeline.config import ClientConfig, ProjectConfig, ProjectRuntimeConfig, RuntimeSettings, get_config
from seo_pipeline.integration_checks import checks_to_markdown, run_connection_checks


class _FakeSemrush:
    def __init__(self, *args, **kwargs):
        pass

    def fetch_related(self, *args, **kwargs):
        return {}


class _FakeGscService:
    def sites(self):
        return self

    def list(self):
        return self

    def execute(self):
        return {"siteEntry": []}


class _FakeSheets:
    def __init__(self, *args, **kwargs):
        pass


def test_run_connection_checks_sanitized_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    client = ClientConfig(
        client_id="c1",
        name="Client",
        semrush_token="semrush",
        serpapi_key="serp",
        openai_key="openai",
        gsc_sa_path="credentials/google.json",
        sheets_sa_path="credentials/google.json",
    )
    project = ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="Project",
        base_domain="https://example.com",
        gsc_property="https://example.com/",
        ga4_property_id="123456",
        sheets_id="sheet-id",
        runtime=ProjectRuntimeConfig(llm={"provider": "openai", "model": "gpt-4o"}),
    )

    results = run_connection_checks(
        client,
        project,
        semrush_factory=_FakeSemrush,
        serp_search=lambda *args, **kwargs: {"organic_results": []},
        gsc_service_builder=lambda *args, **kwargs: _FakeGscService(),
        sheets_handler_factory=_FakeSheets,
        ga4_fetcher=lambda *args, **kwargs: object(),
    )

    assert {result.status for result in results} == {"ok"}
    markdown = checks_to_markdown(results)
    assert "semrush" in markdown
    assert "test-openai-key" not in markdown


def test_run_connection_checks_skips_unconfigured_services(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "seo_pipeline.integration_checks.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ollama unavailable")),
    )
    get_config().runtime_settings = RuntimeSettings(
        semrush_token=None,
        serpapi_key=None,
        openai_key=None,
        anthropic_key=None,
        dataforseo_login=None,
        dataforseo_password=None,
    )
    client = ClientConfig(client_id="c1", name="Client")
    project = ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="Project",
        base_domain="https://example.com",
        gsc_property="",
        sheets_id="",
    )

    results = run_connection_checks(client, project)

    statuses = {result.service: result.status for result in results}
    assert statuses["semrush"] == "skipped"
    assert statuses["serp"] == "skipped"
    assert statuses["gsc"] == "skipped"
    assert statuses["ga4"] == "skipped"
    assert statuses["sheets"] == "skipped"
    assert statuses["llm"] == "failed"

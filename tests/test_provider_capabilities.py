from seo_pipeline.config import ClientConfig
from seo_pipeline.vendors.capabilities import resolve_serp_provider_plan


def test_resolve_serp_provider_plan_defaults(monkeypatch):
    monkeypatch.delenv("SERP_ENABLE_SERPAPI", raising=False)
    monkeypatch.delenv("SERP_ENABLE_DATAFORSEO", raising=False)
    monkeypatch.delenv("SERP_PROVIDER_ORDER", raising=False)
    client = ClientConfig(
        client_id="c1",
        name="c1",
        serpapi_key="serp",
        dataforseo_login="user",
        dataforseo_password="pass",
    )
    plan = resolve_serp_provider_plan(client)
    assert plan.provider_order == ("serpapi", "dataforseo")
    assert plan.use_serpapi is True
    assert plan.use_dataforseo is True


def test_resolve_serp_provider_plan_respects_flags(monkeypatch):
    monkeypatch.setenv("SERP_ENABLE_SERPAPI", "0")
    monkeypatch.setenv("SERP_ENABLE_DATAFORSEO", "1")
    monkeypatch.setenv("SERP_PROVIDER_ORDER", "serpapi,dataforseo")
    client = ClientConfig(
        client_id="c1",
        name="c1",
        serpapi_key="serp",
        dataforseo_login="user",
        dataforseo_password="pass",
    )
    plan = resolve_serp_provider_plan(client)
    assert plan.provider_order == ("dataforseo",)
    assert plan.use_serpapi is False
    assert plan.use_dataforseo is True

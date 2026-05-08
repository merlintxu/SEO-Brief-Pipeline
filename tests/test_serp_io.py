import pytest

from seo_pipeline.config import ClientConfig, get_config
from seo_pipeline.vendors import serp_io
from seo_pipeline.vendors.serp_io import (
    extract_competitor_domains,
    normalize_domain,
    normalize_serp_snapshot,
    search_raw,
)


def test_normalize_domain_accepts_url_domain_and_subdomain():
    assert normalize_domain("https://www.example.com/path?q=1") == "example.com"
    assert normalize_domain("example.com") == "example.com"
    assert normalize_domain("blog.example.com:443/page") == "blog.example.com"


def test_extract_competitor_domains_excludes_domain_variants():
    serp_data = {
        "organic_results": [
            {"link": "https://www.example.com/owned"},
            {"link": "https://blog.example.com/owned"},
            {"link": "https://competitor.com/page"},
            {"link": "https://www.other.com/page"},
        ]
    }

    domains = extract_competitor_domains(
        serp_data,
        exclude_domain="https://www.example.com/path",
        max_domains=3,
    )

    assert domains == ["competitor.com", "other.com"]


def test_normalize_serp_snapshot_counts_core_fields():
    serp_data = {
        "search_parameters": {"q": "kw", "gl": "es", "hl": "es-es"},
        "organic_results": [
            {"link": "https://a.example/page"},
            {"link": "https://b.example/page"},
        ],
        "people_also_ask": [{"question": "Q1"}],
        "related_searches": [{"query": "kw guide"}, {"query": "kw tips"}],
        "ai_overview": {"sources": [{"link": "https://source.example"}]},
    }

    snapshot = normalize_serp_snapshot(serp_data, provider="serpapi")

    assert snapshot.provider == "serpapi"
    assert snapshot.query == "kw"
    assert snapshot.organic_results_count == 2
    assert snapshot.people_also_ask_count == 1
    assert snapshot.related_searches_count == 2
    assert snapshot.ai_overview_present is True
    assert snapshot.top_urls == [
        "https://a.example/page",
        "https://b.example/page",
        "https://source.example",
    ]


def test_dataforseo_fallback_requires_credentials(monkeypatch, tmp_path):
    cfg = get_config()
    cfg.cache_dir = tmp_path
    cfg.active_client = ClientConfig(
        client_id="c1",
        name="c1",
        semrush_token="token",
        serpapi_key=None,
        dataforseo_login=None,
        dataforseo_password=None,
    )

    called = False

    def fake_fetch(*args, **kwargs):
        nonlocal called
        called = True
        return {"organic_results": []}

    monkeypatch.setattr(serp_io, "SERPAPI_AVAILABLE", False)
    monkeypatch.setattr(serp_io, "GoogleSearch", None)
    monkeypatch.setattr("seo_pipeline.vendors.dataforseo_serp.fetch_serp_dataforseo", fake_fetch)

    with pytest.raises(RuntimeError, match="Todos los proveedores SERP fallaron"):
        search_raw("keyword", api_key=None)

    assert called is False

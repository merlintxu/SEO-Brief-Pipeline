import json
import pytest
import requests

from pathlib import Path

from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.config import get_config, ClientConfig, ProjectConfig
from seo_pipeline.vendors.semrush_io import SemrushClient
from seo_pipeline.models import SemrushResults, SemrushKeyword, AuditEntry, AuditReport, SchemaSignals, AnchorSet


def setup_config(tmp_path: Path):
    cfg = get_config()
    cfg.root_dir = tmp_path
    client = ClientConfig(
        client_id='c1',
        name='c1',
        semrush_token='token',
        serpapi_key='serp',
        openai_key='ok',
        gsc_sa_path=None,
        sheets_sa_path=None
    )
    proj = ProjectConfig(
        project_id='p1',
        client_id='c1',
        name='p1',
        base_domain='example.com',
        gsc_property='https://example.com/',
        sheets_id='',
        output_dir='outputs'
    )
    cfg.active_client = client
    cfg.active_project = proj
    return cfg


def test_semrush_network_failure_writes_status(tmp_path, monkeypatch):
    cfg = setup_config(tmp_path)

    def raise_req(self, *a, **kw):
        raise requests.exceptions.RequestException("network")

    monkeypatch.setattr(SemrushClient, 'fetch_related', raise_req)

    status_path = tmp_path / 'status.json'
    output_dir = tmp_path / "run_network"
    with pytest.raises(requests.exceptions.RequestException):
        run_full_pipeline('kw', status_path=status_path, upload_to_sheets=False, output_dir=output_dir)

    assert status_path.exists()
    data = json.loads(status_path.read_text(encoding='utf-8'))
    assert data.get('status') == 'failed'
    assert data.get('error_category') == 'network'
    metrics = json.loads((output_dir / "run_metrics.json").read_text(encoding="utf-8"))
    assert metrics.get("status") == "failed"
    assert metrics.get("error_category") == "network"


def test_openai_failure_writes_status(tmp_path, monkeypatch):
    cfg = setup_config(tmp_path)

    # Semrush returns minimal results
    def semrush_ok(self, *a, **kw):
        return SemrushResults(
            keyword_principal=SemrushKeyword(keyword='kw', search_volume=10),
            keywords_secundarias=[]
        )

    monkeypatch.setattr(SemrushClient, 'fetch_related', semrush_ok)

    # Minimal SERP
    monkeypatch.setattr('seo_pipeline.pipeline.search_raw', lambda *a, **k: {'organic_results': [], 'search_parameters': {}})

    # Minimal audit report
    monkeypatch.setattr('seo_pipeline.pipeline.audit_urls', lambda urls: type('R', (), {'entries': [], 'model_dump': lambda self=None: {}})())

    # anchors
    monkeypatch.setattr('seo_pipeline.pipeline.generate_anchors', lambda **kw: AnchorSet(primary=['a'], secondary=[], internal=[]))

    # Force OpenAI error from generate_briefing
    from openai import OpenAIError

    def raise_openai(*a, **kw):
        raise OpenAIError("openai boom")

    monkeypatch.setattr('seo_pipeline.pipeline.generate_briefing', raise_openai)

    status_path = tmp_path / 'status.json'
    output_dir = tmp_path / "run_openai"
    with pytest.raises(OpenAIError):
        run_full_pipeline('kw', status_path=status_path, upload_to_sheets=False, output_dir=output_dir)

    assert status_path.exists()
    data = json.loads(status_path.read_text(encoding='utf-8'))
    assert data.get('status') == 'failed'
    assert data.get('error_category') == 'unknown'
    metrics = json.loads((output_dir / "run_metrics.json").read_text(encoding="utf-8"))
    assert metrics.get("status") == "failed"
    assert metrics.get("error_category") == "unknown"


def test_serp_failure_writes_rate_limit_category(tmp_path, monkeypatch):
    setup_config(tmp_path)

    def semrush_ok(self, *a, **kw):
        return SemrushResults(
            keyword_principal=SemrushKeyword(keyword='kw', search_volume=10),
            keywords_secundarias=[]
        )

    monkeypatch.setattr(SemrushClient, 'fetch_related', semrush_ok)
    monkeypatch.setattr('seo_pipeline.pipeline.search_raw', lambda *a, **k: (_ for _ in ()).throw(RuntimeError("rate limit exceeded")))

    status_path = tmp_path / 'status.json'
    output_dir = tmp_path / "run_serp"
    with pytest.raises(RuntimeError, match="rate limit exceeded"):
        run_full_pipeline('kw', status_path=status_path, upload_to_sheets=False, output_dir=output_dir)

    data = json.loads(status_path.read_text(encoding='utf-8'))
    assert data.get('status') == 'failed'
    assert data.get('error_category') == 'rate_limit'
    metrics = json.loads((output_dir / "run_metrics.json").read_text(encoding="utf-8"))
    assert metrics.get("status") == "failed"
    assert metrics.get("error_category") == "rate_limit"

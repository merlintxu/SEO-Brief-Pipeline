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
        serpapi_key=None,
        openai_key=None,
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
    with pytest.raises(requests.exceptions.RequestException):
        run_full_pipeline('kw', status_path=status_path, upload_to_sheets=False)

    assert status_path.exists()
    data = json.loads(status_path.read_text(encoding='utf-8'))
    assert data.get('status') == 'failed'


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
    monkeypatch.setattr('seo_pipeline.vendors.serp_io.search_raw', lambda *a, **kw: {
        'organic_results': [], 'search_parameters': {}, 'ai_overview': None, 'people_also_ask': [], 'related_searches': []
    })

    # Minimal audit report
    entry = AuditEntry(
        url='https://a', status_code=200, title='t', h1='h1', meta_desc='d', word_count=100,
        headings={'H2': []}, schema_signals=SchemaSignals(), is_pdf=False, errors=[]
    )
    audit = AuditReport(label='lab', entries=[entry], generated_at='now')
    monkeypatch.setattr('seo_pipeline.audit.content_audit.audit_urls', lambda urls: audit)

    # anchors
    monkeypatch.setattr('seo_pipeline.anchors.generate_anchors', lambda **kw: AnchorSet(primary=['a'], secondary=[], internal=[]))

    # Force OpenAI error from generate_briefing
    from openai.error import OpenAIError

    def raise_openai(*a, **kw):
        raise OpenAIError("openai boom")

    monkeypatch.setattr('seo_pipeline.blueprint.generate_briefing', raise_openai)

    status_path = tmp_path / 'status.json'
    with pytest.raises(OpenAIError):
        run_full_pipeline('kw', status_path=status_path, upload_to_sheets=False)

    assert status_path.exists()
    data = json.loads(status_path.read_text(encoding='utf-8'))
    assert data.get('status') == 'failed'

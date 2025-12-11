import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from seo_pipeline.config import get_config, ClientConfig, ProjectConfig
from seo_pipeline.models import SemrushResults, SemrushKeyword, SheetRow24


def setup_cfg(tmp_path: Path):
    cfg = get_config()
    cfg.root_dir = tmp_path
    client = ClientConfig(
        client_id='c1',
        name='c1',
        semrush_token='token',
        serpapi_key=None,
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


def poll_status(client, run_id, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        r = client.get(f"/briefing/{run_id}")
        if r.status_code == 200:
            data = r.json()
            if data.get("status") in ("done", "failed"):
                return data
        time.sleep(0.2)
    return None


def test_api_background_success(tmp_path, monkeypatch):
    cfg = setup_cfg(tmp_path)

    # Mock providers to return minimal successful data
    monkeypatch.setattr('seo_pipeline.vendors.semrush_io.SemrushClient.fetch_related', lambda *a, **k: SemrushResults(keyword_principal=SemrushKeyword(keyword='kw', search_volume=10), keywords_secundarias=[]))
    monkeypatch.setattr('seo_pipeline.vendors.serp_io.search_raw', lambda *a, **k: {'organic_results': [], 'search_parameters': {}})
    monkeypatch.setattr('seo_pipeline.audit.content_audit.audit_urls', lambda urls: type('R', (), {'entries': [], 'model_dump': lambda self=None: {}})())
    monkeypatch.setattr('seo_pipeline.anchors.generate_anchors', lambda **kw: type('A', (), {'model_dump': lambda self=None: {}})())
    # Briefing minimal
    def fake_briefing(*a, **kw):
        return type('B', (), {'model_dump': lambda self=None: {}, 'headings': [] , 'meta_title':'mt','meta_description':'md','h1':'h1','tone_style':'t','unique_angle':'u','longitud_recomendada':'lr','eeat_notas':'','faqs':[],'external_links':[],'multimedia_suggestions':[]})()
    monkeypatch.setattr('seo_pipeline.blueprint.generate_briefing', fake_briefing)
    monkeypatch.setattr('seo_pipeline.row24.build_row24', lambda *a, **k: SheetRow24(kw_principal='kw', run_id='r1'))
    monkeypatch.setattr('seo_pipeline.exporter.export_all_formats', lambda *a, **k: {'json': Path('x.json')})
    monkeypatch.setattr('seo_pipeline.vendors.sheets_io.upsert_to_sheet', lambda *a, **k: {'status': 'ok'})

    # Import app here (it uses get_config())
    from api.main import app
    client = TestClient(app)

    resp = client.post('/briefing', json={"keyword": "prueba", "target_url": None, "upload_to_sheets": False, "related_limit": 10, "serp_num": 10})
    assert resp.status_code == 200
    body = resp.json()
    run_id = body['run_id']

    data = poll_status(client, run_id, timeout=8.0)
    assert data is not None and data.get('status') == 'done'


def test_api_background_sheets_failure_logs_but_completes(tmp_path, monkeypatch):
    cfg = setup_cfg(tmp_path)

    monkeypatch.setattr('seo_pipeline.vendors.semrush_io.SemrushClient.fetch_related', lambda *a, **k: SemrushResults(keyword_principal=SemrushKeyword(keyword='kw', search_volume=10), keywords_secundarias=[]))
    monkeypatch.setattr('seo_pipeline.vendors.serp_io.search_raw', lambda *a, **k: {'organic_results': [], 'search_parameters': {}})
    monkeypatch.setattr('seo_pipeline.audit.content_audit.audit_urls', lambda urls: type('R', (), {'entries': [], 'model_dump': lambda self=None: {}})())
    monkeypatch.setattr('seo_pipeline.anchors.generate_anchors', lambda **kw: type('A', (), {'model_dump': lambda self=None: {}})())
    monkeypatch.setattr('seo_pipeline.blueprint.generate_briefing', lambda *a, **k: type('B', (), {'model_dump': lambda self=None: {}, 'headings': [] , 'meta_title':'mt','meta_description':'md','h1':'h1','tone_style':'t','unique_angle':'u','longitud_recomendada':'lr','eeat_notas':'','faqs':[],'external_links':[],'multimedia_suggestions':[]})())
    monkeypatch.setattr('seo_pipeline.row24.build_row24', lambda *a, **k: SheetRow24(kw_principal='kw', run_id='r1'))
    monkeypatch.setattr('seo_pipeline.exporter.export_all_formats', lambda *a, **k: {'json': Path('x.json')})

    # Make upsert_to_sheet raise an APIError-like exception
    class FakeAPIError(Exception):
        pass

    def raise_sheets(*a, **k):
        raise FakeAPIError('sheetsboom')

    monkeypatch.setattr('seo_pipeline.vendors.sheets_io.upsert_to_sheet', raise_sheets)

    from api.main import app
    client = TestClient(app)
    resp = client.post('/briefing', json={"keyword": "prueba", "target_url": None, "upload_to_sheets": True, "related_limit": 10, "serp_num": 10})
    assert resp.status_code == 200
    run_id = resp.json()['run_id']

    data = poll_status(client, run_id, timeout=8.0)
    # despite sheets error, pipeline should complete and status==done (Sheets error is non-fatal in pipeline)
    assert data is not None and data.get('status') == 'done'


def test_api_background_gsc_failure_handled(tmp_path, monkeypatch):
    cfg = setup_cfg(tmp_path)
    # enable gsc path to trigger GSC block
    cfg.active_client.gsc_sa_path = 'missing.json'

    monkeypatch.setattr('seo_pipeline.vendors.semrush_io.SemrushClient.fetch_related', lambda *a, **k: SemrushResults(keyword_principal=SemrushKeyword(keyword='kw', search_volume=10), keywords_secundarias=[]))
    monkeypatch.setattr('seo_pipeline.vendors.serp_io.search_raw', lambda *a, **k: {'organic_results': [], 'search_parameters': {}})
    monkeypatch.setattr('seo_pipeline.audit.content_audit.audit_urls', lambda urls: type('R', (), {'entries': [], 'model_dump': lambda self=None: {}})())
    monkeypatch.setattr('seo_pipeline.anchors.generate_anchors', lambda **kw: type('A', (), {'model_dump': lambda self=None: {}})())
    monkeypatch.setattr('seo_pipeline.blueprint.generate_briefing', lambda *a, **k: type('B', (), {'model_dump': lambda self=None: {}, 'headings': [] , 'meta_title':'mt','meta_description':'md','h1':'h1','tone_style':'t','unique_angle':'u','longitud_recomendada':'lr','eeat_notas':'','faqs':[],'external_links':[],'multimedia_suggestions':[]})())
    monkeypatch.setattr('seo_pipeline.row24.build_row24', lambda *a, **k: SheetRow24(kw_principal='kw', run_id='r1'))
    monkeypatch.setattr('seo_pipeline.exporter.export_all_formats', lambda *a, **k: {'json': Path('x.json')})

    # fetch_cannibalization raises RuntimeError to simulate GSC problem
    monkeypatch.setattr('seo_pipeline.vendors.gsc_io.fetch_cannibalization', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('gsc fail')))

    from api.main import app
    client = TestClient(app)
    resp = client.post('/briefing', json={"keyword": "prueba", "target_url": None, "upload_to_sheets": False, "related_limit": 10, "serp_num": 10})
    assert resp.status_code == 200
    run_id = resp.json()['run_id']
    data = poll_status(client, run_id, timeout=8.0)
    # GSC failure is handled and pipeline should complete
    assert data is not None and data.get('status') == 'done'

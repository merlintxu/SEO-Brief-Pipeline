import json
from pathlib import Path

from seo_pipeline.config import ClientConfig, ProjectConfig, get_config
from seo_pipeline.models import (
    AnchorSet,
    AuditEntry,
    AuditReport,
    BriefingSection,
    SEOBriefing,
    SemrushKeyword,
    SemrushResults,
)
from seo_pipeline.pipeline import run_full_pipeline


def _setup_config(tmp_path: Path) -> None:
    cfg = get_config()
    cfg.root_dir = tmp_path
    cfg.cache_dir = tmp_path / "cache"
    cfg.active_client = ClientConfig(
        client_id="c1",
        name="c1",
        semrush_token="semrush",
        serpapi_key="serp",
        openai_key="openai",
        gsc_sa_path=None,
        sheets_sa_path=None,
    )
    cfg.active_project = ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="p1",
        base_domain="example.com",
        gsc_property="https://example.com/",
        sheets_id="",
        output_dir="outputs",
    )


def test_run_metrics_contract_keeps_core_fields_and_stage_observability(tmp_path, monkeypatch):
    _setup_config(tmp_path)

    monkeypatch.setattr(
        "seo_pipeline.pipeline.SemrushClient.fetch_related",
        lambda *args, **kwargs: SemrushResults(
            keyword_principal=SemrushKeyword(keyword="kw", search_volume=100),
            keywords_secundarias=[SemrushKeyword(keyword="kw secundaria", search_volume=50)],
        ),
    )
    monkeypatch.setattr(
        "seo_pipeline.pipeline.search_raw",
        lambda *args, **kwargs: {
            "search_parameters": {"q": "kw", "gl": "es", "hl": "es-es"},
            "organic_results": [{"link": "https://competitor.com/page"}],
        },
    )
    monkeypatch.setattr(
        "seo_pipeline.pipeline.audit_urls",
        lambda urls: AuditReport(
            label="top10_audit",
            generated_at="2026-01-01T00:00:00",
            entries=[
                AuditEntry(
                    url=urls[0],
                    status_code=200,
                    title="Competitor title",
                    h1="Competitor h1",
                    headings={"H2": ["Competitor section"]},
                    word_count=1000,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        "seo_pipeline.pipeline.generate_anchors",
        lambda **kwargs: AnchorSet(primary=["kw guide"], secondary=["kw secundaria"], internal=["learn kw"]),
    )
    monkeypatch.setattr(
        "seo_pipeline.pipeline.generate_briefing",
        lambda *args, **kwargs: SEOBriefing(
            meta_title="KW Guide",
            meta_description="KW description",
            h1="KW H1",
            tone_style="expert",
            unique_angle="Useful angle",
            headings=[BriefingSection(title=f"S{i}", content="Content") for i in range(1, 9)],
        ),
    )

    output_dir = tmp_path / "run"
    status_path = output_dir / "status.json"
    run_full_pipeline(
        "kw",
        run_id="run_contract",
        upload_to_sheets=False,
        status_path=status_path,
        output_dir=output_dir,
    )

    metrics = json.loads((output_dir / "run_metrics.json").read_text(encoding="utf-8"))

    for key in ("run_id", "keyword", "started_at", "finished_at", "status", "stages"):
        assert key in metrics
    assert metrics["status"] == "done"
    assert "quality_gates" in metrics
    assert "passed" in metrics["quality_gates"]
    assert "results" in metrics["quality_gates"]
    assert "quorum" in metrics
    assert "decision" in metrics["quorum"]
    assert "checks" in metrics["quorum"]
    assert "prompt_run" in metrics
    assert "version" in metrics["prompt_run"]
    assert "mode" in metrics["prompt_run"]

    for stage in ("semrush", "serp", "audit", "anchors", "briefing", "export"):
        payload = metrics["stages"][stage]
        assert "provider" in payload
        assert "status" in payload
        assert "retries" in payload
        assert "duration_seconds" in payload
        assert "items_processed" in payload

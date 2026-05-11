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


def test_run_full_pipeline_writes_real_artifacts_with_mocked_vendors(tmp_path, monkeypatch):
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
            "people_also_ask": [{"question": "Que es kw?"}],
            "related_searches": [{"query": "kw guia"}],
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

    status_path = tmp_path / "run" / "status.json"
    output_dir = tmp_path / "run"
    result = run_full_pipeline(
        "kw",
        run_id="run1",
        upload_to_sheets=False,
        status_path=status_path,
        output_dir=output_dir,
    )

    assert result["output_dir"] == str(output_dir)
    assert "pipeline_input" in result
    assert "provider_plan" in result
    assert "quorum" in result
    assert "partial_data" in result
    assert "keyword_set" in result
    assert "competitor_set" in result
    assert "enrichment_set" in result
    assert "briefing_plan" in result
    assert (output_dir / "serp_raw.json").exists()
    assert (output_dir / "audit_report.json").exists()
    assert result["json"].exists()
    assert result["markdown"].exists()
    assert result["csv"].exists()
    assert result["xlsx"].exists()
    assert Path(result["metrics_path"]).exists()
    metrics = json.loads((output_dir / "run_metrics.json").read_text(encoding="utf-8"))
    assert metrics["status"] == "done"
    assert set(metrics["stages"]) >= {"semrush", "serp", "audit", "anchors", "briefing", "export"}
    for stage in ("semrush", "serp", "audit", "anchors", "briefing", "export"):
        assert "provider" in metrics["stages"][stage]
        assert "retries" in metrics["stages"][stage]
        assert "status" in metrics["stages"][stage]
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == "done"

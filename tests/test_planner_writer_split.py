from seo_pipeline.blueprint import build_briefing_plan_artifact
from seo_pipeline.models import SerpSnapshot


def test_build_briefing_plan_artifact_from_audit_and_serp():
    snapshot = SerpSnapshot(
        provider="serpapi",
        query="seo brief",
        gl="es",
        hl="es-es",
        organic_results_count=10,
        people_also_ask_count=3,
        related_searches_count=5,
    )
    audit_report = {
        "entries": [
            {"url": "https://example.com/a", "h1": "Guia SEO"},
            {"url": "https://example.com/b", "h1": "Checklist SEO"},
        ]
    }
    plan = build_briefing_plan_artifact(
        keyword="seo brief",
        serp_snapshot=snapshot,
        audit_report=audit_report,
        prompt_version="v1",
    )
    assert plan.keyword == "seo brief"
    assert plan.prompt_version == "v1"
    assert plan.planner_version == "v1"
    assert len(plan.required_sections) == 2

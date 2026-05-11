from seo_pipeline.models import (
    AnchorSet,
    AuditEntry,
    AuditReport,
    BriefingPlan,
    CompetitorSet,
    EnrichmentSet,
    GscCannibalization,
    KeywordSet,
    PipelineInput,
    SchemaSignals,
    SemrushKeyword,
    SerpSnapshot,
)


def test_pipeline_input_contract_validation():
    payload = PipelineInput(keyword="seo content brief", related_limit=30, serp_num=10)
    assert payload.keyword == "seo content brief"
    assert payload.related_limit == 30
    assert payload.serp_num == 10


def test_keyword_and_competitor_sets_contracts():
    keyword_set = KeywordSet(
        principal=SemrushKeyword(keyword="seo", search_volume=1000),
        related=[SemrushKeyword(keyword="seo brief", search_volume=300)],
    )
    competitor_set = CompetitorSet(
        top_urls=["https://example.com/a", "https://example.com/b"],
        domains=["example.com", "example.org"],
    )
    assert keyword_set.principal.keyword == "seo"
    assert len(competitor_set.top_urls) == 2


def test_enrichment_set_contract_with_optional_fields():
    snapshot = SerpSnapshot(provider="serpapi", query="seo", organic_results_count=10)
    report = AuditReport(
        label="audit",
        entries=[
            AuditEntry(
                url="https://example.com/a",
                status_code=200,
                elapsed_ms=120,
                title="Title",
                h1="H1",
                meta_desc="desc",
                word_count=300,
                headings={},
                schema_signals=SchemaSignals(),
            )
        ],
        generated_at="2026-05-11T10:00:00",
    )
    enrichment = EnrichmentSet(
        serp_snapshot=snapshot,
        audit_report=report,
        cannibalization=GscCannibalization(site_url="https://example.com", start_date="2026-01-01", end_date="2026-05-01", items=[]),
        anchors=AnchorSet(primary=["seo"], secondary=[], internal=[]),
    )
    assert enrichment.serp_snapshot.provider == "serpapi"
    assert enrichment.audit_report.entries[0].status_code == 200


def test_briefing_plan_contract():
    plan = BriefingPlan(
        keyword="seo brief",
        intent_summary="Informational intent focused on process and templates.",
        required_sections=["What is SEO brief", "Template", "Checklist"],
        evidence_points=["SERP shows listicles in top 3", "PAA focuses on templates"],
        constraints=["Spanish language", "Actionable examples"],
        prompt_version="planner-v1",
    )
    assert plan.prompt_version == "planner-v1"
    assert "Template" in plan.required_sections

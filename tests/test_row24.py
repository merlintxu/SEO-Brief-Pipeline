from seo_pipeline.models import AnchorSet, BriefingSection, SEOBriefing, SerpSnapshot
from seo_pipeline.row24 import build_row24


def test_build_row24_uses_serp_snapshot_fields():
    briefing = SEOBriefing(
        meta_title="Meta",
        meta_description="Description",
        h1="Heading",
        tone_style="neutral",
        unique_angle="Angle",
        headings=[BriefingSection(title=f"S{i}", content="C") for i in range(1, 9)],
    )
    anchors = AnchorSet(primary=["p1"], secondary=["s1"], internal=["i1"])
    snapshot = SerpSnapshot(
        provider="serpapi",
        query="kw",
        gl="es",
        hl="es-es",
        organic_results_count=10,
        top_urls=["https://example.com"],
        people_also_ask_count=4,
        related_searches_count=7,
        ai_overview_present=True,
        knowledge_graph_present=True,
    )

    row = build_row24(
        kw="kw",
        sv=120,
        secondary_kws=["a", "b"],
        target_url="https://target",
        briefing=briefing,
        serp_snapshot=snapshot,
        anchors=anchors,
        top_competitors=["a.com", "b.com", "c.com"],
        run_id="run1",
    )

    assert row.ai_overview_present is True
    assert row.paa_count == 4
    assert row.related_count == 7
    assert row.kg_present is True

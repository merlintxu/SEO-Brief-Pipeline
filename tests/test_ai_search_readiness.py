from seo_pipeline.ai_search_readiness import (
    build_readiness_for_new_page,
    build_readiness_report_from_html,
    review_briefing_for_ai_search,
)
from seo_pipeline.models import BriefingSection, SEOBriefing


def test_build_readiness_report_from_html_detects_core_signals():
    html = """
    <html>
      <head>
        <title>Guide</title>
        <meta name="description" content="Useful guide">
        <link rel="canonical" href="https://example.com/guide">
        <script type="application/ld+json">{"@type":"Article"}</script>
      </head>
      <body>
        <h1>Guide</h1>
        <p>Author: Expert. Updated today. Contact us. This is useful text.</p>
        <a href="/related">Related</a>
        <img src="hero.jpg">
        <button></button>
      </body>
    </html>
    """

    report = build_readiness_report_from_html("https://example.com/guide", html)

    assert report.technical.indexable
    assert report.structured_data.has_article
    assert report.media.images_missing_alt == 1
    assert any(finding.category == "media" for finding in report.findings)
    assert any(finding.category == "agent_friendly" for finding in report.findings)


def test_new_page_readiness_adds_vertical_requirements():
    ecommerce = build_readiness_for_new_page(keyword="running shoes", project_type="ecommerce")
    local = build_readiness_for_new_page(keyword="dentist madrid", project_type="local")

    assert any(finding.category == "ecommerce" for finding in ecommerce.findings)
    assert any(finding.category == "local" for finding in local.findings)


def test_brief_quality_review_rejects_unsupported_tactics():
    briefing = SEOBriefing(
        meta_title="Guide",
        meta_description="Useful guide",
        h1="Guide",
        tone_style="expert",
        unique_angle="Specific evidence-led angle for the page",
        eeat_notas="Author and reviewer required",
        headings=[BriefingSection(title=f"S{i}", content="Add llms.txt for AI visibility") for i in range(1, 9)],
        multimedia_suggestions=["Add comparison table"],
    )

    review = review_briefing_for_ai_search(briefing, None)

    assert not review.passed
    assert any(finding.category == "myth" for finding in review.findings)

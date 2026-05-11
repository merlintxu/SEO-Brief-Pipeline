from seo_pipeline.models import CompetitorSet, KeywordSet, SemrushKeyword
from seo_pipeline.quality_gates import evaluate_quality_gates


def _keyword_set() -> KeywordSet:
    return KeywordSet(
        principal=SemrushKeyword(keyword="seo brief", search_volume=100),
        related=[SemrushKeyword(keyword="seo", search_volume=80)],
    )


def test_quality_gates_pass_in_default_mode_with_warnings():
    eval_result = evaluate_quality_gates(
        keyword_set=_keyword_set(),
        competitor_set=CompetitorSet(top_urls=[], domains=[]),
        audit_entries_count=0,
        strict=False,
    )
    assert eval_result.passed is True
    assert any(item.severity == "warning" for item in eval_result.results)


def test_quality_gates_fail_in_strict_mode_for_low_coverage():
    eval_result = evaluate_quality_gates(
        keyword_set=_keyword_set(),
        competitor_set=CompetitorSet(top_urls=[], domains=[]),
        audit_entries_count=0,
        strict=True,
    )
    assert eval_result.passed is False
    assert len(eval_result.failures) >= 1

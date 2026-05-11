from seo_pipeline.models import CompetitorSet, KeywordSet, SemrushKeyword
from seo_pipeline.quorum import QuorumPolicy, evaluate_quorum


def _keyword_set(related_count: int) -> KeywordSet:
    return KeywordSet(
        principal=SemrushKeyword(keyword="seo", search_volume=100),
        related=[SemrushKeyword(keyword=f"rel-{i}", search_volume=10) for i in range(related_count)],
    )


def test_quorum_continue_when_not_enforced():
    decision = evaluate_quorum(
        keyword_set=_keyword_set(related_count=0),
        competitor_set=CompetitorSet(top_urls=[], domains=[]),
        audit_entries_count=0,
        policy=QuorumPolicy(enforce=False),
    )
    assert decision.decision == "continue"
    assert len(decision.failed_checks) >= 1


def test_quorum_fail_when_enforced():
    decision = evaluate_quorum(
        keyword_set=_keyword_set(related_count=0),
        competitor_set=CompetitorSet(top_urls=[], domains=[]),
        audit_entries_count=0,
        policy=QuorumPolicy(enforce=True),
    )
    assert decision.decision == "fail"
    assert len(decision.failed_checks) >= 1

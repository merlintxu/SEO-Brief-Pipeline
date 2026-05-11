from __future__ import annotations

from dataclasses import dataclass

from seo_pipeline.models import CompetitorSet, KeywordSet


@dataclass(frozen=True)
class QuorumPolicy:
    min_related_keywords: int = 1
    min_top_urls: int = 3
    min_competitor_domains: int = 2
    min_audit_entries: int = 1
    enforce: bool = False


@dataclass(frozen=True)
class QuorumCheck:
    rule: str
    passed: bool
    observed: int
    required: int
    message: str


@dataclass(frozen=True)
class QuorumDecision:
    decision: str  # continue | fail
    checks: list[QuorumCheck]

    @property
    def failed_checks(self) -> list[QuorumCheck]:
        return [c for c in self.checks if not c.passed]


def evaluate_quorum(
    *,
    keyword_set: KeywordSet,
    competitor_set: CompetitorSet,
    audit_entries_count: int,
    policy: QuorumPolicy,
) -> QuorumDecision:
    checks = [
        QuorumCheck(
            rule="related_keywords",
            passed=len(keyword_set.related) >= policy.min_related_keywords,
            observed=len(keyword_set.related),
            required=policy.min_related_keywords,
            message="Related keywords coverage below quorum",
        ),
        QuorumCheck(
            rule="top_urls",
            passed=len(competitor_set.top_urls) >= policy.min_top_urls,
            observed=len(competitor_set.top_urls),
            required=policy.min_top_urls,
            message="SERP top URLs coverage below quorum",
        ),
        QuorumCheck(
            rule="competitor_domains",
            passed=len(competitor_set.domains) >= policy.min_competitor_domains,
            observed=len(competitor_set.domains),
            required=policy.min_competitor_domains,
            message="Competitor domains coverage below quorum",
        ),
        QuorumCheck(
            rule="audit_entries",
            passed=audit_entries_count >= policy.min_audit_entries,
            observed=audit_entries_count,
            required=policy.min_audit_entries,
            message="Audit entries coverage below quorum",
        ),
    ]

    has_failures = any(not item.passed for item in checks)
    if has_failures and policy.enforce:
        return QuorumDecision(decision="fail", checks=checks)
    return QuorumDecision(decision="continue", checks=checks)

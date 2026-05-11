from __future__ import annotations

from dataclasses import dataclass

from seo_pipeline.models import CompetitorSet, KeywordSet


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class GateEvaluation:
    passed: bool
    results: list[GateResult]

    @property
    def failures(self) -> list[GateResult]:
        return [r for r in self.results if not r.passed and r.severity == "error"]


def evaluate_quality_gates(
    *,
    keyword_set: KeywordSet,
    competitor_set: CompetitorSet,
    audit_entries_count: int,
    strict: bool = False,
) -> GateEvaluation:
    results: list[GateResult] = []

    results.append(
        GateResult(
            gate="semrush.principal_keyword",
            passed=bool(keyword_set.principal.keyword.strip()),
            message="Principal keyword must be present",
        )
    )
    results.append(
        GateResult(
            gate="semrush.related_min",
            passed=len(keyword_set.related) >= 1,
            message="At least 1 related keyword is required",
            severity="error" if strict else "warning",
        )
    )
    results.append(
        GateResult(
            gate="serp.top_urls_min",
            passed=len(competitor_set.top_urls) >= 3,
            message="At least 3 SERP URLs are required",
            severity="error" if strict else "warning",
        )
    )
    results.append(
        GateResult(
            gate="serp.competitor_domains_min",
            passed=len(competitor_set.domains) >= 2,
            message="At least 2 competitor domains are required",
            severity="error" if strict else "warning",
        )
    )
    results.append(
        GateResult(
            gate="audit.entries_min",
            passed=audit_entries_count >= 1,
            message="At least 1 audited URL is required",
            severity="error" if strict else "warning",
        )
    )

    return GateEvaluation(
        passed=all(r.passed or r.severity != "error" for r in results),
        results=results,
    )

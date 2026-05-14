"""SLO evaluation helpers for run_metrics.json payloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SloThresholds:
    min_success_rate: float = 0.95
    max_p95_duration_seconds: float = 900.0
    max_retry_rate: float = 0.20
    max_error_category_rate: float = 0.10


def evaluate_slo_window(metrics_payloads: list[dict[str, Any]], thresholds: SloThresholds | None = None) -> dict[str, Any]:
    """Evaluate a rolling window of run metrics payloads against operational SLOs."""
    policy = thresholds or SloThresholds()
    total_runs = len(metrics_payloads)
    completed = [payload for payload in metrics_payloads if payload.get("status") == "done"]
    failed = [payload for payload in metrics_payloads if payload.get("status") == "failed"]
    durations = [_run_duration_seconds(payload) for payload in metrics_payloads]
    durations = [value for value in durations if value is not None]
    retry_runs = [payload for payload in metrics_payloads if _total_retries(payload) > 0]
    error_category_runs = [payload for payload in failed if payload.get("error_category")]

    success_rate = len(completed) / total_runs if total_runs else 1.0
    retry_rate = len(retry_runs) / total_runs if total_runs else 0.0
    error_category_rate = len(error_category_runs) / total_runs if total_runs else 0.0
    p95_duration = _percentile(durations, 0.95)

    checks = [
        _check(
            name="success_rate",
            observed=round(success_rate, 4),
            threshold=policy.min_success_rate,
            passed=success_rate >= policy.min_success_rate,
            comparator=">=",
        ),
        _check(
            name="p95_duration_seconds",
            observed=round(p95_duration, 3) if p95_duration is not None else None,
            threshold=policy.max_p95_duration_seconds,
            passed=p95_duration is None or p95_duration <= policy.max_p95_duration_seconds,
            comparator="<=",
        ),
        _check(
            name="retry_rate",
            observed=round(retry_rate, 4),
            threshold=policy.max_retry_rate,
            passed=retry_rate <= policy.max_retry_rate,
            comparator="<=",
        ),
        _check(
            name="error_category_rate",
            observed=round(error_category_rate, 4),
            threshold=policy.max_error_category_rate,
            passed=error_category_rate <= policy.max_error_category_rate,
            comparator="<=",
        ),
    ]
    return {
        "window": {
            "total_runs": total_runs,
            "completed_runs": len(completed),
            "failed_runs": len(failed),
        },
        "thresholds": {
            "min_success_rate": policy.min_success_rate,
            "max_p95_duration_seconds": policy.max_p95_duration_seconds,
            "max_retry_rate": policy.max_retry_rate,
            "max_error_category_rate": policy.max_error_category_rate,
        },
        "summary": {
            "success_rate": round(success_rate, 4),
            "p95_duration_seconds": round(p95_duration, 3) if p95_duration is not None else None,
            "retry_rate": round(retry_rate, 4),
            "error_category_rate": round(error_category_rate, 4),
        },
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
    }


def _run_duration_seconds(payload: dict[str, Any]) -> float | None:
    stages = payload.get("stages")
    if not isinstance(stages, dict):
        return None
    durations = [
        stage.get("duration_seconds")
        for stage in stages.values()
        if isinstance(stage, dict) and isinstance(stage.get("duration_seconds"), (int, float))
    ]
    if not durations:
        return None
    return float(sum(durations))


def _total_retries(payload: dict[str, Any]) -> int:
    stages = payload.get("stages")
    if not isinstance(stages, dict):
        return 0
    return sum(
        int(stage.get("retries", 0))
        for stage in stages.values()
        if isinstance(stage, dict) and isinstance(stage.get("retries", 0), int)
    )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _check(*, name: str, observed: float | None, threshold: float, passed: bool, comparator: str) -> dict[str, Any]:
    return {
        "name": name,
        "observed": observed,
        "threshold": threshold,
        "comparator": comparator,
        "passed": passed,
    }

from seo_pipeline.slo import SloThresholds, evaluate_slo_window


def _metrics(status="done", duration=100.0, retries=0, error_category=None):
    payload = {
        "status": status,
        "stages": {
            "semrush": {"duration_seconds": duration / 2, "retries": retries},
            "briefing": {"duration_seconds": duration / 2, "retries": 0},
        },
    }
    if error_category:
        payload["error_category"] = error_category
    return payload


def test_slo_window_passes_for_healthy_metrics():
    result = evaluate_slo_window(
        [
            _metrics(duration=100),
            _metrics(duration=120),
            _metrics(duration=90),
            _metrics(duration=110),
        ],
        SloThresholds(min_success_rate=0.95, max_p95_duration_seconds=300, max_retry_rate=0.25),
    )

    assert result["passed"] is True
    assert result["summary"]["success_rate"] == 1.0
    assert result["summary"]["p95_duration_seconds"] <= 300
    assert result["window"]["total_runs"] == 4


def test_slo_window_flags_failures_latency_and_retry_spikes():
    result = evaluate_slo_window(
        [
            _metrics(status="failed", duration=1000, retries=2, error_category="network"),
            _metrics(status="done", duration=950, retries=1),
            _metrics(status="done", duration=100, retries=0),
            _metrics(status="done", duration=90, retries=0),
        ],
        SloThresholds(
            min_success_rate=0.90,
            max_p95_duration_seconds=900,
            max_retry_rate=0.20,
            max_error_category_rate=0.10,
        ),
    )

    assert result["passed"] is False
    failed_checks = {item["name"] for item in result["checks"] if not item["passed"]}
    assert failed_checks == {"success_rate", "p95_duration_seconds", "retry_rate", "error_category_rate"}

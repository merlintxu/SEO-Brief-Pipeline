from seo_pipeline.cost_tracking import estimate_openai_text_cost, provider_call_estimate, summarize_costs


def test_openai_text_cost_estimate_uses_model_pricing():
    estimate = estimate_openai_text_cost(
        model="gpt-4o-2024-11-20",
        input_payload="x" * 4000,
        output_payload="y" * 800,
    )

    assert estimate.provider == "openai"
    assert estimate.input_tokens_estimated == 1000
    assert estimate.output_tokens_estimated == 200
    assert estimate.total_tokens_estimated == 1200
    assert estimate.estimated_cost_usd == 0.0045


def test_cost_summary_tracks_unknown_provider_costs():
    summary = summarize_costs(
        [
            estimate_openai_text_cost(model="gpt-4o-2024-11-20", input_payload="x" * 400, output_payload="y" * 400),
            provider_call_estimate(provider="semrush", service="keyword_related", calls=1, notes="plan-specific"),
        ]
    )

    assert summary["currency"] == "USD"
    assert summary["total_estimated_cost_usd"] > 0
    assert summary["unknown_cost_estimate_count"] == 1
    assert len(summary["estimates"]) == 2

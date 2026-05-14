"""Deterministic per-run cost estimates for operational metrics."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


OPENAI_TEXT_PRICES_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    # Official GPT-4o text pricing as of 2026-05-14:
    # input $2.50 / 1M tokens, output $10.00 / 1M tokens.
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-05-13": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
}


@dataclass(frozen=True)
class CostEstimate:
    provider: str
    service: str
    calls: int
    estimated_cost_usd: float | None
    input_tokens_estimated: int | None = None
    output_tokens_estimated: int | None = None
    total_tokens_estimated: int | None = None
    model: str | None = None
    pricing_source: str = "static_estimate"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "service": self.service,
            "calls": self.calls,
            "estimated_cost_usd": self.estimated_cost_usd,
            "input_tokens_estimated": self.input_tokens_estimated,
            "output_tokens_estimated": self.output_tokens_estimated,
            "total_tokens_estimated": self.total_tokens_estimated,
            "model": self.model,
            "pricing_source": self.pricing_source,
            "notes": self.notes,
        }


def estimate_text_tokens(*parts: Any) -> int:
    """Estimate tokens without model-specific tokenizers; stable enough for ops trends."""
    text = "\n".join(_stringify(part) for part in parts if part is not None)
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def estimate_openai_text_cost(
    *,
    model: str,
    input_payload: Any,
    output_payload: Any,
    calls: int = 1,
) -> CostEstimate:
    input_tokens = estimate_text_tokens(input_payload)
    output_tokens = estimate_text_tokens(output_payload)
    total_tokens = input_tokens + output_tokens
    prices = OPENAI_TEXT_PRICES_PER_1M_TOKENS.get(model) or OPENAI_TEXT_PRICES_PER_1M_TOKENS.get("gpt-4o")
    estimated_cost = round(
        (input_tokens * prices["input"] / 1_000_000) + (output_tokens * prices["output"] / 1_000_000),
        6,
    )
    return CostEstimate(
        provider="openai",
        service="structured_briefing",
        calls=calls,
        estimated_cost_usd=estimated_cost,
        input_tokens_estimated=input_tokens,
        output_tokens_estimated=output_tokens,
        total_tokens_estimated=total_tokens,
        model=model,
        notes="Estimated from serialized prompt context/output; not a billing source of truth.",
    )


def provider_call_estimate(*, provider: str, service: str, calls: int, notes: str) -> CostEstimate:
    return CostEstimate(
        provider=provider,
        service=service,
        calls=calls,
        estimated_cost_usd=None,
        pricing_source="not_configured",
        notes=notes,
    )


def summarize_costs(estimates: list[CostEstimate]) -> dict[str, Any]:
    known_total = sum(item.estimated_cost_usd or 0.0 for item in estimates)
    unknown_count = sum(1 for item in estimates if item.estimated_cost_usd is None)
    return {
        "currency": "USD",
        "total_estimated_cost_usd": round(known_total, 6),
        "unknown_cost_estimate_count": unknown_count,
        "estimates": [item.to_dict() for item in estimates],
    }


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)

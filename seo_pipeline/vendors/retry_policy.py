"""Provider-aware retry decisions for external calls."""
from __future__ import annotations

from collections.abc import Callable

import requests

from seo_pipeline.utils.errors import classify_error


RETRYABLE_CATEGORIES = {"network", "timeout", "rate_limit", "provider_unavailable"}
TERMINAL_CATEGORIES = {"auth", "quota", "validation"}


def classify_provider_error(exc: Exception) -> str:
    """Return a stable provider failure category for retry decisions."""
    if isinstance(exc, requests.exceptions.HTTPError):
        response = exc.response
        status_code = response.status_code if response is not None else None
        if status_code == 429:
            return "rate_limit"
        if status_code in {401, 403}:
            return "auth"
        if status_code is not None and 500 <= status_code <= 599:
            return "provider_unavailable"

    message = str(exc).lower()
    if any(marker in message for marker in ("unavailable", "service unavailable", "503", "502", "504")):
        return "provider_unavailable"

    return classify_error(exc)


def should_retry_provider_error(exc: Exception, *, provider: str | None = None) -> bool:
    """Decide whether a provider exception should be retried."""
    category = classify_provider_error(exc)
    if category in TERMINAL_CATEGORIES:
        return False
    return category in RETRYABLE_CATEGORIES


def provider_retry_policy(provider: str) -> Callable[[Exception], bool]:
    """Build a retry predicate for a provider call."""

    def _should_retry(exc: Exception) -> bool:
        return should_retry_provider_error(exc, provider=provider)

    return _should_retry

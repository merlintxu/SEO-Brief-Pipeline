"""Error classification helpers for pipeline observability."""
from __future__ import annotations

from typing import Final

import requests
from pydantic import ValidationError


AUTH_MARKERS: Final = ("unauthorized", "forbidden", "invalid api key", "authentication", "401", "403")
QUOTA_MARKERS: Final = ("quota", "insufficient_quota", "billing", "credit")
RATE_LIMIT_MARKERS: Final = ("rate limit", "too many requests", "429")
TIMEOUT_MARKERS: Final = ("timeout", "timed out")
NETWORK_MARKERS: Final = ("connection", "dns", "network", "remote disconnected")


def classify_error(exc: Exception) -> str:
    """Classify errors into stable categories for metrics and status reporting."""
    message = str(exc).lower()

    if isinstance(exc, PermissionError) or any(marker in message for marker in AUTH_MARKERS):
        return "auth"
    if any(marker in message for marker in QUOTA_MARKERS):
        return "quota"
    if isinstance(exc, requests.exceptions.HTTPError) and "429" in message:
        return "rate_limit"
    if isinstance(exc, requests.exceptions.Timeout) or isinstance(exc, TimeoutError) or any(
        marker in message for marker in TIMEOUT_MARKERS
    ):
        return "timeout"
    if isinstance(exc, requests.exceptions.RequestException) or any(marker in message for marker in NETWORK_MARKERS):
        return "network"
    if isinstance(exc, (ValidationError, ValueError, TypeError)):
        return "validation"
    if any(marker in message for marker in RATE_LIMIT_MARKERS):
        return "rate_limit"
    return "unknown"

import os

import pytest


os.environ.setdefault("API_KEY", "secret-token-2025-test-key-long-enough")


def _clear_rate_limiter_buckets(app) -> None:
    current = getattr(app, "middleware_stack", None)
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        limiter = getattr(current, "limiter", None)
        if limiter is not None and hasattr(limiter, "_buckets"):
            limiter._buckets.clear()  # test-only reset for deterministic isolation
        current = getattr(current, "app", None)


@pytest.fixture(autouse=True)
def reset_rate_limiter_state():
    try:
        from api.main import app
        _clear_rate_limiter_buckets(app)
    except Exception:
        pass
    yield
    try:
        from api.main import app
        _clear_rate_limiter_buckets(app)
    except Exception:
        pass

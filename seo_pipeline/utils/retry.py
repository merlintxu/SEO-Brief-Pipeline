"""Retry helpers with exponential backoff and jitter."""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_call(
    fn: Callable[..., T],
    *args,
    retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float | None = None,
    jitter: float = 0.1,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception, float], None] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
    **kwargs,
) -> T:
    """Execute ``fn`` with retries using exponential backoff and jitter.

    Args:
        fn: Callable to execute.
        *args: Positional arguments passed to ``fn``.
        retries: Maximum attempts before raising the last exception.
        base_delay: Initial delay (in seconds) used for the first retry.
        max_delay: Optional cap for the computed delay.
        jitter: Proportional jitter applied to each delay. Use ``0`` to disable.
        exceptions: Exception types that trigger a retry.
        on_retry: Optional callback receiving ``(attempt, exc, delay)`` before sleeping.
        sleep_fn: Sleep function injected for tests (defaults to ``time.sleep``).
        rng: Random generator to make jitter deterministic in tests.
        **kwargs: Keyword arguments passed to ``fn``.

    Returns:
        Result of the callable.

    Raises:
        The last exception raised by ``fn`` once retries are exhausted.
    """

    if retries < 1:
        raise ValueError("retries must be >= 1")

    generator = rng or random
    attempt = 0
    last_exc: Exception | None = None

    while attempt < retries:
        try:
            return fn(*args, **kwargs)
        except exceptions as exc:  # type: ignore[misc]
            last_exc = exc
            attempt += 1

            if attempt >= retries:
                break

            delay = base_delay * (2 ** (attempt - 1))
            jitter_span = delay * jitter if jitter else 0
            jitter_offset = generator.uniform(-jitter_span, jitter_span) if jitter_span else 0
            delay_with_jitter = delay + jitter_offset
            if max_delay is not None:
                delay_with_jitter = min(delay_with_jitter, max_delay)
            delay_with_jitter = max(delay_with_jitter, 0)

            if on_retry:
                on_retry(attempt, exc, delay_with_jitter)
            sleep_fn(delay_with_jitter)

    assert last_exc is not None  # for type checkers
    raise last_exc

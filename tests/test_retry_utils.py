import random

import pytest

from seo_pipeline.utils.retry import retry_call


def test_retry_call_success_without_retries():
    calls = 0

    def fn():
        nonlocal calls
        calls += 1
        return "ok"

    result = retry_call(fn, retries=3, sleep_fn=lambda _: None, jitter=0)

    assert result == "ok"
    assert calls == 1


def test_retry_call_with_backoff_and_jitter():
    attempts = 0
    observed_delays = []

    def flaky():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("boom")
        return "done"

    rng = random.Random(42)

    result = retry_call(
        flaky,
        retries=3,
        base_delay=1,
        jitter=0.2,
        rng=rng,
        sleep_fn=lambda delay: observed_delays.append(delay),
        exceptions=(ValueError,),
        on_retry=lambda attempt, exc, delay: observed_delays.append((attempt, str(exc), delay)),
    )

    assert result == "done"
    assert attempts == 3
    # two retries -> two delay entries and two callback entries interleaved
    retry_meta = [item for item in observed_delays if isinstance(item, tuple)]
    retry_delays = [item for item in observed_delays if not isinstance(item, tuple)]

    assert retry_meta == [
        (1, "boom", pytest.approx(retry_delays[0])),
        (2, "boom", pytest.approx(retry_delays[1])),
    ]

    assert retry_delays[0] == pytest.approx(1.055, rel=1e-3)
    assert retry_delays[1] == pytest.approx(1.620, rel=1e-3)


def test_retry_call_raises_last_exception():
    def always_fails():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        retry_call(always_fails, retries=2, sleep_fn=lambda _: None, jitter=0, exceptions=(RuntimeError,))

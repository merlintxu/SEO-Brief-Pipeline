import os

os.environ["API_KEY"] = "secret-token-2025-test-key-long-enough"

from api.main import _get_job_retention_days


def test_get_job_retention_days_default(monkeypatch):
    monkeypatch.delenv("JOB_STORE_RETENTION_DAYS", raising=False)
    assert _get_job_retention_days() == 30


def test_get_job_retention_days_custom(monkeypatch):
    monkeypatch.setenv("JOB_STORE_RETENTION_DAYS", "14")
    assert _get_job_retention_days() == 14


def test_get_job_retention_days_rejects_invalid(monkeypatch):
    monkeypatch.setenv("JOB_STORE_RETENTION_DAYS", "0")
    try:
        _get_job_retention_days()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert ">= 1" in str(exc)

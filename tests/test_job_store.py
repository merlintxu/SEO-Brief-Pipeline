from pathlib import Path
from datetime import datetime, timedelta

import pytest

from api.job_store import InvalidJobTransitionError, JobStore


def test_job_store_create_and_get(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run1", "keyword one", "outputs/run1")

    job = store.get_job("run1")
    assert job is not None
    assert job.run_id == "run1"
    assert job.keyword == "keyword one"
    assert job.status == "queued"
    assert job.step == "queued"
    assert job.error_category is None
    assert job.source_run_id is None
    events = store.list_job_events("run1")
    assert len(events) == 1
    assert events[0].status == "queued"
    assert events[0].step == "queued"


def test_job_store_create_with_source_run_id(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run-retry", "keyword retry", "outputs/run-retry", source_run_id="run-parent")

    job = store.get_job("run-retry")
    assert job is not None
    assert job.source_run_id == "run-parent"


def test_job_store_update_status(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run2", "keyword two", "outputs/run2")
    store.update_status(
        "run2",
        status="failed",
        step="error",
        message="rate limited",
        error_category="rate_limit",
    )

    job = store.get_job("run2")
    assert job is not None
    assert job.status == "failed"
    assert job.step == "error"
    assert job.message == "rate limited"
    assert job.error_category == "rate_limit"
    events = store.list_job_events("run2")
    assert len(events) == 2
    assert events[0].status == "failed"
    assert events[1].status == "queued"


def test_job_store_rejects_invalid_transition(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run_invalid", "keyword", "outputs/run_invalid")
    store.update_status("run_invalid", status="running", step="start", message="started")
    store.update_status("run_invalid", status="done", step="done", message="ok")

    with pytest.raises(InvalidJobTransitionError, match="done -> running"):
        store.update_status("run_invalid", status="running", step="restart", message="restart")


def test_job_store_rejects_unknown_run_id(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    with pytest.raises(KeyError, match="not found"):
        store.update_status("missing_run", status="running", step="start", message="start")


def test_job_store_list_jobs_desc_order(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("runA", "a", "outputs/runA")
    store.create_job("runB", "b", "outputs/runB")

    jobs = store.list_jobs(limit=10)
    assert len(jobs) == 2
    assert jobs[0].run_id == "runB"
    assert jobs[1].run_id == "runA"


def test_job_store_delete_job(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run_del", "kw", "outputs/run_del")
    store.persist_run_metrics(
        "run_del",
        {
            "stages": {"briefing": {"status": "ok", "provider": "openai"}},
            "costs": {"estimates": [{"provider": "openai", "service": "briefing", "calls": 1}]},
            "prompt_run": {"key": "brief_generator", "version": "v1"},
        },
    )
    deleted = store.delete_job("run_del")
    assert deleted == 1
    assert store.get_job("run_del") is None
    assert store.list_job_events("run_del") == []
    assert store.list_stage_metrics("run_del") == []
    assert store.list_provider_calls("run_del") == []
    assert store.get_prompt_run("run_del") is None


def test_job_store_initializes_metrics_tables_idempotently(tmp_path: Path):
    db_path = tmp_path / "jobs.db"
    JobStore(db_path)
    JobStore(db_path)

    with JobStore(db_path)._connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {"job_stage_metrics", "provider_calls", "prompt_runs"} <= tables


def test_job_store_persists_run_metrics_from_payload(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run_metrics", "kw", "outputs/run_metrics")
    store.persist_run_metrics(
        "run_metrics",
        {
            "stages": {
                "semrush": {
                    "status": "ok",
                    "provider": "semrush",
                    "retries": 1,
                    "items_processed": 12,
                    "duration_seconds": 2.5,
                },
                "briefing": {
                    "status": "ok",
                    "provider": "openai",
                    "estimated_cost_usd": 0.42,
                    "total_tokens_estimated": 2100,
                },
            },
            "costs": {
                "estimates": [
                    {
                        "provider": "openai",
                        "service": "briefing",
                        "calls": 1,
                        "estimated_cost_usd": 0.42,
                        "total_tokens_estimated": 2100,
                        "notes": "estimate",
                    },
                    {
                        "provider": "serpapi",
                        "service": "search",
                        "calls": 1,
                        "notes": "plan-specific",
                    },
                ]
            },
            "prompt_run": {
                "key": "brief_generator",
                "version": "v1",
                "planner_version": "v1",
                "mode": "planner_writer",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
            },
        },
    )

    stages = store.list_stage_metrics("run_metrics")
    assert [stage.stage for stage in stages] == ["semrush", "briefing"]
    assert stages[0].provider == "semrush"
    assert stages[0].retries == 1
    assert stages[1].estimated_cost_usd == 0.42

    calls = store.list_provider_calls("run_metrics")
    assert [(call.provider, call.service) for call in calls] == [
        ("openai", "briefing"),
        ("serpapi", "search"),
    ]
    assert calls[0].total_tokens_estimated == 2100

    prompt_run = store.get_prompt_run("run_metrics")
    assert prompt_run is not None
    assert prompt_run.key == "brief_generator"
    assert prompt_run.mode == "planner_writer"
    assert prompt_run.temperature == 0.2


def test_job_store_persist_run_metrics_is_idempotent(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run_replace", "kw", "outputs/run_replace")

    store.persist_run_metrics("run_replace", {"stages": {"old": {"provider": "old"}}})
    store.persist_run_metrics(
        "run_replace",
        {
            "stages": {"new": {"provider": "new"}},
            "costs": {"estimates": [{"provider": "new", "service": "call", "calls": 2}]},
        },
    )

    assert [stage.stage for stage in store.list_stage_metrics("run_replace")] == ["new"]
    calls = store.list_provider_calls("run_replace")
    assert len(calls) == 1
    assert calls[0].calls == 2


def test_job_store_operator_audit_trail_is_append_only(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    first = store.append_operator_audit_event(
        action="cancel_confirm",
        result="confirmed",
        run_id="run_audit",
        metadata="run_id=run_audit",
    )
    second = store.append_operator_audit_event(
        action="cancel",
        result="ok",
        run_id="run_audit",
        metadata="run_id=run_audit",
    )

    assert first.id < second.id
    events = store.list_operator_audit_events(limit=10)
    assert [event.action for event in events] == ["cancel", "cancel_confirm"]
    assert events[0].run_id == "run_audit"
    assert events[0].metadata == "run_id=run_audit"


def test_job_store_cleanup_old_jobs(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run_old_done", "kw1", "outputs/run_old_done")
    store.create_job("run_new_done", "kw2", "outputs/run_new_done")
    store.create_job("run_old_running", "kw3", "outputs/run_old_running")

    store.update_status("run_old_done", status="done", step="done", message="ok")
    store.update_status("run_new_done", status="done", step="done", message="ok")
    store.update_status("run_old_running", status="running", step="serp", message="running")

    old_ts = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
    new_ts = (datetime.now() - timedelta(days=5)).isoformat(timespec="seconds")
    with store._connect() as conn:  # test-only direct timestamp setup
        conn.execute("UPDATE jobs SET updated_at = ? WHERE run_id = ?", (old_ts, "run_old_done"))
        conn.execute("UPDATE jobs SET updated_at = ? WHERE run_id = ?", (new_ts, "run_new_done"))
        conn.execute("UPDATE jobs SET updated_at = ? WHERE run_id = ?", (old_ts, "run_old_running"))
        conn.commit()

    deleted = store.cleanup_old_jobs(max_age_days=30)
    assert deleted == 1
    assert store.get_job("run_old_done") is None
    assert store.get_job("run_new_done") is not None
    assert store.get_job("run_old_running") is not None


def test_job_store_list_jobs_filter_search_and_offset(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run-1", "alpha keyword", "outputs/run-1")
    store.create_job("run-2", "beta keyword", "outputs/run-2")
    store.create_job("run-3", "alpha secondary", "outputs/run-3")
    store.update_status("run-1", status="failed", step="error", message="boom")
    store.update_status("run-2", status="done", step="done", message="ok")
    store.update_status("run-3", status="failed", step="error", message="boom")

    failed = store.list_jobs(limit=10, status="failed")
    assert {job.run_id for job in failed} == {"run-1", "run-3"}

    alpha = store.list_jobs(limit=10, search="alpha")
    assert {job.run_id for job in alpha} == {"run-1", "run-3"}

    page_1 = store.list_jobs(limit=1, offset=0)
    page_2 = store.list_jobs(limit=1, offset=1)
    assert len(page_1) == 1
    assert len(page_2) == 1
    assert page_1[0].run_id != page_2[0].run_id


def test_job_store_list_jobs_filters_error_and_created_range(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run-old-network", "alpha keyword", "outputs/run-old-network")
    store.create_job("run-new-validation", "beta keyword", "outputs/run-new-validation")
    store.update_status("run-old-network", status="failed", step="error", message="boom", error_category="network")
    store.update_status(
        "run-new-validation",
        status="failed",
        step="error",
        message="invalid",
        error_category="validation",
    )

    old_ts = (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds")
    new_ts = datetime.now().isoformat(timespec="seconds")
    with store._connect() as conn:
        conn.execute("UPDATE jobs SET created_at = ? WHERE run_id = ?", (old_ts, "run-old-network"))
        conn.execute("UPDATE jobs SET created_at = ? WHERE run_id = ?", (new_ts, "run-new-validation"))
        conn.commit()

    validation = store.list_jobs(limit=10, error_category="validation")
    assert [job.run_id for job in validation] == ["run-new-validation"]

    recent = store.list_jobs(limit=10, created_from=(datetime.now() - timedelta(days=1)).isoformat(timespec="seconds"))
    assert [job.run_id for job in recent] == ["run-new-validation"]


def test_job_store_rejects_unknown_backend(tmp_path: Path):
    with pytest.raises(RuntimeError, match="Unsupported JOB_STORE_BACKEND"):
        JobStore(tmp_path / "jobs.db", backend="unknown")


def test_job_store_postgres_scaffold_not_enabled(tmp_path: Path):
    with pytest.raises(RuntimeError, match="PostgreSQL backend scaffold"):
        JobStore(tmp_path / "jobs.db", backend="postgres")

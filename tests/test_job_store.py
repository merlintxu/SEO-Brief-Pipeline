from pathlib import Path
from datetime import datetime, timedelta

from api.job_store import JobStore


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
    deleted = store.delete_job("run_del")
    assert deleted == 1
    assert store.get_job("run_del") is None


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

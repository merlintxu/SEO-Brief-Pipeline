from datetime import datetime, timedelta
from pathlib import Path

import pytest

from api.job_lifecycle import JobLifecycleService
from api.job_store import InvalidJobTransitionError, JobStore


def test_job_lifecycle_enqueue_start_and_fail(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    service = JobLifecycleService(store)
    run_dir = tmp_path / "outputs" / "run_lifecycle"
    run_dir.mkdir(parents=True)
    status_path = run_dir / "status.json"

    service.enqueue(
        run_id="run_lifecycle",
        keyword="kw",
        output_dir=run_dir,
        status_path=status_path,
        message="queued",
    )
    assert store.get_job("run_lifecycle").status == "queued"
    assert status_path.exists()

    assert service.start("run_lifecycle") is True
    service.fail_from_exception("run_lifecycle", status_path, RuntimeError("rate limit"))

    job = store.get_job("run_lifecycle")
    assert job.status == "failed"
    assert job.step == "error"
    assert job.error_category == "rate_limit"


def test_job_lifecycle_cancel_updates_status_file(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    service = JobLifecycleService(store)
    run_dir = tmp_path / "outputs" / "run_cancel"
    run_dir.mkdir(parents=True)
    status_path = run_dir / "status.json"
    service.enqueue(run_id="run_cancel", keyword="kw", output_dir=run_dir, status_path=status_path)

    job = store.get_job("run_cancel")
    service.cancel(job)

    updated = store.get_job("run_cancel")
    assert updated.status == "failed"
    assert updated.step == "canceled"
    assert "canceled" in status_path.read_text(encoding="utf-8")

    with pytest.raises(InvalidJobTransitionError):
        service.cancel(updated)


def test_job_lifecycle_detects_stale_running_jobs(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    service = JobLifecycleService(store)
    store.create_job("run_old", "old", "outputs/run_old")
    store.create_job("run_new", "new", "outputs/run_new")
    store.update_status("run_old", status="running", step="start", message="running")
    store.update_status("run_new", status="running", step="start", message="running")

    old_ts = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
    new_ts = datetime.now().isoformat(timespec="seconds")
    with store._connect() as conn:
        conn.execute("UPDATE jobs SET updated_at = ? WHERE run_id = ?", (old_ts, "run_old"))
        conn.execute("UPDATE jobs SET updated_at = ? WHERE run_id = ?", (new_ts, "run_new"))
        conn.commit()

    stale = service.list_stale_running_jobs(max_age_minutes=60)

    assert [job.run_id for job in stale] == ["run_old"]

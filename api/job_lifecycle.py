"""Internal job lifecycle service for API queue readiness."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from api.job_store import InvalidJobTransitionError, JobRecord, JobStore
from seo_pipeline.utils.errors import classify_error
from seo_pipeline.utils.io import load_json, save_json


class JobLifecycleService:
    """Centralize job state mutations while the API still uses BackgroundTasks."""

    def __init__(self, store: JobStore):
        self.store = store

    def enqueue(
        self,
        *,
        run_id: str,
        keyword: str,
        output_dir: Path,
        status_path: Path,
        message: str = "Tarea en cola",
        source_run_id: str | None = None,
        client_id: str | None = None,
        project_id: str | None = None,
        brief_type: str | None = None,
        target_url: str | None = None,
    ) -> None:
        save_json(
            status_path,
            {
                "status": "queued",
                "step": "queued",
                "message": message,
            },
        )
        self.store.create_job(
            run_id=run_id,
            keyword=keyword,
            output_dir=str(output_dir),
            source_run_id=source_run_id,
            client_id=client_id,
            project_id=project_id,
            brief_type=brief_type,
            target_url=target_url,
        )
        self._try_update(run_id, status="queued", step="queued", message=message)

    def start(self, run_id: str) -> bool:
        return self._try_update(run_id, status="running", step="start", message="Pipeline iniciado")

    def complete_from_status(self, run_id: str, status_path: Path) -> None:
        final_status = load_json(status_path, default={})
        self.store.update_status(
            run_id,
            status=final_status.get("status", "done"),
            step=final_status.get("step", "done"),
            message=final_status.get("message", "Pipeline completado"),
            error_category=final_status.get("error_category"),
        )

    def fail_from_exception(self, run_id: str, status_path: Path, exc: Exception) -> None:
        error_category = classify_error(exc)
        save_json(
            status_path,
            {
                "status": "failed",
                "step": "error",
                "message": str(exc),
                "error_category": error_category,
            },
        )
        self._try_update(
            run_id,
            status="failed",
            step="error",
            message=str(exc),
            error_category=error_category,
        )

    def cancel(self, job: JobRecord) -> None:
        if job.status not in {"queued", "running"}:
            raise InvalidJobTransitionError("Only queued/running jobs can be canceled")
        self.store.update_status(
            job.run_id,
            status="failed",
            step="canceled",
            message="Canceled by operator",
            error_category="unknown",
        )
        status_path = Path(job.output_dir) / "status.json"
        if status_path.exists():
            save_json(
                status_path,
                {
                    "status": "failed",
                    "step": "canceled",
                    "message": "Canceled by operator",
                    "error_category": "unknown",
                },
            )

    def list_stale_running_jobs(self, *, max_age_minutes: int = 60) -> list[JobRecord]:
        if max_age_minutes < 1:
            raise ValueError("max_age_minutes must be >= 1")
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        stale: list[JobRecord] = []
        for job in self.store.list_jobs(limit=200, status="running"):
            try:
                updated_at = datetime.fromisoformat(job.updated_at)
            except ValueError:
                continue
            if updated_at < cutoff:
                stale.append(job)
        return stale

    def _try_update(
        self,
        run_id: str,
        *,
        status: str,
        step: str,
        message: str,
        error_category: str | None = None,
    ) -> bool:
        try:
            self.store.update_status(
                run_id,
                status=status,
                step=step,
                message=message,
                error_category=error_category,
            )
        except InvalidJobTransitionError:
            return False
        return True

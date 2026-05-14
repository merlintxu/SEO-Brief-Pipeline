"""Job store facade with pluggable backends (SQLite operational, PostgreSQL scaffold)."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol


class InvalidJobTransitionError(ValueError):
    """Raised when a requested job state transition is not allowed."""


@dataclass(frozen=True)
class JobRecord:
    run_id: str
    keyword: str
    status: str
    step: str
    message: str
    error_category: str | None
    output_dir: str
    source_run_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class JobEventRecord:
    id: int
    run_id: str
    status: str
    step: str
    message: str
    error_category: str | None
    created_at: str


@dataclass(frozen=True)
class OperatorAuditRecord:
    id: int
    action: str
    result: str
    run_id: str | None
    metadata: str | None
    created_at: str


@dataclass(frozen=True)
class JobStageMetricRecord:
    run_id: str
    stage: str
    status: str | None
    provider: str | None
    retries: int | None
    items_processed: int | None
    duration_seconds: float | None
    error_category: str | None
    estimated_cost_usd: float | None
    total_tokens_estimated: int | None
    created_at: str


@dataclass(frozen=True)
class ProviderCallRecord:
    id: int
    run_id: str
    provider: str
    service: str
    calls: int | None
    estimated_cost_usd: float | None
    total_tokens_estimated: int | None
    notes: str | None
    created_at: str


@dataclass(frozen=True)
class PromptRunRecord:
    run_id: str
    key: str | None
    version: str | None
    planner_version: str | None
    mode: str | None
    model: str | None
    temperature: float | None
    created_at: str


@dataclass(frozen=True)
class JobOutputRecord:
    run_id: str
    keyword: str
    briefing_json: dict[str, Any] | None
    row24_json: dict[str, Any] | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class JobArtifactRecord:
    id: int
    run_id: str
    artifact_type: str
    path: str
    created_at: str


@dataclass(frozen=True)
class BriefingRecord:
    run_id: str
    keyword: str
    h1: str | None
    meta_title: str | None
    meta_description: str | None
    model: str | None
    provider: str | None
    created_at: str


class JobStoreBackend(Protocol):
    def create_job(self, run_id: str, keyword: str, output_dir: str, *, source_run_id: str | None = None) -> None: ...
    def update_status(self, run_id: str, *, status: str, step: str, message: str, error_category: str | None = None) -> None: ...
    def get_job(self, run_id: str) -> JobRecord | None: ...
    def list_jobs(
        self,
        limit: int = 100,
        *,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        error_category: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[JobRecord]: ...
    def list_job_events(self, run_id: str, *, limit: int = 100, offset: int = 0) -> list[JobEventRecord]: ...
    def append_operator_audit_event(self, *, action: str, result: str, run_id: str | None = None, metadata: str | None = None) -> OperatorAuditRecord: ...
    def list_operator_audit_events(self, *, limit: int = 100, offset: int = 0) -> list[OperatorAuditRecord]: ...
    def persist_run_metrics(self, run_id: str, metrics: dict[str, Any]) -> None: ...
    def list_stage_metrics(self, run_id: str) -> list[JobStageMetricRecord]: ...
    def list_provider_calls(self, run_id: str) -> list[ProviderCallRecord]: ...
    def get_prompt_run(self, run_id: str) -> PromptRunRecord | None: ...
    def persist_job_output(
        self,
        run_id: str,
        *,
        keyword: str,
        briefing: dict[str, Any] | None,
        row24: dict[str, Any] | None,
        artifacts: dict[str, str],
        provider: str | None = None,
        model: str | None = None,
    ) -> None: ...
    def get_job_output(self, run_id: str) -> JobOutputRecord | None: ...
    def list_job_artifacts(self, run_id: str) -> list[JobArtifactRecord]: ...
    def get_briefing_record(self, run_id: str) -> BriefingRecord | None: ...
    def delete_job(self, run_id: str) -> int: ...
    def cleanup_old_jobs(self, *, max_age_days: int = 30, statuses: tuple[str, ...] = ("done", "failed")) -> int: ...


class SQLiteJobStoreBackend:
    ALLOWED_STATUSES = {"queued", "running", "done", "failed"}
    ALLOWED_TRANSITIONS = {
        "queued": {"queued", "running", "done", "failed"},
        "running": {"running", "done", "failed"},
        "done": {"done"},
        "failed": {"failed"},
    }

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    run_id TEXT PRIMARY KEY,
                    keyword TEXT NOT NULL,
                    status TEXT NOT NULL,
                    step TEXT NOT NULL,
                    message TEXT NOT NULL,
                    error_category TEXT,
                    output_dir TEXT NOT NULL,
                    source_run_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    step TEXT NOT NULL,
                    message TEXT NOT NULL,
                    error_category TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operator_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    run_id TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_stage_metrics (
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT,
                    provider TEXT,
                    retries INTEGER,
                    items_processed INTEGER,
                    duration_seconds REAL,
                    error_category TEXT,
                    estimated_cost_usd REAL,
                    total_tokens_estimated INTEGER,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, stage)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    service TEXT NOT NULL,
                    calls INTEGER,
                    estimated_cost_usd REAL,
                    total_tokens_estimated INTEGER,
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_runs (
                    run_id TEXT PRIMARY KEY,
                    key TEXT,
                    version TEXT,
                    planner_version TEXT,
                    mode TEXT,
                    model TEXT,
                    temperature REAL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_outputs (
                    run_id TEXT PRIMARY KEY,
                    keyword TEXT NOT NULL,
                    briefing_json TEXT,
                    row24_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS briefing_records (
                    run_id TEXT PRIMARY KEY,
                    keyword TEXT NOT NULL,
                    h1 TEXT,
                    meta_title TEXT,
                    meta_description TEXT,
                    model TEXT,
                    provider TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "source_run_id" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN source_run_id TEXT")
            conn.commit()

    def create_job(self, run_id: str, keyword: str, output_dir: str, *, source_run_id: str | None = None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (run_id, keyword, status, step, message, error_category, output_dir, source_run_id, created_at, updated_at)
                VALUES (?, ?, 'queued', 'queued', 'Tarea en cola', NULL, ?, ?, ?, ?)
                """,
                (run_id, keyword, output_dir, source_run_id, now, now),
            )
            self._insert_event(
                conn,
                run_id=run_id,
                status="queued",
                step="queued",
                message="Tarea en cola",
                error_category=None,
                created_at=now,
            )
            conn.commit()

    def update_status(
        self,
        run_id: str,
        *,
        status: str,
        step: str,
        message: str,
        error_category: str | None = None,
    ) -> None:
        if status not in self.ALLOWED_STATUSES:
            raise InvalidJobTransitionError(f"Invalid status '{status}'")

        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM jobs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(f"Run_id '{run_id}' not found")
            current_status = row["status"]
            allowed_next = self.ALLOWED_TRANSITIONS.get(current_status, set())
            if status not in allowed_next:
                raise InvalidJobTransitionError(f"Invalid transition: {current_status} -> {status}")
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, step = ?, message = ?, error_category = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, step, message, error_category, now, run_id),
            )
            self._insert_event(
                conn,
                run_id=run_id,
                status=status,
                step=step,
                message=message,
                error_category=error_category,
                created_at=now,
            )
            conn.commit()

    def get_job(self, run_id: str) -> JobRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

    def list_jobs(
        self,
        limit: int = 100,
        *,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        error_category: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[JobRecord]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if offset < 0:
            raise ValueError("offset must be >= 0")

        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("(run_id LIKE ? OR keyword LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        if error_category:
            clauses.append("error_category = ?")
            params.append(error_category)
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT *
            FROM jobs
            {where_sql}
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            OFFSET ?
        """
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_record(row) for row in rows]

    def list_job_events(self, run_id: str, *, limit: int = 100, offset: int = 0) -> list[JobEventRecord]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if offset < 0:
            raise ValueError("offset must be >= 0")

        query = """
            SELECT *
            FROM job_events
            WHERE run_id = ?
            ORDER BY id DESC
            LIMIT ?
            OFFSET ?
        """
        with self._connect() as conn:
            rows = conn.execute(query, (run_id, limit, offset)).fetchall()
            return [self._row_to_event_record(row) for row in rows]

    def append_operator_audit_event(
        self,
        *,
        action: str,
        result: str,
        run_id: str | None = None,
        metadata: str | None = None,
    ) -> OperatorAuditRecord:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO operator_audit_events (action, result, run_id, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (action, result, run_id, metadata, now),
            )
            conn.commit()
            return OperatorAuditRecord(
                id=cursor.lastrowid,
                action=action,
                result=result,
                run_id=run_id,
                metadata=metadata,
                created_at=now,
            )

    def list_operator_audit_events(self, *, limit: int = 100, offset: int = 0) -> list[OperatorAuditRecord]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if offset < 0:
            raise ValueError("offset must be >= 0")

        query = """
            SELECT *
            FROM operator_audit_events
            ORDER BY id DESC
            LIMIT ?
            OFFSET ?
        """
        with self._connect() as conn:
            rows = conn.execute(query, (limit, offset)).fetchall()
            return [self._row_to_operator_audit_record(row) for row in rows]

    def persist_run_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        if not isinstance(metrics, dict):
            raise ValueError("metrics must be a dict")
        now = datetime.now().isoformat(timespec="seconds")
        stages = metrics.get("stages", {})
        costs = metrics.get("costs", {})
        estimates = costs.get("estimates", []) if isinstance(costs, dict) else []
        prompt_run = metrics.get("prompt_run", {})

        with self._connect() as conn:
            conn.execute("DELETE FROM job_stage_metrics WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM provider_calls WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM prompt_runs WHERE run_id = ?", (run_id,))

            if isinstance(stages, dict):
                for stage_name, payload in stages.items():
                    if not isinstance(payload, dict):
                        continue
                    conn.execute(
                        """
                        INSERT INTO job_stage_metrics (
                            run_id, stage, status, provider, retries, items_processed,
                            duration_seconds, error_category, estimated_cost_usd,
                            total_tokens_estimated, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            str(stage_name),
                            _optional_str(payload.get("status")),
                            _optional_str(payload.get("provider")),
                            _optional_int(payload.get("retries")),
                            _optional_int(payload.get("items_processed")),
                            _optional_float(payload.get("duration_seconds")),
                            _optional_str(payload.get("error_category")),
                            _optional_float(payload.get("estimated_cost_usd")),
                            _optional_int(payload.get("total_tokens_estimated")),
                            now,
                        ),
                    )

            if isinstance(estimates, list):
                for estimate in estimates:
                    if not isinstance(estimate, dict):
                        continue
                    provider = _optional_str(estimate.get("provider"))
                    service = _optional_str(estimate.get("service"))
                    if not provider or not service:
                        continue
                    conn.execute(
                        """
                        INSERT INTO provider_calls (
                            run_id, provider, service, calls, estimated_cost_usd,
                            total_tokens_estimated, notes, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            provider,
                            service,
                            _optional_int(estimate.get("calls")),
                            _optional_float(estimate.get("estimated_cost_usd")),
                            _optional_int(estimate.get("total_tokens_estimated")),
                            _optional_str(estimate.get("notes")),
                            now,
                        ),
                    )

            if isinstance(prompt_run, dict) and prompt_run:
                conn.execute(
                    """
                    INSERT INTO prompt_runs (
                        run_id, key, version, planner_version, mode, model, temperature, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        _optional_str(prompt_run.get("key")),
                        _optional_str(prompt_run.get("version")),
                        _optional_str(prompt_run.get("planner_version")),
                        _optional_str(prompt_run.get("mode")),
                        _optional_str(prompt_run.get("model")),
                        _optional_float(prompt_run.get("temperature")),
                        now,
                    ),
                )
            conn.commit()

    def list_stage_metrics(self, run_id: str) -> list[JobStageMetricRecord]:
        query = """
            SELECT *
            FROM job_stage_metrics
            WHERE run_id = ?
            ORDER BY rowid ASC
        """
        with self._connect() as conn:
            rows = conn.execute(query, (run_id,)).fetchall()
            return [self._row_to_stage_metric_record(row) for row in rows]

    def list_provider_calls(self, run_id: str) -> list[ProviderCallRecord]:
        query = """
            SELECT *
            FROM provider_calls
            WHERE run_id = ?
            ORDER BY id ASC
        """
        with self._connect() as conn:
            rows = conn.execute(query, (run_id,)).fetchall()
            return [self._row_to_provider_call_record(row) for row in rows]

    def get_prompt_run(self, run_id: str) -> PromptRunRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM prompt_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_prompt_run_record(row)

    def persist_job_output(
        self,
        run_id: str,
        *,
        keyword: str,
        briefing: dict[str, Any] | None,
        row24: dict[str, Any] | None,
        artifacts: dict[str, str],
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        briefing_json = _json_dumps(briefing) if briefing is not None else None
        row24_json = _json_dumps(row24) if row24 is not None else None
        h1 = _optional_str((briefing or {}).get("h1"))
        meta_title = _optional_str((briefing or {}).get("meta_title"))
        meta_description = _optional_str((briefing or {}).get("meta_description"))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_outputs (run_id, keyword, briefing_json, row24_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    keyword = excluded.keyword,
                    briefing_json = excluded.briefing_json,
                    row24_json = excluded.row24_json,
                    updated_at = excluded.updated_at
                """,
                (run_id, keyword, briefing_json, row24_json, now, now),
            )
            conn.execute("DELETE FROM job_artifacts WHERE run_id = ?", (run_id,))
            for artifact_type, path in artifacts.items():
                conn.execute(
                    """
                    INSERT INTO job_artifacts (run_id, artifact_type, path, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (run_id, artifact_type, path, now),
                )
            conn.execute(
                """
                INSERT INTO briefing_records (
                    run_id, keyword, h1, meta_title, meta_description, model, provider, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    keyword = excluded.keyword,
                    h1 = excluded.h1,
                    meta_title = excluded.meta_title,
                    meta_description = excluded.meta_description,
                    model = excluded.model,
                    provider = excluded.provider,
                    created_at = excluded.created_at
                """,
                (run_id, keyword, h1, meta_title, meta_description, model, provider, now),
            )
            conn.commit()

    def get_job_output(self, run_id: str) -> JobOutputRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM job_outputs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_job_output_record(row)

    def list_job_artifacts(self, run_id: str) -> list[JobArtifactRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM job_artifacts WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
            return [self._row_to_job_artifact_record(row) for row in rows]

    def get_briefing_record(self, run_id: str) -> BriefingRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM briefing_records WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_briefing_record(row)

    def delete_job(self, run_id: str) -> int:
        with self._connect() as conn:
            conn.execute("DELETE FROM job_events WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM job_stage_metrics WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM provider_calls WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM prompt_runs WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM job_outputs WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM job_artifacts WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM briefing_records WHERE run_id = ?", (run_id,))
            cursor = conn.execute("DELETE FROM jobs WHERE run_id = ?", (run_id,))
            conn.commit()
            return cursor.rowcount

    def cleanup_old_jobs(self, *, max_age_days: int = 30, statuses: tuple[str, ...] = ("done", "failed")) -> int:
        if max_age_days < 1:
            raise ValueError("max_age_days must be >= 1")
        if not statuses:
            raise ValueError("statuses must not be empty")

        cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat(timespec="seconds")
        placeholders = ", ".join("?" for _ in statuses)
        query = f"""
            DELETE FROM jobs
            WHERE updated_at < ?
              AND status IN ({placeholders})
        """
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT run_id
                FROM jobs
                WHERE updated_at < ?
                  AND status IN ({placeholders})
                """,
                (cutoff, *statuses),
            ).fetchall()
            run_ids = [row["run_id"] for row in rows]
            for run_id in run_ids:
                conn.execute("DELETE FROM job_events WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM job_stage_metrics WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM provider_calls WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM prompt_runs WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM job_outputs WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM job_artifacts WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM briefing_records WHERE run_id = ?", (run_id,))
            cursor = conn.execute(query, (cutoff, *statuses))
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            run_id=row["run_id"],
            keyword=row["keyword"],
            status=row["status"],
            step=row["step"],
            message=row["message"],
            error_category=row["error_category"],
            output_dir=row["output_dir"],
            source_run_id=row["source_run_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_event_record(row: sqlite3.Row) -> JobEventRecord:
        return JobEventRecord(
            id=row["id"],
            run_id=row["run_id"],
            status=row["status"],
            step=row["step"],
            message=row["message"],
            error_category=row["error_category"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_operator_audit_record(row: sqlite3.Row) -> OperatorAuditRecord:
        return OperatorAuditRecord(
            id=row["id"],
            action=row["action"],
            result=row["result"],
            run_id=row["run_id"],
            metadata=row["metadata"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_stage_metric_record(row: sqlite3.Row) -> JobStageMetricRecord:
        return JobStageMetricRecord(
            run_id=row["run_id"],
            stage=row["stage"],
            status=row["status"],
            provider=row["provider"],
            retries=row["retries"],
            items_processed=row["items_processed"],
            duration_seconds=row["duration_seconds"],
            error_category=row["error_category"],
            estimated_cost_usd=row["estimated_cost_usd"],
            total_tokens_estimated=row["total_tokens_estimated"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_provider_call_record(row: sqlite3.Row) -> ProviderCallRecord:
        return ProviderCallRecord(
            id=row["id"],
            run_id=row["run_id"],
            provider=row["provider"],
            service=row["service"],
            calls=row["calls"],
            estimated_cost_usd=row["estimated_cost_usd"],
            total_tokens_estimated=row["total_tokens_estimated"],
            notes=row["notes"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_prompt_run_record(row: sqlite3.Row) -> PromptRunRecord:
        return PromptRunRecord(
            run_id=row["run_id"],
            key=row["key"],
            version=row["version"],
            planner_version=row["planner_version"],
            mode=row["mode"],
            model=row["model"],
            temperature=row["temperature"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_job_output_record(row: sqlite3.Row) -> JobOutputRecord:
        return JobOutputRecord(
            run_id=row["run_id"],
            keyword=row["keyword"],
            briefing_json=_json_loads(row["briefing_json"]),
            row24_json=_json_loads(row["row24_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_job_artifact_record(row: sqlite3.Row) -> JobArtifactRecord:
        return JobArtifactRecord(
            id=row["id"],
            run_id=row["run_id"],
            artifact_type=row["artifact_type"],
            path=row["path"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_briefing_record(row: sqlite3.Row) -> BriefingRecord:
        return BriefingRecord(
            run_id=row["run_id"],
            keyword=row["keyword"],
            h1=row["h1"],
            meta_title=row["meta_title"],
            meta_description=row["meta_description"],
            model=row["model"],
            provider=row["provider"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _insert_event(
        conn: sqlite3.Connection,
        *,
        run_id: str,
        status: str,
        step: str,
        message: str,
        error_category: str | None,
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO job_events (run_id, status, step, message, error_category, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, status, step, message, error_category, created_at),
        )


class PostgresJobStoreBackend:
    """Scaffold backend for future production migration."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        raise RuntimeError(
            "PostgreSQL backend scaffold is present but not enabled yet. "
            "Use JOB_STORE_BACKEND=sqlite for now."
        )

    def create_job(self, run_id: str, keyword: str, output_dir: str, *, source_run_id: str | None = None) -> None:
        raise NotImplementedError

    def update_status(
        self,
        run_id: str,
        *,
        status: str,
        step: str,
        message: str,
        error_category: str | None = None,
    ) -> None:
        raise NotImplementedError

    def get_job(self, run_id: str) -> JobRecord | None:
        raise NotImplementedError

    def list_jobs(
        self,
        limit: int = 100,
        *,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        error_category: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[JobRecord]:
        raise NotImplementedError

    def delete_job(self, run_id: str) -> int:
        raise NotImplementedError

    def list_job_events(self, run_id: str, *, limit: int = 100, offset: int = 0) -> list[JobEventRecord]:
        raise NotImplementedError

    def append_operator_audit_event(
        self,
        *,
        action: str,
        result: str,
        run_id: str | None = None,
        metadata: str | None = None,
    ) -> OperatorAuditRecord:
        raise NotImplementedError

    def list_operator_audit_events(self, *, limit: int = 100, offset: int = 0) -> list[OperatorAuditRecord]:
        raise NotImplementedError

    def persist_run_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        raise NotImplementedError

    def list_stage_metrics(self, run_id: str) -> list[JobStageMetricRecord]:
        raise NotImplementedError

    def list_provider_calls(self, run_id: str) -> list[ProviderCallRecord]:
        raise NotImplementedError

    def get_prompt_run(self, run_id: str) -> PromptRunRecord | None:
        raise NotImplementedError

    def persist_job_output(
        self,
        run_id: str,
        *,
        keyword: str,
        briefing: dict[str, Any] | None,
        row24: dict[str, Any] | None,
        artifacts: dict[str, str],
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        raise NotImplementedError

    def get_job_output(self, run_id: str) -> JobOutputRecord | None:
        raise NotImplementedError

    def list_job_artifacts(self, run_id: str) -> list[JobArtifactRecord]:
        raise NotImplementedError

    def get_briefing_record(self, run_id: str) -> BriefingRecord | None:
        raise NotImplementedError

    def cleanup_old_jobs(self, *, max_age_days: int = 30, statuses: tuple[str, ...] = ("done", "failed")) -> int:
        raise NotImplementedError


class JobStore:
    """Facade to preserve API surface while allowing backend swapping."""

    def __init__(self, db_path: Path, *, backend: str | None = None):
        backend_name = (backend or os.getenv("JOB_STORE_BACKEND", "sqlite")).strip().lower()
        if backend_name == "sqlite":
            self._backend: JobStoreBackend = SQLiteJobStoreBackend(db_path)
        elif backend_name in {"postgres", "postgresql"}:
            dsn = os.getenv("JOB_STORE_POSTGRES_DSN", "").strip()
            self._backend = PostgresJobStoreBackend(dsn)
        else:
            raise RuntimeError(f"Unsupported JOB_STORE_BACKEND: {backend_name}")

    # Kept for test compatibility with existing sqlite-based timestamp manipulation.
    def _connect(self) -> sqlite3.Connection:
        if isinstance(self._backend, SQLiteJobStoreBackend):
            return self._backend._connect()
        raise RuntimeError("_connect is only available for sqlite backend")

    def create_job(self, run_id: str, keyword: str, output_dir: str, *, source_run_id: str | None = None) -> None:
        self._backend.create_job(run_id, keyword, output_dir, source_run_id=source_run_id)

    def update_status(
        self,
        run_id: str,
        *,
        status: str,
        step: str,
        message: str,
        error_category: str | None = None,
    ) -> None:
        self._backend.update_status(run_id, status=status, step=step, message=message, error_category=error_category)

    def get_job(self, run_id: str) -> JobRecord | None:
        return self._backend.get_job(run_id)

    def list_jobs(
        self,
        limit: int = 100,
        *,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        error_category: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[JobRecord]:
        return self._backend.list_jobs(
            limit=limit,
            offset=offset,
            status=status,
            search=search,
            error_category=error_category,
            created_from=created_from,
            created_to=created_to,
        )

    def delete_job(self, run_id: str) -> int:
        return self._backend.delete_job(run_id)

    def list_job_events(self, run_id: str, *, limit: int = 100, offset: int = 0) -> list[JobEventRecord]:
        return self._backend.list_job_events(run_id, limit=limit, offset=offset)

    def append_operator_audit_event(
        self,
        *,
        action: str,
        result: str,
        run_id: str | None = None,
        metadata: str | None = None,
    ) -> OperatorAuditRecord:
        return self._backend.append_operator_audit_event(
            action=action,
            result=result,
            run_id=run_id,
            metadata=metadata,
        )

    def list_operator_audit_events(self, *, limit: int = 100, offset: int = 0) -> list[OperatorAuditRecord]:
        return self._backend.list_operator_audit_events(limit=limit, offset=offset)

    def persist_run_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        self._backend.persist_run_metrics(run_id, metrics)

    def list_stage_metrics(self, run_id: str) -> list[JobStageMetricRecord]:
        return self._backend.list_stage_metrics(run_id)

    def list_provider_calls(self, run_id: str) -> list[ProviderCallRecord]:
        return self._backend.list_provider_calls(run_id)

    def get_prompt_run(self, run_id: str) -> PromptRunRecord | None:
        return self._backend.get_prompt_run(run_id)

    def persist_job_output(
        self,
        run_id: str,
        *,
        keyword: str,
        briefing: dict[str, Any] | None,
        row24: dict[str, Any] | None,
        artifacts: dict[str, str],
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self._backend.persist_job_output(
            run_id,
            keyword=keyword,
            briefing=briefing,
            row24=row24,
            artifacts=artifacts,
            provider=provider,
            model=model,
        )

    def get_job_output(self, run_id: str) -> JobOutputRecord | None:
        return self._backend.get_job_output(run_id)

    def list_job_artifacts(self, run_id: str) -> list[JobArtifactRecord]:
        return self._backend.list_job_artifacts(run_id)

    def get_briefing_record(self, run_id: str) -> BriefingRecord | None:
        return self._backend.get_briefing_record(run_id)

    def cleanup_old_jobs(self, *, max_age_days: int = 30, statuses: tuple[str, ...] = ("done", "failed")) -> int:
        return self._backend.cleanup_old_jobs(max_age_days=max_age_days, statuses=statuses)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    import json

    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else None

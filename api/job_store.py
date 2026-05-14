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


class JobStoreBackend(Protocol):
    def create_job(self, run_id: str, keyword: str, output_dir: str, *, source_run_id: str | None = None) -> None: ...
    def update_status(self, run_id: str, *, status: str, step: str, message: str, error_category: str | None = None) -> None: ...
    def get_job(self, run_id: str) -> JobRecord | None: ...
    def list_jobs(self, limit: int = 100, *, offset: int = 0, status: str | None = None, search: str | None = None) -> list[JobRecord]: ...
    def list_job_events(self, run_id: str, *, limit: int = 100, offset: int = 0) -> list[JobEventRecord]: ...
    def append_operator_audit_event(self, *, action: str, result: str, run_id: str | None = None, metadata: str | None = None) -> OperatorAuditRecord: ...
    def list_operator_audit_events(self, *, limit: int = 100, offset: int = 0) -> list[OperatorAuditRecord]: ...
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

    def delete_job(self, run_id: str) -> int:
        with self._connect() as conn:
            conn.execute("DELETE FROM job_events WHERE run_id = ?", (run_id,))
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
    ) -> list[JobRecord]:
        return self._backend.list_jobs(limit=limit, offset=offset, status=status, search=search)

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

    def cleanup_old_jobs(self, *, max_age_days: int = 30, statuses: tuple[str, ...] = ("done", "failed")) -> int:
        return self._backend.cleanup_old_jobs(max_age_days=max_age_days, statuses=statuses)

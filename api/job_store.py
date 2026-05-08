"""SQLite-backed job metadata store for durable API run state."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JobRecord:
    run_id: str
    keyword: str
    status: str
    step: str
    message: str
    error_category: str | None
    output_dir: str
    created_at: str
    updated_at: str


class JobStore:
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create_job(self, run_id: str, keyword: str, output_dir: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (run_id, keyword, status, step, message, error_category, output_dir, created_at, updated_at)
                VALUES (?, ?, 'queued', 'queued', 'Tarea en cola', NULL, ?, ?, ?)
                """,
                (run_id, keyword, output_dir, now, now),
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
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, step = ?, message = ?, error_category = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, step, message, error_category, now, run_id),
            )
            conn.commit()

    def get_job(self, run_id: str) -> JobRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

    def list_jobs(self, limit: int = 100) -> list[JobRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]

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
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

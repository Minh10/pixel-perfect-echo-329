"""SQLite-backed metadata repository for documents and processing jobs.

SQLite in WAL mode is shared by the API process and the worker process(es) through a
common volume.  All job state transitions are single atomic UPDATE statements, so several
workers may poll the same database safely.  The repository interface is deliberately
small so it can be re-implemented on Postgres later.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    issuer          TEXT,
    period          TEXT,
    doc_type        TEXT,
    filename        TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    sha256          TEXT NOT NULL,
    page_count      INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('processing','ready','failed')),
    uploaded_at     TEXT NOT NULL,
    processed_at    TEXT,
    error_code      TEXT,
    error_message   TEXT,
    parser_json     TEXT,
    warnings_json   TEXT NOT NULL DEFAULT '[]',
    latest_job_id   TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded ON documents(uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_sha ON documents(sha256);

CREATE TABLE IF NOT EXISTS jobs (
    id                TEXT PRIMARY KEY,
    document_id       TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    state             TEXT NOT NULL CHECK (state IN ('queued','running','succeeded','failed')),
    stage             TEXT NOT NULL,
    progress          REAL NOT NULL DEFAULT 0,
    attempts          INTEGER NOT NULL DEFAULT 0,
    max_attempts      INTEGER NOT NULL,
    requested_parser  TEXT NOT NULL,
    error_code        TEXT,
    error_message     TEXT,
    worker_id         TEXT,
    created_at        TEXT NOT NULL,
    started_at        TEXT,
    finished_at       TEXT,
    heartbeat_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_state_created ON jobs(state, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_document ON jobs(document_id);
"""


def utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------ documents
    def create_document_with_job(self, doc: dict[str, Any], requested_parser: str, max_attempts: int) -> tuple[dict, dict]:
        now = utcnow()
        job_id = new_id("job")
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute(
                """INSERT INTO documents (id, title, issuer, period, doc_type, filename, size_bytes, sha256,
                       page_count, status, uploaded_at, latest_job_id)
                   VALUES (:id, :title, :issuer, :period, :doc_type, :filename, :size_bytes, :sha256,
                       :page_count, 'processing', :uploaded_at, :job_id)""",
                {**doc, "uploaded_at": _iso(now), "job_id": job_id},
            )
            self._insert_job(c, job_id, doc["id"], requested_parser, max_attempts, now)
            c.execute("COMMIT")
        return self.get_document(doc["id"]), self.get_job(job_id)  # type: ignore[return-value]

    def get_document(self, doc_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return _doc_row(row) if row else None

    def list_documents(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
        return [_doc_row(r) for r in rows]

    def delete_document(self, doc_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def mark_document_ready(self, doc_id: str, parser: dict, warnings: list[str]) -> None:
        with self._conn() as c:
            c.execute(
                """UPDATE documents SET status='ready', processed_at=?, parser_json=?, warnings_json=?,
                       error_code=NULL, error_message=NULL WHERE id=?""",
                (_iso(utcnow()), json.dumps(parser), json.dumps(warnings), doc_id),
            )

    def mark_document_failed(self, doc_id: str, code: str, message: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE documents SET status='failed', processed_at=?, error_code=?, error_message=? WHERE id=?",
                (_iso(utcnow()), code, message, doc_id),
            )

    # ------------------------------------------------------------------ jobs
    @staticmethod
    def _insert_job(c: sqlite3.Connection, job_id: str, doc_id: str, parser: str, max_attempts: int, now: datetime) -> None:
        c.execute(
            """INSERT INTO jobs (id, document_id, state, stage, progress, attempts, max_attempts,
                   requested_parser, created_at)
               VALUES (?, ?, 'queued', 'queued', 0, 0, ?, ?, ?)""",
            (job_id, doc_id, max_attempts, parser, _iso(now)),
        )

    def enqueue_job(self, doc_id: str, requested_parser: str, max_attempts: int) -> dict:
        """Queue a re-processing job.  Raises ValueError if a job is already active."""
        now = utcnow()
        job_id = new_id("job")
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            active = c.execute(
                "SELECT 1 FROM jobs WHERE document_id=? AND state IN ('queued','running')", (doc_id,)
            ).fetchone()
            if active:
                c.execute("ROLLBACK")
                raise ValueError("job_already_active")
            self._insert_job(c, job_id, doc_id, requested_parser, max_attempts, now)
            c.execute(
                """UPDATE documents SET status='processing', latest_job_id=?, error_code=NULL,
                       error_message=NULL WHERE id=?""",
                (job_id, doc_id),
            )
            c.execute("COMMIT")
        return self.get_job(job_id)  # type: ignore[return-value]

    def get_job(self, job_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def has_active_job(self, doc_id: str) -> bool:
        with self._conn() as c:
            return (
                c.execute("SELECT 1 FROM jobs WHERE document_id=? AND state='running'", (doc_id,)).fetchone()
                is not None
            )

    def claim_next_job(self, worker_id: str) -> dict | None:
        now = _iso(utcnow())
        with self._conn() as c:
            row = c.execute(
                """UPDATE jobs SET state='running', stage='inspecting', progress=0.05, worker_id=?,
                       attempts=attempts+1, started_at=?, heartbeat_at=?, error_code=NULL, error_message=NULL
                   WHERE id = (SELECT id FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1)
                     AND state='queued'
                   RETURNING *""",
                (worker_id, now, now),
            ).fetchone()
        return dict(row) if row else None

    def update_job_progress(self, job_id: str, stage: str, progress: float) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE jobs SET stage=?, progress=?, heartbeat_at=? WHERE id=? AND state='running'",
                (stage, progress, _iso(utcnow()), job_id),
            )

    def heartbeat(self, job_id: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE jobs SET heartbeat_at=? WHERE id=? AND state='running'", (_iso(utcnow()), job_id))

    def finish_job(self, job_id: str) -> None:
        now = _iso(utcnow())
        with self._conn() as c:
            c.execute(
                """UPDATE jobs SET state='succeeded', stage='done', progress=1, finished_at=?, heartbeat_at=?
                   WHERE id=?""",
                (now, now, job_id),
            )

    def fail_job(self, job_id: str, code: str, message: str, *, retry: bool) -> str:
        """Fail or re-queue a job.  Returns the resulting state."""
        now = _iso(utcnow())
        with self._conn() as c:
            row = c.execute("SELECT attempts, max_attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                return "failed"
            if retry and row["attempts"] < row["max_attempts"]:
                c.execute(
                    """UPDATE jobs SET state='queued', stage='queued', progress=0, error_code=?, error_message=?,
                           worker_id=NULL WHERE id=?""",
                    (code, message, job_id),
                )
                return "queued"
            c.execute(
                """UPDATE jobs SET state='failed', error_code=?, error_message=?, finished_at=?
                   WHERE id=?""",
                (code, message, now, job_id),
            )
            return "failed"

    def recover_stale_jobs(self, stale_after_s: float) -> list[dict]:
        """Re-queue (or fail, if out of attempts) running jobs whose worker stopped heart-beating."""
        cutoff = _iso(utcnow() - timedelta(seconds=stale_after_s))
        now = _iso(utcnow())
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            requeued = c.execute(
                """UPDATE jobs SET state='queued', stage='queued', progress=0, worker_id=NULL,
                       error_code='worker_lost', error_message='Worker heartbeat expired; job re-queued'
                   WHERE state='running' AND heartbeat_at < ? AND attempts < max_attempts
                   RETURNING *""",
                (cutoff,),
            ).fetchall()
            failed = c.execute(
                """UPDATE jobs SET state='failed', finished_at=?, error_code='worker_lost',
                       error_message='Worker heartbeat expired and max attempts reached'
                   WHERE state='running' AND heartbeat_at < ? AND attempts >= max_attempts
                   RETURNING *""",
                (now, cutoff),
            ).fetchall()
            for r in failed:
                c.execute(
                    """UPDATE documents SET status='failed', processed_at=?, error_code='worker_lost',
                           error_message='Processing worker stopped responding' WHERE id=? AND latest_job_id=?""",
                    (now, r["document_id"], r["id"]),
                )
            c.execute("COMMIT")
        return [dict(r) for r in [*requeued, *failed]]


def _doc_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["parser"] = json.loads(d.pop("parser_json")) if d.get("parser_json") else None
    d["warnings"] = json.loads(d.pop("warnings_json") or "[]")
    return d

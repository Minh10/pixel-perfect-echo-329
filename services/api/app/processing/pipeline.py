"""Execute one processing job: inspect -> parse -> assemble -> persist."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from app.config import Settings
from app.processing.assemble import assemble
from app.processing.docling_parser import ParseFailed, ParserUnavailable, parse_with_docling
from app.processing.model import RawParse
from app.processing.pymupdf_parser import inspect_pages, parse_with_pymupdf
from app.storage.db import Repository
from app.storage.files import FileStore

log = logging.getLogger("finaudit.pipeline")


class _Heartbeat:
    """Background thread that keeps a running job's heartbeat fresh during long blocking calls."""

    def __init__(self, repo: Repository, job_id: str, interval: float) -> None:
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, args=(repo, job_id, interval), daemon=True)

    def _run(self, repo: Repository, job_id: str, interval: float) -> None:
        while not self._stop.wait(interval):
            try:
                repo.heartbeat(job_id)
            except Exception:  # pragma: no cover - transient DB lock
                log.exception("heartbeat failed")

    def __enter__(self) -> _Heartbeat:
        self._t.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._t.join(timeout=5)


def _parse(requested: str, pdf, s: Settings, on_page: Callable[[int, int], None]) -> RawParse:
    if requested == "pymupdf":
        return parse_with_pymupdf(pdf)
    try:
        return parse_with_docling(pdf, s, on_page=on_page)
    except ParserUnavailable as exc:
        if requested != "auto":
            raise
        raw = parse_with_pymupdf(pdf)
        raw.warnings.insert(0, f"Docling unavailable; fell back to PyMuPDF text-layer parser. Reason: {exc}")
        return raw


def run_job(job: dict, repo: Repository, files: FileStore, s: Settings) -> None:
    job_id, doc_id = job["id"], job["document_id"]
    doc = repo.get_document(doc_id)
    if doc is None:
        repo.fail_job(job_id, "document_deleted", "Document was deleted before processing", retry=False)
        return
    if job.get("kind") == "index":
        run_index_job(job, doc, repo, files, s)
        return
    pdf = files.source_path(doc_id)
    started = time.monotonic()
    try:
        with _Heartbeat(repo, job_id, s.job_heartbeat_interval_s):
            inspections = inspect_pages(pdf)
            repo.update_job_progress(job_id, "parsing", 0.1)

            def on_page(done: int, total: int) -> None:
                repo.update_job_progress(job_id, "parsing", 0.1 + 0.75 * (done / max(total, 1)))

            raw = _parse(job["requested_parser"], pdf, s, on_page)
            repo.update_job_progress(job_id, "assembling", 0.88)
            result = assemble(raw, inspections, document_id=doc_id, job_id=job_id, sha256=doc["sha256"])
            repo.update_job_progress(job_id, "persisting", 0.95)
            if repo.get_document(doc_id) is None:
                repo.fail_job(job_id, "document_deleted", "Document was deleted during processing", retry=False)
                return
            files.clear_derived(doc_id)
            if raw.native_json:
                files.write_atomic(files.docling_path(doc_id), raw.native_json)
            files.write_atomic(files.parse_path(doc_id), result.model_dump_json())
        repo.mark_document_ready(doc_id, result.parser.model_dump(), result.warnings)
        repo.finish_job(job_id)
        if s.auto_index:
            try:
                repo.enqueue_index_job(doc_id, s.job_max_attempts)
            except ValueError:
                pass  # an index job is already queued
        log.info("job %s succeeded: %s pages, %s evidence, parser=%s, %.1fs", job_id, len(result.pages),
                 len(result.evidence), raw.parser, time.monotonic() - started)
    except ParserUnavailable as exc:
        _fail(repo, job_id, doc_id, "parser_unavailable", str(exc), retry=False)
    except ParseFailed as exc:
        _fail(repo, job_id, doc_id, "parse_failed", str(exc), retry=False)
    except Exception as exc:  # unexpected: retry up to max_attempts
        log.exception("job %s crashed", job_id)
        _fail(repo, job_id, doc_id, "internal_error", f"{type(exc).__name__}: {exc}", retry=True)


def _fail(repo: Repository, job_id: str, doc_id: str, code: str, message: str, *, retry: bool) -> None:
    state = repo.fail_job(job_id, code, message, retry=retry)
    if state == "failed":
        repo.mark_document_failed(doc_id, code, message)
    log.warning("job %s %s: %s %s", job_id, state, code, message)


def run_index_job(job: dict, doc: dict, repo: Repository, files: FileStore, s: Settings) -> None:
    from app.indexing.service import IndexError_, index_document
    from app.indexing.store import ChunkStore

    job_id = job["id"]
    if doc["status"] != "ready":
        repo.fail_job(job_id, "document_not_ready", f"Document status is {doc['status']}", retry=False)
        return
    try:
        with _Heartbeat(repo, job_id, s.job_heartbeat_interval_s):
            repo.update_job_progress(job_id, "indexing", 0.2)
            index_document(doc, files, ChunkStore(s.db_path), s)
        repo.finish_job(job_id)
    except IndexError_ as exc:
        repo.fail_job(job_id, "index_failed", str(exc), retry=False)
    except Exception as exc:
        log.exception("index job %s crashed", job_id)
        repo.fail_job(job_id, "internal_error", f"{type(exc).__name__}: {exc}", retry=True)

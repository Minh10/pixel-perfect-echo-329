"""Background worker: polls the jobs table and processes PDFs.

    python -m app.worker            # run forever
    python -m app.worker --once     # process at most one job, then exit (CI / debugging)
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import threading

from app.config import Settings, get_settings
from app.processing.pipeline import run_job
from app.storage.db import Repository
from app.storage.files import FileStore

log = logging.getLogger("finaudit.worker")


class Worker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        self.repo = Repository(self.s.db_path)
        self.files = FileStore(self.s.documents_dir)
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self._stop = threading.Event()

    def run_once(self) -> bool:
        """Recover stale jobs, then claim and run one job.  Returns True if a job was processed."""
        for j in self.repo.recover_stale_jobs(self.s.job_stale_after_s):
            log.warning("recovered stale job %s -> %s", j["id"], j["state"])
        job = self.repo.claim_next_job(self.worker_id)
        if job is None:
            return False
        log.info("claimed job %s for document %s (attempt %s)", job["id"], job["document_id"], job["attempts"])
        run_job(job, self.repo, self.files, self.s)
        return True

    def run_until_idle(self, max_jobs: int = 100) -> int:
        n = 0
        while n < max_jobs and self.run_once():
            n += 1
        return n

    def run_forever(self) -> None:
        log.info("worker %s started (parser=%s, data_dir=%s)", self.worker_id, self.s.parser, self.s.data_dir)
        while not self._stop.is_set():
            try:
                if not self.run_once():
                    self._stop.wait(self.s.worker_poll_interval_s)
            except Exception:
                log.exception("worker loop error")
                self._stop.wait(self.s.worker_poll_interval_s)
        log.info("worker stopped")

    def stop(self, *_: object) -> None:
        self._stop.set()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    w = Worker()
    if args.once:
        w.run_once()
        return
    signal.signal(signal.SIGTERM, w.stop)
    signal.signal(signal.SIGINT, w.stop)
    w.run_forever()


if __name__ == "__main__":
    main()

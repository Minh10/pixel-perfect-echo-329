import threading
from pathlib import Path

import pytest

from app.storage.db import Repository


def _doc(doc_id: str = "doc_1") -> dict:
    return {"id": doc_id, "title": "t", "issuer": None, "period": None, "doc_type": None, "filename": "f.pdf",
            "size_bytes": 10, "sha256": "a" * 64, "page_count": 2}


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "db.sqlite3")


def test_create_and_claim(repo: Repository) -> None:
    doc, job = repo.create_document_with_job(_doc(), "pymupdf", 3)
    assert doc["status"] == "processing" and doc["latest_job_id"] == job["id"]
    assert job["state"] == "queued" and job["attempts"] == 0
    claimed = repo.claim_next_job("w1")
    assert claimed["id"] == job["id"] and claimed["state"] == "running" and claimed["attempts"] == 1
    assert repo.claim_next_job("w2") is None


def test_concurrent_claims_are_exclusive(repo: Repository) -> None:
    for i in range(5):
        repo.create_document_with_job(_doc(f"doc_{i}"), "pymupdf", 3)
    got: list[str] = []
    lock = threading.Lock()

    def claim(wid: str) -> None:
        while (j := repo.claim_next_job(wid)) is not None:
            with lock:
                got.append(j["id"])

    threads = [threading.Thread(target=claim, args=(f"w{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(got) == 5 and len(set(got)) == 5


def test_retry_then_fail_after_max_attempts(repo: Repository) -> None:
    _, job = repo.create_document_with_job(_doc(), "pymupdf", 2)
    repo.claim_next_job("w")
    assert repo.fail_job(job["id"], "internal_error", "boom", retry=True) == "queued"
    repo.claim_next_job("w")
    assert repo.fail_job(job["id"], "internal_error", "boom", retry=True) == "failed"
    j = repo.get_job(job["id"])
    assert j["state"] == "failed" and j["attempts"] == 2 and j["error_code"] == "internal_error"


def test_stale_running_job_is_recovered(repo: Repository) -> None:
    _, job = repo.create_document_with_job(_doc(), "pymupdf", 1)
    repo.claim_next_job("w")
    assert repo.recover_stale_jobs(stale_after_s=3600) == []
    recovered = repo.recover_stale_jobs(stale_after_s=-1)  # every heartbeat is "stale"
    assert [r["id"] for r in recovered] == [job["id"]]
    assert repo.get_job(job["id"])["state"] == "failed"  # max_attempts=1 already used
    assert repo.get_document("doc_1")["status"] == "failed"


def test_reprocess_conflicts_with_active_job(repo: Repository) -> None:
    _, job = repo.create_document_with_job(_doc(), "pymupdf", 3)
    with pytest.raises(ValueError):
        repo.enqueue_job("doc_1", "pymupdf", 3)
    repo.claim_next_job("w")
    repo.finish_job(job["id"])
    new = repo.enqueue_job("doc_1", "docling", 3)
    assert new["requested_parser"] == "docling"
    assert repo.get_document("doc_1")["latest_job_id"] == new["id"]


def test_delete_cascades_jobs(repo: Repository) -> None:
    _, job = repo.create_document_with_job(_doc(), "pymupdf", 3)
    repo.delete_document("doc_1")
    assert repo.get_document("doc_1") is None and repo.get_job(job["id"]) is None

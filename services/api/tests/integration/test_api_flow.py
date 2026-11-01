"""End-to-end: HTTP upload -> SQLite job queue -> worker -> parsed pages/evidence/renders."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.processing import docling_parser, pipeline
from app.worker import Worker

pytestmark = pytest.mark.integration

# Keys of the frontend types in src/lib/api/types.ts that must remain present.
FIN_DOCUMENT_KEYS = {"id", "title", "issuer", "period", "type", "pages", "uploadedAt", "status", "sizeMb"}
PAGE_KEYS = {"number", "section", "blocks"}
BLOCK_KEYS = {"id", "kind"}
EVIDENCE_KEYS = {"id", "page", "blockId", "category", "label", "excerpt", "confidence", "related"}


def upload(client: TestClient, path: Path, **form) -> dict:
    with path.open("rb") as fh:
        r = client.post("/api/v1/documents", files={"file": (path.name, fh, "application/pdf")}, data=form)
    assert r.status_code == 202, r.text
    return r.json()


def test_full_ingestion_flow(client: TestClient, worker: Worker, fixtures_dir: Path) -> None:
    pdf = fixtures_dir / "annual_report_excerpt.pdf"
    body = upload(client, pdf, issuer="Fictional Example Holdings plc", period="FY2025", type="Annual Report")
    doc, job = body["document"], body["job"]
    assert FIN_DOCUMENT_KEYS <= doc.keys()
    assert doc["status"] == "processing" and doc["pages"] == 3 and doc["type"] == "Annual Report"
    assert doc["title"].startswith("Fictional Example Holdings - Annual Report 2025")  # from PDF metadata
    assert doc["sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert job["state"] == "queued" and job["requestedParser"] == "pymupdf"

    # Not ready yet: pages/evidence behave like the demo service for unparsed docs.
    r = client.get(f"/api/v1/documents/{doc['id']}/pages")
    assert r.status_code == 200 and r.json() == [] and r.headers["x-document-status"] == "processing"

    assert worker.run_until_idle() == 2  # parse job, then the automatically queued index job

    job = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert job["state"] == "succeeded" and job["stage"] == "done" and job["progress"] == 1
    assert client.get(f"/api/v1/documents/{doc['id']}/job").json()["id"] == job["id"]
    doc = client.get(f"/api/v1/documents/{doc['id']}").json()
    assert doc["status"] == "ready" and doc["parser"]["name"] == "pymupdf" and doc["processedAt"]
    assert [d["id"] for d in client.get("/api/v1/documents").json()] == [doc["id"]]

    pages = client.get(f"/api/v1/documents/{doc['id']}/pages").json()
    assert len(pages) == 3
    for p in pages:
        assert PAGE_KEYS <= p.keys()
        for b in p["blocks"]:
            assert BLOCK_KEYS <= b.keys()
            prov = b["provenance"]
            assert prov["documentId"] == doc["id"] and prov["sourceSha256"] == doc["sha256"]
            assert prov["page"] == p["number"] and prov["jobId"] == job["id"]
            assert 0 <= b["bboxNormalized"]["x"] <= 1 and b["bbox"]["coordOrigin"] == "top-left"
    table = next(b for b in pages[1]["blocks"] if b["kind"] == "table")
    assert table["table"]["columns"] == ["", "2025", "2024", "Change"]
    assert table["table"]["rows"][0] == {"label": "Revenue", "values": ["4,812", "4,281", "+12.4%"]}

    page2 = client.get(f"/api/v1/documents/{doc['id']}/pages/2").json()
    assert page2 == pages[1]

    evidence = client.get(f"/api/v1/documents/{doc['id']}/evidence").json()
    assert evidence and all(EVIDENCE_KEYS <= e.keys() for e in evidence)
    block_ids = {b["id"] for p in pages for b in p["blocks"]}
    assert all(e["blockId"] in block_ids for e in evidence)
    assert all(e["extracted"] is None and e["confidence"] is None for e in evidence)
    tables = client.get(f"/api/v1/documents/{doc['id']}/evidence", params={"category": "table"}).json()
    assert [e["category"] for e in tables] == ["table"]
    assert all(e["page"] == 3 for e in client.get(f"/api/v1/documents/{doc['id']}/evidence?page=3").json())

    # Renders come from the original PDF bytes.
    r = client.get(pages[0]["imageUrl"], params={"dpi": 72})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    pix = pymupdf.Pixmap(r.content)
    assert abs(pix.width - 595.28) <= 1 and abs(pix.height - 841.89) <= 1  # A4 at 72 dpi
    fig = next(b for b in pages[2]["blocks"] if b["kind"] == "figure")
    r = client.get(fig["figure"]["imageUrl"], params={"dpi": 72})
    crop = pymupdf.Pixmap(r.content)
    assert abs(crop.width - 400) <= 2 and abs(crop.height - 240) <= 2  # the 400x240pt chart region

    src = client.get(f"/api/v1/documents/{doc['id']}/source")
    assert src.content == pdf.read_bytes() and src.headers["x-content-sha256"] == doc["sha256"]
    assert client.get(f"/api/v1/documents/{doc['id']}/export/docling").status_code == 404  # not a Docling parse

    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 404


@pytest.mark.parametrize(
    ("name", "status", "code"),
    [("not_a_pdf.txt", 415, "not_a_pdf"), ("encrypted.pdf", 422, "encrypted_pdf"),
     ("truncated.pdf", 422, "corrupt_pdf"), ("corrupt.pdf", 422, "no_pages")],
)
def test_upload_rejections(client: TestClient, fixtures_dir: Path, name: str, status: int, code: str) -> None:
    with (fixtures_dir / name).open("rb") as fh:
        r = client.post("/api/v1/documents", files={"file": (name, fh, "application/pdf")})
    assert r.status_code == status
    assert r.json()["error"]["code"] == code
    assert client.get("/api/v1/documents").json() == []  # nothing stored or queued


def test_empty_and_oversized_uploads(client: TestClient, settings, fixtures_dir: Path) -> None:
    r = client.post("/api/v1/documents", files={"file": ("e.pdf", io.BytesIO(b""), "application/pdf")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "empty_file"
    settings.max_upload_mb = 0.001
    with (fixtures_dir / "annual_report_excerpt.pdf").open("rb") as fh:
        r = client.post("/api/v1/documents", files={"file": ("a.pdf", fh, "application/pdf")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_invalid_metadata_and_missing_resources(client: TestClient, fixtures_dir: Path) -> None:
    with (fixtures_dir / "annual_report_excerpt.pdf").open("rb") as fh:
        r = client.post("/api/v1/documents", files={"file": ("a.pdf", fh)}, data={"type": "Brochure"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    assert client.get("/api/v1/documents/doc_missing").json()["error"]["code"] == "document_not_found"
    assert client.get("/api/v1/jobs/job_missing").status_code == 404


def test_strict_docling_mode_fails_honestly_when_models_unavailable(
    client: TestClient, worker: Worker, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*_a, **_k):
        raise docling_parser.ParserUnavailable("Docling could not be initialised (simulated: no model weights)")

    monkeypatch.setattr(pipeline, "parse_with_docling", unavailable)
    with (fixtures_dir / "annual_report_excerpt.pdf").open("rb") as fh:
        body = client.post("/api/v1/documents?parser=docling", files={"file": ("a.pdf", fh)}).json()
    worker.run_until_idle()
    doc = client.get(f"/api/v1/documents/{body['document']['id']}").json()
    job = client.get(f"/api/v1/jobs/{body['job']['id']}").json()
    assert doc["status"] == "failed" and doc["error"]["code"] == "parser_unavailable"
    assert job["state"] == "failed" and job["attempts"] == 1  # configuration errors are not retried
    assert client.get(f"/api/v1/documents/{doc['id']}/pages").json() == []

    # auto mode falls back to PyMuPDF and says so on the document.
    r = client.post(f"/api/v1/documents/{doc['id']}/reprocess?parser=auto")
    assert r.status_code == 202
    worker.run_until_idle()
    doc = client.get(f"/api/v1/documents/{doc['id']}").json()
    assert doc["status"] == "ready" and doc["parser"]["name"] == "pymupdf"
    assert doc["warnings"][0].startswith("Docling unavailable; fell back to PyMuPDF")


def test_crash_is_retried_then_failed(client: TestClient, worker: Worker, fixtures_dir: Path,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(pipeline, "assemble", boom)
    with (fixtures_dir / "annual_report_excerpt.pdf").open("rb") as fh:
        body = client.post("/api/v1/documents", files={"file": ("a.pdf", fh)}).json()
    worker.run_until_idle()
    job = client.get(f"/api/v1/jobs/{body['job']['id']}").json()
    assert calls["n"] == 3 and job["attempts"] == 3 and job["state"] == "failed"
    assert job["error"]["code"] == "internal_error"
    assert client.get(f"/api/v1/documents/{body['document']['id']}").json()["status"] == "failed"


def test_health(client: TestClient) -> None:
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["doclingVersion"] and h["pymupdfVersion"]


@pytest.mark.docling_models
def test_real_docling_pipeline_on_fixture(tmp_path: Path, fixtures_dir: Path, require_docling_models) -> None:
    """Runs the actual Docling layout + TableFormer models.  Skips if weights are unavailable."""
    from app.config import Settings
    from app.main import create_app

    s = Settings(data_dir=tmp_path / "d", parser="docling")
    client, worker = TestClient(create_app(s)), Worker(s)
    body = upload(client, fixtures_dir / "annual_report_excerpt.pdf")
    worker.run_until_idle()
    doc = client.get(f"/api/v1/documents/{body['document']['id']}").json()
    assert doc["status"] == "ready", doc
    assert doc["parser"]["name"] == "docling"
    pages = client.get(f"/api/v1/documents/{doc['id']}/pages").json()
    tables = [b for b in pages[1]["blocks"] if b["kind"] == "table"]
    assert tables, "Docling should detect the ruled income-statement table"
    bb = tables[0]["bbox"]
    assert abs(bb["l"] - 72) < 10 and abs(bb["t"] - 170) < 10 and abs(bb["r"] - 522) < 10 and abs(bb["b"] - 324) < 10
    cells = {c["text"] for c in tables[0]["table"]["cells"]}
    assert {"4,812", "(3,018)", "+12.4%"} <= cells
    assert any(b["kind"] == "figure" for b in pages[2]["blocks"])
    assert client.get(f"/api/v1/documents/{doc['id']}/export/docling").status_code == 200

"""Versioned REST API (v1).  Mounted at /api/v1."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

import pymupdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app import __version__
from app.config import Settings
from app.processing.docling_parser import docling_version
from app.processing.pymupdf_parser import pymupdf_version
from app.processing.validation import ValidationError, spool_upload, validate_pdf
from app.schemas import (
    ApiError,
    DocumentPage,
    DocumentType,
    Evidence,
    FinDocument,
    Health,
    Job,
    ParseResult,
    UploadResponse,
)
from app.storage.db import Repository, new_id
from app.storage.files import FileStore

router = APIRouter()
log = logging.getLogger("finaudit.api")


# --------------------------------------------------------------------------- dependencies
def get_repo(request: Request) -> Repository:
    return request.app.state.repo


def get_files(request: Request) -> FileStore:
    return request.app.state.files


def get_cfg(request: Request) -> Settings:
    return request.app.state.settings


Repo = Annotated[Repository, Depends(get_repo)]
Files = Annotated[FileStore, Depends(get_files)]
Cfg = Annotated[Settings, Depends(get_cfg)]


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


# --------------------------------------------------------------------------- mappers
def to_document(row: dict) -> FinDocument:
    return FinDocument(
        id=row["id"], title=row["title"], issuer=row["issuer"], period=row["period"], type=row["doc_type"],
        pages=row["page_count"], uploaded_at=row["uploaded_at"], status=row["status"],
        size_mb=round(row["size_bytes"] / (1024 * 1024), 2), filename=row["filename"], sha256=row["sha256"],
        processed_at=row["processed_at"], latest_job_id=row["latest_job_id"], parser=row["parser"],
        warnings=row["warnings"],
        error=ApiError(code=row["error_code"], message=row["error_message"] or "") if row["error_code"] else None,
    )


def to_job(row: dict) -> Job:
    return Job(
        id=row["id"], document_id=row["document_id"], kind=row.get("kind", "parse"), state=row["state"],
        stage=row["stage"],
        progress=round(min(max(row["progress"], 0.0), 1.0), 3), attempts=row["attempts"],
        max_attempts=row["max_attempts"], requested_parser=row["requested_parser"],
        error=ApiError(code=row["error_code"], message=row["error_message"] or "") if row["error_code"] else None,
        created_at=row["created_at"], started_at=row["started_at"], finished_at=row["finished_at"],
        heartbeat_at=row["heartbeat_at"],
    )


def _require_doc(repo: Repository, doc_id: str) -> dict:
    row = repo.get_document(doc_id)
    if row is None:
        raise api_error(404, "document_not_found", f"Document {doc_id} not found")
    return row


def _load_parse(files: FileStore, doc_id: str) -> ParseResult | None:
    p = files.parse_path(doc_id)
    try:
        mtime = p.stat().st_mtime_ns
    except FileNotFoundError:
        return None
    return _read_parse(str(p), mtime)


@lru_cache(maxsize=32)
def _read_parse(path: str, _mtime_ns: int) -> ParseResult:
    # Keyed on mtime: a reprocess atomically replaces parse.json, which invalidates the entry.
    with open(path, encoding="utf-8") as fh:
        return ParseResult.model_validate_json(fh.read())


# --------------------------------------------------------------------------- health
@router.get("/health", response_model=Health, tags=["meta"])
def health(cfg: Cfg) -> Health:
    return Health(status="ok", version=__version__, parser=cfg.parser, docling_version=docling_version(),
                  pymupdf_version=pymupdf_version())


# --------------------------------------------------------------------------- documents
@router.post("/documents", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED, tags=["documents"])
def upload_document(
    repo: Repo, files: Files, cfg: Cfg,
    file: Annotated[UploadFile, File(description="PDF file")],
    title: Annotated[str | None, Form(max_length=300)] = None,
    issuer: Annotated[str | None, Form(max_length=300)] = None,
    period: Annotated[str | None, Form(max_length=50)] = None,
    type: Annotated[DocumentType | None, Form()] = None,  # noqa: A002 - matches frontend field name
    parser: Annotated[str | None, Query(pattern="^(docling|pymupdf|auto)$")] = None,
) -> UploadResponse:
    """Validate and store a PDF, then queue it for background processing (202 Accepted).

    Metadata fields are optional and stored exactly as supplied; nothing is inferred.  When no
    title is given we use the PDF's embedded title metadata, else the file name.
    """
    tmp_dir = cfg.data_dir / "tmp"
    try:
        tmp, size, sha = spool_upload(file.file, tmp_dir, cfg.max_upload_bytes)
        try:
            v = validate_pdf(tmp, size, sha, cfg.max_pages)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    except ValidationError as exc:
        raise api_error(exc.status_code, exc.code, exc.message) from exc

    doc_id = new_id("doc")
    filename = (file.filename or "upload.pdf").rsplit("/", 1)[-1][:255]
    files.store_source(doc_id, v.tmp_path)
    doc, job = repo.create_document_with_job(
        {
            "id": doc_id, "title": (title or v.metadata_title or filename).strip(), "issuer": issuer,
            "period": period, "doc_type": type, "filename": filename, "size_bytes": v.size_bytes,
            "sha256": v.sha256, "page_count": v.page_count,
        },
        requested_parser=parser or cfg.parser, max_attempts=cfg.job_max_attempts,
    )
    return UploadResponse(document=to_document(doc), job=to_job(job))


@router.get("/documents", response_model=list[FinDocument], tags=["documents"])
def list_documents(repo: Repo) -> list[FinDocument]:
    return [to_document(r) for r in repo.list_documents()]


@router.get("/documents/{doc_id}", response_model=FinDocument, tags=["documents"])
def get_document(doc_id: str, repo: Repo) -> FinDocument:
    return to_document(_require_doc(repo, doc_id))


@router.delete("/documents/{doc_id}", status_code=204, tags=["documents"])
def delete_document(doc_id: str, request: Request, repo: Repo, files: Files) -> Response:
    _require_doc(repo, doc_id)
    if repo.has_active_job(doc_id):
        raise api_error(409, "job_running", "Document is being processed; retry after the job finishes")
    repo.delete_document(doc_id)  # FK cascade removes chunks, FTS rows, index runs, chart readings
    files.delete(doc_id)
    try:  # vectors live in Qdrant: best effort, never blocks deletion of the source of truth
        from app.indexing.vectors import delete_document_everywhere

        delete_document_everywhere(request.app.state.settings, doc_id)
    except Exception:
        log.warning("could not delete vectors for %s", doc_id, exc_info=True)
    return Response(status_code=204)


@router.post("/documents/{doc_id}/reprocess", response_model=Job, status_code=202, tags=["documents"])
def reprocess_document(
    doc_id: str, repo: Repo, cfg: Cfg,
    parser: Annotated[str | None, Query(pattern="^(docling|pymupdf|auto)$")] = None,
) -> Job:
    _require_doc(repo, doc_id)
    try:
        return to_job(repo.enqueue_job(doc_id, parser or cfg.parser, cfg.job_max_attempts))
    except ValueError as exc:
        raise api_error(409, "job_already_active", "A job for this document is already queued or running") from exc


@router.get("/documents/{doc_id}/source", tags=["documents"])
def download_source(doc_id: str, repo: Repo, files: Files) -> FileResponse:
    row = _require_doc(repo, doc_id)
    return FileResponse(files.source_path(doc_id), media_type="application/pdf", filename=row["filename"],
                        headers={"X-Content-SHA256": row["sha256"]})


# --------------------------------------------------------------------------- jobs
@router.get("/documents/{doc_id}/job", response_model=Job, tags=["jobs"])
def get_document_job(doc_id: str, repo: Repo) -> Job:
    row = _require_doc(repo, doc_id)
    job = repo.get_job(row["latest_job_id"]) if row["latest_job_id"] else None
    if job is None:
        raise api_error(404, "job_not_found", "No job recorded for this document")
    return to_job(job)


@router.get("/jobs/{job_id}", response_model=Job, tags=["jobs"])
def get_job(job_id: str, repo: Repo) -> Job:
    job = repo.get_job(job_id)
    if job is None:
        raise api_error(404, "job_not_found", f"Job {job_id} not found")
    return to_job(job)


# --------------------------------------------------------------------------- parsed content
# Like the existing frontend demo service, pages/evidence of a document that is not `ready`
# are an empty list (200) rather than an error; `X-Document-Status` says why.
@router.get("/documents/{doc_id}/pages", response_model=list[DocumentPage], tags=["content"])
def get_pages(doc_id: str, repo: Repo, files: Files, response: Response) -> list[DocumentPage]:
    row = _require_doc(repo, doc_id)
    response.headers["X-Document-Status"] = row["status"]
    parsed = _load_parse(files, doc_id) if row["status"] == "ready" else None
    return parsed.pages if parsed else []


@router.get("/documents/{doc_id}/pages/{page_no}", response_model=DocumentPage, tags=["content"])
def get_page(doc_id: str, page_no: int, repo: Repo, files: Files) -> DocumentPage:
    row = _require_doc(repo, doc_id)
    parsed = _load_parse(files, doc_id) if row["status"] == "ready" else None
    if parsed is None:
        raise api_error(409, "document_not_ready", f"Document status is {row['status']}")
    for p in parsed.pages:
        if p.number == page_no:
            return p
    raise api_error(404, "page_not_found", f"Page {page_no} does not exist (1..{len(parsed.pages)})")


@router.get("/documents/{doc_id}/evidence", response_model=list[Evidence], tags=["content"])
def get_evidence(
    doc_id: str, repo: Repo, files: Files, response: Response,
    page: Annotated[int | None, Query(ge=1)] = None,
    category: Annotated[str | None, Query(pattern="^(disclosure|table|figure)$")] = None,
) -> list[Evidence]:
    row = _require_doc(repo, doc_id)
    response.headers["X-Document-Status"] = row["status"]
    parsed = _load_parse(files, doc_id) if row["status"] == "ready" else None
    if not parsed:
        return []
    return [e for e in parsed.evidence
            if (page is None or e.page == page) and (category is None or e.category == category)]


@router.get("/documents/{doc_id}/export/docling", tags=["content"])
def export_docling(doc_id: str, repo: Repo, files: Files) -> Response:
    _require_doc(repo, doc_id)
    p = files.docling_path(doc_id)
    if not p.exists():
        raise api_error(404, "docling_export_not_found", "No Docling output for this document (not parsed by Docling)")
    return Response(p.read_bytes(), media_type="application/json")


# --------------------------------------------------------------------------- renders
def _render(files: FileStore, doc_id: str, page_no: int, dpi: int, clip=None, cache_name: str | None = None) -> Response:
    cache = files.render_dir(doc_id) / cache_name if cache_name else None
    if cache and cache.exists():
        return Response(cache.read_bytes(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
    with pymupdf.open(files.source_path(doc_id)) as doc:
        if not 1 <= page_no <= doc.page_count:
            raise api_error(404, "page_not_found", f"Page {page_no} does not exist (1..{doc.page_count})")
        page = doc[page_no - 1]
        if clip is not None:
            # Provenance boxes are in the rotated (displayed) page frame; get_pixmap clips in the unrotated frame.
            clip = pymupdf.Rect(*clip) * page.derotation_matrix
        png = page.get_pixmap(dpi=dpi, clip=clip, alpha=False).tobytes("png")
    if cache:
        files.write_bytes_atomic(cache, png)
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/documents/{doc_id}/pages/{page_no}/image", tags=["renders"],
            responses={200: {"content": {"image/png": {}}}})
def page_image(doc_id: str, page_no: int, repo: Repo, files: Files, cfg: Cfg,
               dpi: Annotated[int | None, Query(ge=36)] = None) -> Response:
    """Render a page of the original PDF to PNG (PyMuPDF).  Use with `bboxNormalized` for overlays."""
    _require_doc(repo, doc_id)
    d = min(dpi or cfg.render_default_dpi, cfg.render_max_dpi)
    return _render(files, doc_id, page_no, d, cache_name=f"p{page_no}@{d}.png")


@router.get("/documents/{doc_id}/blocks/{block_id}/image", tags=["renders"],
            responses={200: {"content": {"image/png": {}}}})
def block_image(doc_id: str, block_id: str, repo: Repo, files: Files, cfg: Cfg,
                dpi: Annotated[int | None, Query(ge=36)] = None) -> Response:
    """Crop a block's bbox (e.g. a figure/chart or table region) from the original PDF page."""
    row = _require_doc(repo, doc_id)
    parsed = _load_parse(files, doc_id) if row["status"] == "ready" else None
    if parsed is None:
        raise api_error(409, "document_not_ready", f"Document status is {row['status']}")
    for p in parsed.pages:
        for b in p.blocks:
            if b.id == block_id:
                d = min(dpi or 150, cfg.render_max_dpi)
                bb = b.bbox
                return _render(files, doc_id, p.number, d, clip=(bb.l, bb.t, bb.r, bb.b),
                               cache_name=f"{block_id}@{d}.png")
    raise api_error(404, "block_not_found", f"Block {block_id} not found")


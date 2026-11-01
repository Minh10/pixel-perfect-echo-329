"""Synchronous upload validation.  Runs before anything is queued."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pymupdf

CHUNK = 1024 * 1024


class ValidationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedPdf:
    tmp_path: Path
    size_bytes: int
    sha256: str
    page_count: int
    metadata_title: str | None


def spool_upload(stream: BinaryIO, tmp_dir: Path, max_bytes: int) -> tuple[Path, int, str]:
    """Copy an upload stream to disk, enforcing the size limit and hashing as we go."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    fd = tempfile.NamedTemporaryFile(dir=tmp_dir, prefix="upload-", suffix=".pdf", delete=False)
    path = Path(fd.name)
    try:
        with fd:
            while chunk := stream.read(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise ValidationError(
                        "file_too_large", f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit", 413
                    )
                h.update(chunk)
                fd.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path, size, h.hexdigest()


def validate_pdf(path: Path, size: int, sha256: str, max_pages: int) -> ValidatedPdf:
    if size == 0:
        raise ValidationError("empty_file", "Uploaded file is empty", 400)
    with path.open("rb") as fh:
        head = fh.read(1024)
    # The PDF spec allows junk before the header but requires it within the first 1024 bytes.
    if b"%PDF-" not in head:
        raise ValidationError("not_a_pdf", "File is not a PDF (missing %PDF- header)", 415)
    try:
        doc = pymupdf.open(path, filetype="pdf")
    except Exception as exc:  # pymupdf raises FileDataError / RuntimeError variants
        raise ValidationError("corrupt_pdf", f"PDF could not be opened: {exc}") from exc
    try:
        if doc.needs_pass:
            raise ValidationError("encrypted_pdf", "PDF is password-protected; upload an unencrypted copy")
        if doc.page_count == 0:
            raise ValidationError("no_pages", "PDF contains no pages")
        if doc.page_count > max_pages:
            raise ValidationError("too_many_pages", f"PDF has {doc.page_count} pages; the limit is {max_pages}")
        # Touch every page once so structurally broken page trees fail now, not in the worker.
        for page in doc:
            _ = page.rect
        title = (doc.metadata or {}).get("title") or None
        return ValidatedPdf(path, size, sha256, doc.page_count, title.strip() if title else None)
    finally:
        doc.close()

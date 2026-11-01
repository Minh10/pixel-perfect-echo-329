"""Filesystem layout for document artefacts.

    {data_dir}/documents/{document_id}/
        source.pdf        original upload, byte-for-byte (sha256 recorded in DB)
        parse.json        normalised ParseResult served by the API
        docling.json      raw DoclingDocument export (only when Docling produced the parse)
        renders/          cached PNG renders (safe to delete)
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


class FileStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def doc_dir(self, doc_id: str) -> Path:
        # doc ids are generated server-side ("doc_<hex>"), but guard against traversal anyway.
        if not doc_id.replace("_", "").isalnum():
            raise ValueError("invalid document id")
        return self.root / doc_id

    def source_path(self, doc_id: str) -> Path:
        return self.doc_dir(doc_id) / "source.pdf"

    def parse_path(self, doc_id: str) -> Path:
        return self.doc_dir(doc_id) / "parse.json"

    def docling_path(self, doc_id: str) -> Path:
        return self.doc_dir(doc_id) / "docling.json"

    def render_dir(self, doc_id: str) -> Path:
        d = self.doc_dir(doc_id) / "renders"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def store_source(self, doc_id: str, tmp_file: Path) -> Path:
        dest = self.source_path(doc_id)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_file), dest)
        return dest

    def write_atomic(self, path: Path, data: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)

    def write_bytes_atomic(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)

    def clear_derived(self, doc_id: str) -> None:
        for p in (self.parse_path(doc_id), self.docling_path(doc_id)):
            p.unlink(missing_ok=True)
        shutil.rmtree(self.doc_dir(doc_id) / "renders", ignore_errors=True)

    def delete(self, doc_id: str) -> None:
        shutil.rmtree(self.doc_dir(doc_id), ignore_errors=True)

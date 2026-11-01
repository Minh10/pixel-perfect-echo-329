import io
from pathlib import Path

import pymupdf
import pytest

from app.processing.validation import ValidationError, spool_upload, validate_pdf


def _validate(data: bytes, tmp_path: Path, max_bytes: int = 10_000_000, max_pages: int = 100):
    path, size, sha = spool_upload(io.BytesIO(data), tmp_path, max_bytes)
    return validate_pdf(path, size, sha, max_pages)


def test_valid_pdf(fixtures_dir: Path, tmp_path: Path) -> None:
    data = (fixtures_dir / "annual_report_excerpt.pdf").read_bytes()
    v = _validate(data, tmp_path)
    assert v.page_count == 3
    assert v.size_bytes == len(data)
    assert len(v.sha256) == 64
    assert v.metadata_title and "synthetic fixture" in v.metadata_title


@pytest.mark.parametrize(
    ("name", "code", "status"),
    [
        ("not_a_pdf.txt", "not_a_pdf", 415),
        ("truncated.pdf", "corrupt_pdf", 422),
        ("corrupt.pdf", "no_pages", 422),
        ("encrypted.pdf", "encrypted_pdf", 422),
    ],
)
def test_rejections(fixtures_dir: Path, tmp_path: Path, name: str, code: str, status: int) -> None:
    with pytest.raises(ValidationError) as ei:
        _validate((fixtures_dir / name).read_bytes(), tmp_path)
    assert ei.value.code == code
    assert ei.value.status_code == status


def test_empty_file(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as ei:
        _validate(b"", tmp_path)
    assert ei.value.code == "empty_file"


def test_size_limit_enforced_while_streaming(fixtures_dir: Path, tmp_path: Path) -> None:
    data = (fixtures_dir / "annual_report_excerpt.pdf").read_bytes()
    with pytest.raises(ValidationError) as ei:
        spool_upload(io.BytesIO(data), tmp_path, max_bytes=1000)
    assert ei.value.code == "file_too_large" and ei.value.status_code == 413
    assert list(tmp_path.iterdir()) == []  # partial temp file removed


def test_page_limit(tmp_path: Path) -> None:
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()
    with pytest.raises(ValidationError) as ei:
        _validate(doc.tobytes(), tmp_path, max_pages=2)
    assert ei.value.code == "too_many_pages"

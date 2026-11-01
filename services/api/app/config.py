"""Runtime configuration (environment variables prefixed with FINAUDIT_)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ParserChoice = Literal["docling", "pymupdf", "auto"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINAUDIT_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=Path("./data"), description="Root for SQLite DB and document files.")
    max_upload_mb: float = 100.0
    max_pages: int = 1500

    # "docling": Docling only; job fails if Docling/models are unavailable (production default).
    # "pymupdf": deterministic text-layer parser only (no ML layout model).
    # "auto": try Docling, fall back to PyMuPDF and record a warning on the document.
    parser: ParserChoice = "docling"
    docling_do_ocr: bool = False
    docling_table_structure: bool = True
    docling_picture_classification: bool = False
    docling_num_threads: int = 4
    docling_device: str = "cpu"
    docling_document_timeout_s: float | None = 900.0
    # Directory with pre-downloaded Docling weights (`docling-tools models download -o DIR`).
    # Used only if it exists and is non-empty; otherwise Docling downloads from HuggingFace on first use.
    docling_artifacts_path: Path | None = None

    cors_origins: list[str] = ["http://localhost:8080", "http://localhost:5173", "http://localhost:3000"]

    worker_poll_interval_s: float = 1.0
    job_heartbeat_interval_s: float = 5.0
    job_stale_after_s: float = 120.0
    job_max_attempts: int = 3

    render_default_dpi: int = 110
    render_max_dpi: int = 300

    @property
    def db_path(self) -> Path:
        return self.data_dir / "finaudit.sqlite3"

    @property
    def documents_dir(self) -> Path:
        return self.data_dir / "documents"

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()

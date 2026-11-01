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

    # ---------------------------------------------------------------- indexing / retrieval (Milestone 3)
    auto_index: bool = True  # queue an index job after every successful parse
    # Embedders: onnx | wordllama | openai | sentence-transformers | none
    embedder: str = "onnx"
    embedder_model_path: Path = Path("./models/all-MiniLM-L6-v2")
    embedder_model: str | None = None          # openai / sentence-transformers model name
    embedder_base_url: str | None = None       # openai-compatible base URL, e.g. http://localhost:11434/v1
    embedder_api_key_env: str = "FINAUDIT_EMBEDDER_API_KEY"  # name of the env var holding the key
    embedder_dim: int | None = None
    embedder_max_length: int = 256
    embedder_query_prefix: str = ""            # e.g. "query: " for e5 models
    embedder_document_prefix: str = ""
    # Qdrant: server URL (recommended, required when API and worker are separate processes) or
    # embedded on-disk mode (single process only: tests, benchmark scripts).
    qdrant_url: str | None = None
    qdrant_api_key_env: str = "FINAUDIT_QDRANT_API_KEY"
    qdrant_path: Path | None = None            # default: {data_dir}/qdrant when qdrant_url is unset
    qdrant_collection_prefix: str = "finaudit"
    rrf_k: int = 60
    retrieval_candidates: int = 50             # per-method candidate depth before fusion
    # Reranker: none | cross-encoder (sentence-transformers CrossEncoder model) — off unless measured
    reranker: str = "none"
    reranker_model: str | None = None

    # ---------------------------------------------------------------- LLM (QA + chart interpretation)
    # Provider: none | anthropic | openai (any OpenAI-compatible chat endpoint, incl. vLLM/Ollama)
    llm_provider: str = "none"
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key_env: str = "FINAUDIT_LLM_API_KEY"   # name of the env var holding the key (never the key)
    llm_timeout_s: float = 120.0
    llm_max_output_tokens: int = 2048
    llm_temperature: float = 0.0               # OpenAI-compatible providers only (Claude models reject sampling params)
    llm_effort: str | None = "high"            # Anthropic output_config.effort: low|medium|high|xhigh|max
    llm_refusal_fallback: bool = True          # Anthropic server-side refusal fallback on supported models
    # Optional pricing (USD per 1M tokens) for cost reporting.  Unset -> cost reported as null.
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None
    qa_top_k: int = 8
    qa_method: str = "hybrid"                  # retrieval method used by /qa (see eval/results for evidence)
    qa_chunk_set: str = "layout"
    qa_max_evidence_chars: int = 24000

    @property
    def resolved_qdrant_path(self) -> Path:
        return self.qdrant_path or (self.data_dir / "qdrant")

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

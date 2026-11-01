from __future__ import annotations

import functools
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.worker import Worker

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_llm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Developer .env must not turn 'no provider' tests into live model calls."""
    monkeypatch.setenv("FINAUDIT_LLM_PROVIDER", "none")
    monkeypatch.setenv("FINAUDIT_LLM_MODEL", "")
    monkeypatch.setenv("FINAUDIT_LLM_BASE_URL", "")
    monkeypatch.delenv("FINAUDIT_LLM_API_KEY", raising=False)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", parser="pymupdf", job_heartbeat_interval_s=0.2)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture
def worker(settings: Settings) -> Worker:
    return Worker(settings)


@functools.cache
def docling_models_available() -> str | None:
    """Returns None if Docling can be initialised here, else the reason it cannot."""
    from app.processing.docling_parser import ParserUnavailable, get_converter

    try:
        get_converter(Settings())
    except ParserUnavailable as exc:
        return str(exc)
    return None


@pytest.fixture
def require_docling_models() -> None:
    reason = docling_models_available()
    if reason:
        pytest.skip(f"Docling models unavailable in this environment: {reason[:200]}")

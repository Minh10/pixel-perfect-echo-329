"""FastAPI application factory.

    uvicorn app.main:app --reload          # API
    python -m app.worker                   # background worker (separate process)
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1.rag_routes import router as rag_router
from app.api.v1.routes import router as v1_router
from app.config import Settings, get_settings
from app.storage.db import Repository
from app.indexing.store import ChunkStore
from app.retrieval.search import Retriever
from app.storage.files import FileStore
from app.visual.charts import ChartStore


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or get_settings()
    app = FastAPI(
        title="FINAUDIT AI API",
        version=__version__,
        description="Financial PDF ingestion, layout-aware parsing, evidence provenance, layout-aware retrieval "
        "and evidence-grounded QA. Answers are validated against cited evidence; this is not financial auditing.",
    )
    app.state.settings = s
    app.state.repo = Repository(s.db_path)
    app.state.files = FileStore(s.documents_dir)
    app.state.chunks = ChunkStore(s.db_path)
    app.state.charts = ChartStore(s.db_path)
    app.state.retriever = Retriever(s, store=app.state.chunks)  # embedder loaded lazily, cached per process

    app.add_middleware(
        CORSMiddleware, allow_origins=s.cors_origins, allow_methods=["*"], allow_headers=["*"],
        expose_headers=["X-Document-Status", "X-Content-SHA256"],
    )

    # Uniform error envelope: {"error": {"code": ..., "message": ...}}
    @app.exception_handler(HTTPException)
    async def _http_exc(_: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            body = exc.detail
        else:
            body = {"code": f"http_{exc.status_code}", "message": str(exc.detail)}
        return JSONResponse({"error": body}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "invalid_request", "message": "Request validation failed",
                       "details": jsonable_errors(exc)}},
            status_code=422,
        )

    app.include_router(v1_router, prefix="/api/v1")
    app.include_router(rag_router, prefix="/api/v1")
    return app


def jsonable_errors(exc: RequestValidationError) -> list[dict]:
    return [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = create_app()

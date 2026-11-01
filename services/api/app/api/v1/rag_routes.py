"""Milestone 3 endpoints: indexing, retrieval, evidence-grounded QA, citations, chart interpretation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.routes import Cfg, Files, Repo, _load_parse, _require_doc, api_error, to_job
from app.indexing.store import ChunkStore
from app.indexing.vectors import VectorStoreUnavailable, get_client
from app.qa.evidence import chunk_ref, ranked
from app.qa.llm import LLMError, LLMUnavailable, get_llm
from app.qa.pipeline import QAPipeline
from app.qa.schemas import (
    ChartInterpretation,
    ChunkRef,
    DocumentIndexStatus,
    IndexRun,
    QARequest,
    QAResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from app.retrieval.embeddings import EmbedderUnavailable, get_embedder
from app.retrieval.search import Retriever
from app.schemas import Job
from app.visual.charts import ChartStore, evidence_text, interpret_chart

router = APIRouter()


def get_store(request: Request) -> ChunkStore:
    return request.app.state.chunks


def get_retriever(request: Request) -> Retriever:
    return request.app.state.retriever


Store = Annotated[ChunkStore, Depends(get_store)]
Ret = Annotated[Retriever, Depends(get_retriever)]


def _titles(repo) -> dict[str, str]:
    return {d["id"]: d["title"] for d in repo.list_documents()}


# --------------------------------------------------------------------------- indexing
@router.post("/documents/{doc_id}/index", response_model=Job, status_code=status.HTTP_202_ACCEPTED, tags=["indexing"])
def reindex_document(doc_id: str, repo: Repo, cfg: Cfg) -> Job:
    """Queue (re-)indexing.  Deterministic: chunk ids are stable and previous chunks/vectors are replaced."""
    row = _require_doc(repo, doc_id)
    if row["status"] != "ready":
        raise api_error(409, "document_not_ready", f"Document status is {row['status']}")
    try:
        return to_job(repo.enqueue_index_job(doc_id, cfg.job_max_attempts))
    except ValueError as exc:
        raise api_error(409, "job_already_active", "An index job for this document is already queued or running") from exc


@router.get("/documents/{doc_id}/index", response_model=DocumentIndexStatus, tags=["indexing"])
def document_index_status(doc_id: str, repo: Repo, store: Store) -> DocumentIndexStatus:
    _require_doc(repo, doc_id)
    runs = [IndexRun(**{k: r[k] for k in ("chunk_set", "index_version", "embedder_id", "status", "chunk_count",
                                          "vector_count", "dense_status", "dense_error", "parse_job_id", "seconds",
                                          "updated_at")}) for r in store.runs(doc_id)]
    job = repo.latest_job(doc_id, "index")
    return DocumentIndexStatus(document_id=doc_id, indexed=any(r.status == "ok" for r in runs), runs=runs,
                               latest_job=to_job(job).model_dump(by_alias=True) if job else None)


@router.get("/index/status", tags=["indexing"])
def index_status(repo: Repo, store: Store, cfg: Cfg) -> dict:
    """Configuration and health of the retrieval/QA stack.  Never returns secrets."""
    try:
        emb = get_embedder(cfg)
        embedder = {"backend": cfg.embedder, "id": emb.id if emb else None, "available": emb is not None, "error": None}
    except EmbedderUnavailable as exc:
        embedder = {"backend": cfg.embedder, "id": None, "available": False, "error": str(exc)}
    try:
        get_client(cfg)
        vstore = {"mode": "server" if cfg.qdrant_url else "embedded", "available": True, "error": None}
    except VectorStoreUnavailable as exc:
        vstore = {"mode": "server" if cfg.qdrant_url else "embedded", "available": False, "error": str(exc)}
    try:
        llm = get_llm(cfg)
        llm_state = {"provider": cfg.llm_provider, "model": llm.model, "available": True, "error": None}
    except LLMUnavailable as exc:
        llm_state = {"provider": cfg.llm_provider, "model": cfg.llm_model, "available": False, "error": str(exc)}
    return {"embedder": embedder, "vectorStore": vstore, "llm": llm_state, "reranker": cfg.reranker,
            "qaRetrieval": {"method": cfg.qa_method, "chunkSet": cfg.qa_chunk_set, "topK": cfg.qa_top_k},
            "chunks": {"layout": store.count(chunk_set="layout"), "flat": store.count(chunk_set="flat")},
            "documentsIndexed": len({r["document_id"] for r in store.runs() if r["status"] == "ok"})}


# --------------------------------------------------------------------------- retrieval
@router.post("/retrieve", response_model=RetrieveResponse, tags=["retrieval"])
def retrieve(body: RetrieveRequest, repo: Repo, store: Store, retriever: Ret) -> RetrieveResponse:
    res = retriever.search(body.query, method=body.method, chunk_set=body.chunk_set, document_ids=body.document_ids,
                           k=body.k, rerank=body.rerank)
    rows = store.get(h.chunk_id for h in res.hits)
    return RetrieveResponse(query=body.query, method=body.method, effective_method=res.effective_method,
                            chunk_set=body.chunk_set, embedder_id=res.embedder_id, reranker=res.reranker,
                            warnings=res.warnings, timings_ms=res.timings_ms, results=ranked(res, rows, _titles(repo)))


@router.get("/citations/{chunk_id}", response_model=ChunkRef, tags=["retrieval"])
def citation(chunk_id: str, repo: Repo, store: Store) -> ChunkRef:
    """Full detail for a cited evidence chunk: text, section, exact page/block/bbox regions, image URLs."""
    row = store.get([chunk_id]).get(chunk_id)
    if row is None:
        raise api_error(404, "citation_not_found", f"Evidence chunk {chunk_id} not found (deleted or re-indexed?)")
    return chunk_ref(row, _titles(repo))


# --------------------------------------------------------------------------- QA
@router.post("/qa", response_model=QAResponse, tags=["qa"],
             responses={503: {"description": "No LLM provider configured or reachable"}})
def qa(body: QARequest, request: Request, repo: Repo, store: Store, retriever: Ret, cfg: Cfg) -> QAResponse:
    try:
        llm = get_llm(cfg)
    except LLMUnavailable as exc:
        raise api_error(503, "llm_unavailable", str(exc)) from exc
    charts: ChartStore = request.app.state.charts

    def visual(doc_id: str, block_id: str | None) -> str | None:
        ci = charts.get(doc_id, block_id) if block_id else None
        return evidence_text(ci) if ci else None

    pipe = QAPipeline(cfg, store, retriever, llm, repo.list_documents(), visual_lookup=visual)
    try:
        return pipe.answer(body)
    except LLMUnavailable as exc:
        raise api_error(503, "llm_unavailable", str(exc)) from exc
    except LLMError as exc:
        raise api_error(502, exc.code, str(exc)) from exc


# --------------------------------------------------------------------------- charts (visual extension)
def _figure_block(files, doc_id: str, block_id: str):
    parsed = _load_parse(files, doc_id)
    if parsed is None:
        raise api_error(409, "document_not_ready", "Document has no parse result")
    for p in parsed.pages:
        for b in p.blocks:
            if b.id == block_id:
                if b.kind != "figure":
                    raise api_error(422, "not_a_figure", f"Block {block_id} is a {b.kind}, not a figure")
                ctx = " ".join(x.text or "" for x in p.blocks if x.kind == "paragraph")[:800]
                return p.number, b, (b.figure.caption if b.figure and b.figure.caption else "") + " " + ctx
    raise api_error(404, "block_not_found", f"Block {block_id} not found")


@router.get("/documents/{doc_id}/figures/{block_id}/interpretation", response_model=ChartInterpretation, tags=["visual"])
def get_chart_interpretation(doc_id: str, block_id: str, request: Request, repo: Repo) -> ChartInterpretation:
    _require_doc(repo, doc_id)
    ci = request.app.state.charts.get(doc_id, block_id)
    if ci is None:
        raise api_error(404, "interpretation_not_found", "Chart has not been interpreted; POST to .../interpret")
    return ci


@router.post("/documents/{doc_id}/figures/{block_id}/interpret", response_model=ChartInterpretation, tags=["visual"],
             responses={503: {"description": "No vision-capable LLM provider configured"}})
def interpret_figure(doc_id: str, block_id: str, request: Request, repo: Repo, files: Files, store: Store, cfg: Cfg,
                     refresh: Annotated[bool, Query()] = False) -> ChartInterpretation:
    """Read a chart with the configured vision-language model.  All values are visual estimates and are
    cross-checked against the document's table evidence."""
    _require_doc(repo, doc_id)
    charts: ChartStore = request.app.state.charts
    if not refresh and (ci := charts.get(doc_id, block_id)):
        return ci
    page_no, block, context = _figure_block(files, doc_id, block_id)
    try:
        llm = get_llm(cfg)
        ci = interpret_chart(doc_id, {"id": block.id, "bbox": block.bbox.model_dump()}, page_no,
                             files.source_path(doc_id), llm, store, context)
    except LLMUnavailable as exc:
        raise api_error(503, "llm_unavailable", str(exc)) from exc
    except LLMError as exc:
        raise api_error(502, exc.code, str(exc)) from exc
    charts.put(ci)
    return ci

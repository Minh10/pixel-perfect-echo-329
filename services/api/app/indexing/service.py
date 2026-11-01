"""Index a parsed document: chunk (layout + flat) -> structured store/BM25 -> embeddings -> Qdrant.

Deterministic: chunk ids are content/position hashes, every write replaces the document's previous
chunks/vectors for that chunk set, so re-indexing yields identical ids and never duplicates evidence.
Graceful: if the embedder or Qdrant is unavailable, BM25 indexing still completes and the run records
dense_status="unavailable" with the reason; dense/hybrid retrieval then reports the degradation.
"""

from __future__ import annotations

import logging
import time

from app.config import Settings
from app.indexing.chunker import CHUNKER_VERSION, FLAT_CHUNKER_VERSION, Chunk, DocMeta, chunk_flat, chunk_layout
from app.indexing.store import ChunkStore
from app.indexing.vectors import VectorIndex, VectorStoreUnavailable
from app.retrieval.embeddings import EmbedderUnavailable, get_embedder
from app.schemas import ParseResult
from app.storage.files import FileStore

log = logging.getLogger("finaudit.indexing")
CHUNK_SETS = ("layout", "flat")
VERSIONS = {"layout": CHUNKER_VERSION, "flat": FLAT_CHUNKER_VERSION}


class IndexError_(RuntimeError):
    pass


def doc_meta(doc: dict, parse: ParseResult) -> DocMeta:
    return DocMeta(document_id=doc["id"], title=doc["title"], company=doc["issuer"], period=doc["period"],
                   doc_type=doc["doc_type"], source_sha256=doc["sha256"], parser=parse.parser.name,
                   parser_version=parse.parser.version, parse_job_id=parse.job_id)


def build_chunks(doc: dict, parse: ParseResult, files: FileStore, chunk_set: str) -> list[Chunk]:
    meta = doc_meta(doc, parse)
    return chunk_layout(parse, meta) if chunk_set == "layout" else chunk_flat(files.source_path(doc["id"]), meta)


def index_document(doc: dict, files: FileStore, store: ChunkStore, s: Settings,
                   chunk_sets: tuple[str, ...] = CHUNK_SETS) -> dict[str, dict]:
    p = files.parse_path(doc["id"])
    if not p.exists():
        raise IndexError_("document has no parse result; parse it first")
    parse = ParseResult.model_validate_json(p.read_text(encoding="utf-8"))
    prov = {"source_sha256": doc["sha256"], "parser": parse.parser.name, "parser_version": parse.parser.version,
            "parse_job_id": parse.job_id}
    try:
        embedder = get_embedder(s)
        emb_error = None if embedder else "dense retrieval disabled (FINAUDIT_EMBEDDER=none)"
    except EmbedderUnavailable as exc:
        embedder, emb_error = None, str(exc)
    report: dict[str, dict] = {}
    for cs in chunk_sets:
        t0 = time.monotonic()
        chunks = build_chunks(doc, parse, files, cs)
        version = VERSIONS[cs]
        store.replace_document_chunks(doc["id"], cs, version, chunks, prov)
        n_vec, dense_status, dense_error = 0, "unavailable", emb_error
        if embedder is not None:
            try:
                vi = VectorIndex(s, cs, embedder.id, embedder.dim)
                vecs = embedder.embed_documents([c.search_text for c in chunks])
                n_vec = vi.replace_document(doc["id"], [c.chunk_id for c in chunks], vecs,
                                            [{"kind": c.kind, "page": c.pages[0], "chunk_set": cs} for c in chunks])
                dense_status, dense_error = "ok", None
            except (VectorStoreUnavailable, EmbedderUnavailable) as exc:
                dense_error = str(exc)
        secs = round(time.monotonic() - t0, 2)
        run = {"index_version": version, "embedder_id": embedder.id if embedder else None, "status": "ok",
               "chunk_count": len(chunks), "vector_count": n_vec, "dense_status": dense_status,
               "dense_error": dense_error, "parse_job_id": parse.job_id, "seconds": secs}
        store.set_run(doc["id"], cs, **run)
        report[cs] = run
        log.info("indexed %s/%s: %d chunks, %d vectors (%s) in %.1fs", doc["id"], cs, len(chunks), n_vec,
                 dense_status, secs)
    return report

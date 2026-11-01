"""Retrieval: BM25 (SQLite FTS5), dense (Qdrant), hybrid (reciprocal rank fusion), optional reranking.

Named configurations (the milestone baselines; all other combinations are available as ablations):
    B1  bm25   over flat page-window chunks      (text-only lexical)
    B2  dense  over flat page-window chunks      (semantic)
    B3  bm25   over layout chunks                (layout-aware: sections + structured tables/figures)
    B4  hybrid over layout chunks (BM25 + dense, RRF)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.config import Settings
from app.indexing.store import ChunkStore
from app.indexing.vectors import VectorIndex, VectorStoreUnavailable
from app.retrieval.embeddings import Embedder, EmbedderUnavailable, get_embedder

Method = Literal["bm25", "dense", "hybrid"]
ChunkSet = Literal["layout", "flat"]

BASELINES: dict[str, tuple[Method, ChunkSet]] = {
    "B1": ("bm25", "flat"),
    "B2": ("dense", "flat"),
    "B3": ("bm25", "layout"),
    "B4": ("hybrid", "layout"),
    # ablations
    "A-dense-layout": ("dense", "layout"),
    "A-hybrid-flat": ("hybrid", "flat"),
}


@dataclass
class Hit:
    chunk_id: str
    score: float
    rank: int
    method_scores: dict[str, float] = field(default_factory=dict)
    method_ranks: dict[str, int] = field(default_factory=dict)
    rerank_score: float | None = None


@dataclass
class SearchResult:
    hits: list[Hit]
    method: str
    chunk_set: str
    effective_method: str
    warnings: list[str]
    timings_ms: dict[str, float]
    embedder_id: str | None
    reranker: str | None = None


class Reranker(Protocol):
    id: str

    def score(self, query: str, texts: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    """sentence-transformers CrossEncoder (e.g. a BGE / MS MARCO reranker).  Optional dependency."""

    def __init__(self, model: str) -> None:
        try:
            from sentence_transformers import CrossEncoder

            self._m = CrossEncoder(model, device="cpu")
        except Exception as exc:
            raise EmbedderUnavailable(f"reranker {model!r} unavailable: {exc}") from exc
        self.id = f"cross-encoder-{model.replace('/', '_')}"

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(x) for x in self._m.predict([(query, t) for t in texts])]


def get_reranker(s: Settings) -> Reranker | None:
    if s.reranker == "none":
        return None
    if s.reranker == "cross-encoder" and s.reranker_model:
        return CrossEncoderReranker(s.reranker_model)
    raise EmbedderUnavailable(f"unknown reranker configuration {s.reranker!r}")


def rrf(rankings: dict[str, list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal rank fusion (Cormack et al., 2009): score(d) = sum_m 1 / (k + rank_m(d))."""
    scores: dict[str, float] = {}
    for ranked in rankings.values():
        for r, cid in enumerate(ranked, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + r)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


class Retriever:
    def __init__(self, s: Settings, store: ChunkStore | None = None, embedder: Embedder | None = None,
                 reranker: Reranker | None = None) -> None:
        self.s = s
        self.store = store or ChunkStore(s.db_path)
        self._embedder = embedder
        self._embedder_error: str | None = None
        self.reranker = reranker

    def embedder(self) -> Embedder | None:
        if self._embedder is None and self._embedder_error is None:
            try:
                self._embedder = get_embedder(self.s)
                if self._embedder is None:
                    self._embedder_error = "dense retrieval disabled (FINAUDIT_EMBEDDER=none)"
            except EmbedderUnavailable as exc:
                self._embedder_error = str(exc)
        return self._embedder

    def _dense(self, query: str, chunk_set: str, doc_ids: list[str] | None, n: int,
               warnings: list[str], timings: dict[str, float]) -> list[tuple[str, float]] | None:
        emb = self.embedder()
        if emb is None:
            warnings.append(f"dense retrieval unavailable: {self._embedder_error}")
            return None
        t = time.perf_counter()
        qv = emb.embed_query(query)
        timings["embed_query_ms"] = (time.perf_counter() - t) * 1000
        try:
            t = time.perf_counter()
            res = VectorIndex(self.s, chunk_set, emb.id, emb.dim).search(qv, doc_ids, n)
            timings["dense_ms"] = (time.perf_counter() - t) * 1000
        except VectorStoreUnavailable as exc:
            warnings.append(f"vector store unavailable: {exc}")
            return None
        return res

    def search(self, query: str, *, method: Method = "hybrid", chunk_set: ChunkSet = "layout",
               document_ids: list[str] | None = None, k: int = 10, rerank: bool = False,
               rerank_depth: int = 30) -> SearchResult:
        t0 = time.perf_counter()
        warnings: list[str] = []
        timings: dict[str, float] = {}
        depth = max(self.s.retrieval_candidates, k, rerank_depth if rerank else 0)
        per_method: dict[str, list[tuple[str, float]]] = {}
        if method in ("bm25", "hybrid"):
            t = time.perf_counter()
            per_method["bm25"] = self.store.bm25(query, chunk_set, document_ids, depth)
            timings["bm25_ms"] = (time.perf_counter() - t) * 1000
        if method in ("dense", "hybrid"):
            dense = self._dense(query, chunk_set, document_ids, depth, warnings, timings)
            if dense is not None:
                per_method["dense"] = dense
            elif method == "dense":  # never return zero evidence just because the embedder is down
                t = time.perf_counter()
                per_method["bm25"] = self.store.bm25(query, chunk_set, document_ids, depth)
                timings["bm25_ms"] = (time.perf_counter() - t) * 1000
                warnings.append("dense degraded to bm25 only")
        effective = "+".join(sorted(per_method)) or "none"
        if method == "hybrid" and len(per_method) == 2:
            fused = rrf({m: [c for c, _ in r] for m, r in per_method.items()}, self.s.rrf_k)
        elif per_method:
            fused = next(iter(per_method.values()))
            if method == "hybrid":
                warnings.append(f"hybrid degraded to {effective} only")
        else:
            fused = []
        hits: list[Hit] = []
        lookup = {m: {c: (r, sc) for r, (c, sc) in enumerate(res, start=1)} for m, res in per_method.items()}
        for r, (cid, sc) in enumerate(fused[:depth], start=1):
            hits.append(Hit(chunk_id=cid, score=sc, rank=r,
                            method_scores={m: lookup[m][cid][1] for m in lookup if cid in lookup[m]},
                            method_ranks={m: lookup[m][cid][0] for m in lookup if cid in lookup[m]}))
        reranker_id = None
        if rerank:
            if self.reranker is None:
                warnings.append("reranking requested but no reranker is configured (FINAUDIT_RERANKER)")
            else:
                t = time.perf_counter()
                cand = hits[:rerank_depth]
                texts = self.store.get(h.chunk_id for h in cand)
                scores = self.reranker.score(query, [texts[h.chunk_id]["search_text"] for h in cand])
                for h, sc in zip(cand, scores, strict=True):
                    h.rerank_score = sc
                cand.sort(key=lambda h: -(h.rerank_score or 0.0))
                hits = cand + hits[rerank_depth:]
                for i, h in enumerate(hits, start=1):
                    h.rank = i
                timings["rerank_ms"] = (time.perf_counter() - t) * 1000
                reranker_id = self.reranker.id
        timings["total_ms"] = (time.perf_counter() - t0) * 1000
        emb = self._embedder
        return SearchResult(hits=hits[:k], method=method, chunk_set=chunk_set, effective_method=effective,
                            warnings=warnings, timings_ms={k_: round(v, 2) for k_, v in timings.items()},
                            embedder_id=emb.id if emb and "dense" in per_method else None, reranker=reranker_id)

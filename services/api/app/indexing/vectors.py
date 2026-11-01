"""Qdrant vector index.  Vectors + minimal payload only; metadata stays in the structured store.

One collection per (chunk set, embedder id), so vectors from different models are never mixed and an
embedder change is an explicit re-index.  Point ids are UUIDv5(chunk_id): upserts are idempotent.
"""

from __future__ import annotations

import atexit
import os
import re
import threading
import uuid

import numpy as np

from app.config import Settings

NAMESPACE = uuid.UUID("6f1f3c56-7d0e-4f53-9a0c-3c6c3e7b1a10")
_clients: dict[str, object] = {}
_lock = threading.Lock()


class VectorStoreUnavailable(RuntimeError):
    pass


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE, chunk_id))


def collection_name(s: Settings, chunk_set: str, embedder_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", f"{s.qdrant_collection_prefix}_{chunk_set}_{embedder_id}")[:200]


def get_client(s: Settings):
    from qdrant_client import QdrantClient

    key = s.qdrant_url or str(s.resolved_qdrant_path)
    with _lock:
        if key not in _clients:
            try:
                if s.qdrant_url:
                    _clients[key] = QdrantClient(url=s.qdrant_url, api_key=os.environ.get(s.qdrant_api_key_env),
                                                 timeout=30)
                else:
                    s.resolved_qdrant_path.mkdir(parents=True, exist_ok=True)
                    _clients[key] = QdrantClient(path=str(s.resolved_qdrant_path))
            except Exception as exc:  # e.g. embedded storage locked by another process
                raise VectorStoreUnavailable(f"Qdrant unavailable ({type(exc).__name__}: {exc})") from exc
        return _clients[key]


@atexit.register
def close_clients() -> None:
    with _lock:
        for c in _clients.values():
            try:
                c.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        _clients.clear()


class VectorIndex:
    def __init__(self, s: Settings, chunk_set: str, embedder_id: str, dim: int) -> None:
        self.client = get_client(s)
        self.name = collection_name(s, chunk_set, embedder_id)
        self.dim = dim

    def ensure(self) -> None:
        from qdrant_client import models

        if not self.client.collection_exists(self.name):
            self.client.create_collection(
                self.name, vectors_config=models.VectorParams(size=self.dim, distance=models.Distance.COSINE))
            self.client.create_payload_index(self.name, "document_id", models.PayloadSchemaType.KEYWORD)

    def replace_document(self, document_id: str, chunk_ids: list[str], vectors: np.ndarray, payloads: list[dict]) -> int:
        from qdrant_client import models

        self.ensure()
        self.delete_document(document_id)
        points = [models.PointStruct(id=point_id(cid), vector=vec.tolist(), payload={**p, "chunk_id": cid,
                                                                                     "document_id": document_id})
                  for cid, vec, p in zip(chunk_ids, vectors, payloads, strict=True)]
        for i in range(0, len(points), 256):
            self.client.upsert(self.name, points=points[i:i + 256], wait=True)
        return len(points)

    def delete_document(self, document_id: str) -> None:
        from qdrant_client import models

        if not self.client.collection_exists(self.name):
            return
        self.client.delete(self.name, points_selector=models.FilterSelector(filter=models.Filter(
            must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))])), wait=True)

    def count(self, document_id: str | None = None) -> int:
        from qdrant_client import models

        if not self.client.collection_exists(self.name):
            return 0
        flt = None
        if document_id:
            flt = models.Filter(must=[models.FieldCondition(key="document_id",
                                                            match=models.MatchValue(value=document_id))])
        return int(self.client.count(self.name, count_filter=flt, exact=True).count)

    def search(self, vector: np.ndarray, document_ids: list[str] | None, limit: int) -> list[tuple[str, float]]:
        from qdrant_client import models

        if not self.client.collection_exists(self.name):
            return []
        flt = None
        if document_ids:
            flt = models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchAny(any=document_ids))])
        res = self.client.query_points(self.name, query=vector.tolist(), query_filter=flt, limit=limit,
                                       with_payload=["chunk_id"])
        return [(p.payload["chunk_id"], float(p.score)) for p in res.points]


def delete_document_everywhere(s: Settings, document_id: str) -> None:
    """Remove a document's vectors from every FINAUDIT collection (any chunk set / embedder)."""
    client = get_client(s)
    from qdrant_client import models

    for col in client.get_collections().collections:
        if col.name.startswith(s.qdrant_collection_prefix + "_"):
            client.delete(col.name, points_selector=models.FilterSelector(filter=models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))])),
                wait=True)

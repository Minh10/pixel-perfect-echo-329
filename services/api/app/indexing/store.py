"""Structured chunk store (SQLite) with an FTS5 BM25 index.

Chunk metadata and provenance live here (the "structured store"); Qdrant only holds vectors + ids.
BM25 uses SQLite FTS5's built-in bm25() (k1=1.2, b=0.75) over text produced by `analyze()`, a
financial-aware analyzer: lower-case, Porter-stemmed (FTS5 `porter` tokenizer), thousands separators
removed ("1,577" -> "1577") and decimals kept as one token ("12.4" -> "12_4").
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.indexing.chunker import BlockRef, Chunk

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id         TEXT PRIMARY KEY,
    document_id      TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_set        TEXT NOT NULL,
    kind             TEXT NOT NULL,
    index_version    TEXT NOT NULL,
    company          TEXT,
    period           TEXT,
    pages_json       TEXT NOT NULL,
    page_first       INTEGER NOT NULL,
    section_json     TEXT NOT NULL,
    content          TEXT NOT NULL,
    search_text      TEXT NOT NULL,
    blocks_json      TEXT NOT NULL,
    meta_json        TEXT NOT NULL,
    ordinal          INTEGER NOT NULL,
    source_sha256    TEXT NOT NULL,
    parser           TEXT NOT NULL,
    parser_version   TEXT NOT NULL,
    parse_job_id     TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_set ON chunks(document_id, chunk_set);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED, document_id UNINDEXED, chunk_set UNINDEXED, tokens,
    tokenize = "porter unicode61 tokenchars '_'"
);
CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON chunks BEGIN
    DELETE FROM chunks_fts WHERE chunk_id = old.chunk_id;
END;
CREATE TABLE IF NOT EXISTS index_runs (
    document_id      TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_set        TEXT NOT NULL,
    index_version    TEXT NOT NULL,
    embedder_id      TEXT,
    status           TEXT NOT NULL,
    chunk_count      INTEGER NOT NULL DEFAULT 0,
    vector_count     INTEGER NOT NULL DEFAULT 0,
    dense_status     TEXT NOT NULL,
    dense_error      TEXT,
    parse_job_id     TEXT,
    seconds          REAL,
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (document_id, chunk_set)
);
"""

_NUM_SEP = re.compile(r"(?<=\d),(?=\d{3}\b)")
_DEC = re.compile(r"(?<=\d)\.(?=\d)")
_NON_TOKEN = re.compile(r"[^\w]+", re.UNICODE)


def analyze(text: str) -> str:
    """Normalise text for BM25 (applied identically to documents and queries)."""
    t = _NUM_SEP.sub("", text.lower())
    t = _DEC.sub("_", t)
    return " ".join(tok for tok in _NON_TOKEN.split(t) if tok)


def fts_query(text: str) -> str | None:
    toks = list(dict.fromkeys(analyze(text).split()))
    return " OR ".join(f'"{t}"' for t in toks) if toks else None


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ChunkStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------ writes
    def replace_document_chunks(self, document_id: str, chunk_set: str, index_version: str, chunks: list[Chunk],
                                prov: dict) -> None:
        """Atomically replace all chunks of (document, chunk_set): re-indexing never duplicates."""
        now = _now()
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("DELETE FROM chunks WHERE document_id=? AND chunk_set=?", (document_id, chunk_set))
            for ch in chunks:
                c.execute(
                    """INSERT INTO chunks (chunk_id, document_id, chunk_set, kind, index_version, company, period,
                           pages_json, page_first, section_json, content, search_text, blocks_json, meta_json,
                           ordinal, source_sha256, parser, parser_version, parse_job_id, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (ch.chunk_id, document_id, chunk_set, ch.kind, index_version, ch.company, ch.period,
                     json.dumps(ch.pages), ch.pages[0], json.dumps(ch.section_path), ch.content, ch.search_text,
                     json.dumps([b.to_dict() for b in ch.blocks]), json.dumps(ch.meta), ch.ordinal,
                     prov["source_sha256"], prov["parser"], prov["parser_version"], prov["parse_job_id"], now),
                )
                c.execute("INSERT INTO chunks_fts (chunk_id, document_id, chunk_set, tokens) VALUES (?,?,?,?)",
                          (ch.chunk_id, document_id, chunk_set, analyze(ch.search_text)))
            c.execute("COMMIT")

    def set_run(self, document_id: str, chunk_set: str, **fields: object) -> None:
        fields.setdefault("updated_at", _now())
        with self._conn() as c:
            cols = ", ".join(fields)
            ph = ", ".join("?" for _ in fields)
            upd = ", ".join(f"{k}=excluded.{k}" for k in fields)
            c.execute(f"INSERT INTO index_runs (document_id, chunk_set, {cols}) VALUES (?, ?, {ph}) "  # noqa: S608
                      f"ON CONFLICT(document_id, chunk_set) DO UPDATE SET {upd}",
                      (document_id, chunk_set, *fields.values()))

    def delete_document(self, document_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
            c.execute("DELETE FROM index_runs WHERE document_id=?", (document_id,))

    # ------------------------------------------------------------------ reads
    def runs(self, document_id: str | None = None) -> list[dict]:
        with self._conn() as c:
            q = "SELECT * FROM index_runs" + (" WHERE document_id=?" if document_id else "") + " ORDER BY document_id, chunk_set"
            return [dict(r) for r in c.execute(q, (document_id,) if document_id else ())]

    def count(self, document_id: str | None = None, chunk_set: str | None = None) -> int:
        q, args = "SELECT COUNT(*) FROM chunks WHERE 1=1", []
        if document_id:
            q, args = q + " AND document_id=?", [*args, document_id]
        if chunk_set:
            q, args = q + " AND chunk_set=?", [*args, chunk_set]
        with self._conn() as c:
            return int(c.execute(q, args).fetchone()[0])

    def fts_count(self, document_id: str) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) FROM chunks_fts WHERE document_id=?", (document_id,)).fetchone()[0])

    def get(self, chunk_ids: Iterable[str]) -> dict[str, dict]:
        ids = list(dict.fromkeys(chunk_ids))
        if not ids:
            return {}
        out: dict[str, dict] = {}
        with self._conn() as c:
            for i in range(0, len(ids), 500):
                part = ids[i:i + 500]
                rows = c.execute(f"SELECT * FROM chunks WHERE chunk_id IN ({','.join('?' * len(part))})", part)  # noqa: S608
                for r in rows:
                    out[r["chunk_id"]] = _row(r)
        return out

    def chunks_for(self, document_id: str, chunk_set: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM chunks WHERE document_id=? AND chunk_set=? ORDER BY ordinal",
                             (document_id, chunk_set)).fetchall()
        return [_row(r) for r in rows]

    def bm25(self, query: str, chunk_set: str, document_ids: list[str] | None, limit: int) -> list[tuple[str, float]]:
        q = fts_query(query)
        if not q:
            return []
        sql = "SELECT chunk_id, bm25(chunks_fts) AS s FROM chunks_fts WHERE chunks_fts MATCH ? AND chunk_set = ?"
        args: list[object] = [q, chunk_set]
        if document_ids:
            sql += f" AND document_id IN ({','.join('?' * len(document_ids))})"
            args += document_ids
        sql += " ORDER BY s LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            return [(r["chunk_id"], -float(r["s"])) for r in c.execute(sql, args)]  # higher = better


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["pages"] = json.loads(d.pop("pages_json"))
    d["section_path"] = json.loads(d.pop("section_json"))
    d["blocks"] = json.loads(d.pop("blocks_json"))
    d["meta"] = json.loads(d.pop("meta_json"))
    return d


__all__ = ["BlockRef", "ChunkStore", "analyze", "fts_query"]

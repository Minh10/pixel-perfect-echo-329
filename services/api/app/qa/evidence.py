"""Evidence helpers shared by /retrieve, /qa and /citations: chunk rows -> API objects, document routing."""

from __future__ import annotations

import re

from app.qa.schemas import ChunkRef, CitedRegion, RankedEvidence
from app.retrieval.search import SearchResult
from app.schemas import BBox, NormalizedBBox

API = "/api/v1"


def chunk_ref(row: dict, doc_titles: dict[str, str] | None = None) -> ChunkRef:
    regions = []
    for b in row["blocks"]:
        nb = b["bboxNormalized"]
        clamp = lambda v: min(max(v, 0.0), 1.0)  # noqa: E731
        regions.append(CitedRegion(
            page=b["page"], block_id=b["blockId"], role=b.get("role"),
            bbox=BBox(**b["bbox"]),
            bbox_normalized=NormalizedBBox(x=clamp(nb["x"]), y=clamp(nb["y"]), width=clamp(nb["width"]),
                                           height=clamp(nb["height"])),
            workspace_evidence_id=f"ev-{b['blockId']}" if b["blockId"] else None,
        ))
    meta = row["meta"]
    return ChunkRef(
        chunk_id=row["chunk_id"], chunk_set=row["chunk_set"], kind=row["kind"], document_id=row["document_id"],
        document_title=(doc_titles or {}).get(row["document_id"]), company=row["company"], period=row["period"],
        pages=row["pages"], section_path=row["section_path"], content=row["content"], regions=regions,
        table=meta if row["kind"] == "table" else None, figure=meta if row["kind"] == "figure" else None,
        page_image_url=f"{API}/documents/{row['document_id']}/pages/{row['pages'][0]}/image",
        source_sha256=row["source_sha256"], parser=row["parser"], parser_version=row["parser_version"],
        index_version=row["index_version"],
    )


def ranked(res: SearchResult, rows: dict[str, dict], titles: dict[str, str]) -> list[RankedEvidence]:
    return [RankedEvidence(rank=h.rank, score=round(h.score, 6), method_scores={k: round(v, 6) for k, v in h.method_scores.items()},
                           method_ranks=h.method_ranks, rerank_score=h.rerank_score, chunk=chunk_ref(rows[h.chunk_id], titles))
            for h in res.hits if h.chunk_id in rows]


# --------------------------------------------------------------------------- document routing
_SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|co|company|plc|ltd|limited|holdings|group|sa|nv|the)\b\.?",
                     re.IGNORECASE)
_YEAR = re.compile(r"(?:fy\s?|fiscal\s+(?:year\s+)?)?((?:19|20)\d{2})", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def company_keys(company: str) -> set[str]:
    base = _SUFFIX.sub(" ", company).strip()
    keys = {_norm(company), _norm(base)}
    parts = [p for p in re.split(r"\s+", base) if p]
    if len(parts) > 1:
        keys.add(_norm(" ".join(parts)))
    return {k for k in keys if len(k) >= 2}


def route_documents(question: str, docs: list[dict]) -> list[dict]:
    """Select documents whose issuer is named in the question (alias-normalised), ranking those whose
    reporting period matches a year in the question first.  Empty list = no company match (open corpus)."""
    qn = _norm(question)
    qwords = {_norm(w) for w in re.findall(r"[A-Za-z0-9&]+", question)}
    years = set(_YEAR.findall(question))
    out = []
    for d in docs:
        if d["status"] != "ready" or not d.get("issuer"):
            continue
        keys = company_keys(d["issuer"])
        # short keys (e.g. "3m", "aes", "amd") must match a whole word; long ones may match inside the string
        hit = any((k in qwords) if len(k) <= 4 else (k in qn) for k in keys)
        if hit:
            out.append({"documentId": d["id"], "issuer": d["issuer"], "period": d["period"], "title": d["title"],
                        "periodMatch": bool(d["period"] and d["period"] in years)})
    out.sort(key=lambda x: (not x["periodMatch"], x["documentId"]))
    return out

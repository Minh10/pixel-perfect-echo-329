"""Visual RAG extension: chart interpretation with a vision-language model + table cross-checks.

* The figure crop is rendered from the original PDF (PyMuPDF), sent to the configured LLM provider with a
  JSON schema, and every returned value is typed `visual_estimate` — never a reported figure.
* Cross-check: for each estimated point, table chunks of the same document are searched for a row whose
  label contains the point label; numbers on that row are candidate reported values.  A candidate within
  VISUAL_TOLERANCE (relative) => "consistent"; candidates but none close => "conflict"; none => "no_table_evidence".
  The table value, when consistent, is the authoritative figure; the estimate stays an estimate.
* Results are cached per (document, block) in SQLite and deleted with the document (FK cascade).
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pymupdf

from app.evaluation.metrics import numbers_in, parse_number
from app.indexing.store import ChunkStore
from app.qa.llm import ImagePart, LLMProvider
from app.qa.schemas import ChartInterpretation, ChartPoint, TableCheck

VISUAL_TOLERANCE = 0.10

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["is_chart", "chart_type", "title", "points"],
    "properties": {
        "is_chart": {"type": "boolean"},
        "chart_type": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "points": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["series", "label", "value", "unit", "printed_on_chart"],
            "properties": {"series": {"type": ["string", "null"]}, "label": {"type": "string"},
                           "value": {"type": "string"}, "unit": {"type": ["string", "null"]},
                           "printed_on_chart": {"type": "boolean"}}}},
    },
}

PROMPT = """You are reading a chart image cropped from a company financial report.
If the image is not a data chart, set is_chart to false and return no points.
Otherwise report each data point you can read: its category label exactly as printed, the series name if there are
several series, the value, and the unit if shown in the title, axis or legend. If a number is printed on the chart
as a data label, copy it exactly and set printed_on_chart true. If you must estimate a value from bar length or
point position against the axis, give your best reading as a plain number and set printed_on_chart false.
Do not invent categories that are not visible. Do not add commentary or confidence scores.
Caption / surrounding text (for context only, do not copy numbers from it): {context}"""

DDL = """CREATE TABLE IF NOT EXISTS chart_interpretations (
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    block_id    TEXT NOT NULL,
    data_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (document_id, block_id)
)"""


class ChartStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        with self._c() as c:
            c.execute(DDL)

    def _c(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def get(self, document_id: str, block_id: str) -> ChartInterpretation | None:
        with self._c() as c:
            r = c.execute("SELECT data_json FROM chart_interpretations WHERE document_id=? AND block_id=?",
                          (document_id, block_id)).fetchone()
        return ChartInterpretation.model_validate_json(r[0]) if r else None

    def put(self, ci: ChartInterpretation) -> None:
        with self._c() as c:
            c.execute("INSERT OR REPLACE INTO chart_interpretations VALUES (?,?,?,?)",
                      (ci.document_id, ci.block_id, ci.model_dump_json(), ci.created_at))


def render_crop(pdf: Path, page_no: int, bbox: tuple[float, float, float, float], dpi: int = 150) -> bytes:
    with pymupdf.open(pdf) as doc:
        page = doc[page_no - 1]
        clip = pymupdf.Rect(*bbox) * page.derotation_matrix
        return page.get_pixmap(dpi=dpi, clip=clip, alpha=False).tobytes("png")


def cross_check(points: list[ChartPoint], table_chunks: list[dict]) -> list[TableCheck]:
    out = []
    for pt in points:
        est = parse_number(pt.value)
        label = pt.label.strip().lower()
        cands: list[tuple[Decimal, str]] = []
        if est is not None and len(label) >= 2:
            for ch in table_chunks:
                for line in ch["content"].splitlines():
                    head = line.split(":", 1)[0].strip().lower()
                    if re.search(rf"\b{re.escape(label)}\b", head):
                        rest = line.split(":", 1)[1] if ":" in line else ""
                        # numbers after "col = " pairs; skip the column labels (often years)
                        vals = [numbers_in(seg.split("=", 1)[1]) for seg in rest.split(";") if "=" in seg]
                        cands += [(v[0], ch["chunk_id"]) for v in vals if v]
        if est is None or not cands:
            out.append(TableCheck(label=pt.label, estimate=pt.value, table_value=None, table_chunk_id=None,
                                  relative_difference=None, status="no_table_evidence"))
            continue
        best = min(cands, key=lambda c: abs(c[0] - est))
        rel = float(abs(best[0] - est) / abs(best[0])) if best[0] != 0 else (0.0 if est == 0 else float("inf"))
        out.append(TableCheck(label=pt.label, estimate=pt.value, table_value=str(best[0]), table_chunk_id=best[1],
                              relative_difference=round(rel, 4),
                              status="consistent" if rel <= VISUAL_TOLERANCE else "conflict"))
    return out


def interpret_chart(document_id: str, block: dict, page_no: int, pdf: Path, llm: LLMProvider,
                    store: ChunkStore, context: str) -> ChartInterpretation:
    bb = block["bbox"]
    png = render_crop(pdf, page_no, (bb["l"], bb["t"], bb["r"], bb["b"]))
    res = llm.generate_json("You extract data from chart images precisely and never guess beyond what is visible.",
                            [ImagePart(png), PROMPT.format(context=context[:800] or "(none)")], SCHEMA, "chart_reading")
    d = res.data
    points = [ChartPoint(series=p.get("series"), label=p["label"], value=p["value"], unit=p.get("unit"),
                         printed_on_chart=bool(p.get("printed_on_chart"))) for p in (d.get("points") or [])
              if d.get("is_chart")]
    tables = [c for c in store.chunks_for(document_id, "layout") if c["kind"] == "table"]
    return ChartInterpretation(
        document_id=document_id, block_id=block["id"], chart_type=d.get("chart_type"), title=d.get("title"),
        points=points, table_checks=cross_check(points, tables),
        crop_url=f"/api/v1/documents/{document_id}/blocks/{block['id']}/image", provider=res.provider,
        model=res.model, created_at=datetime.now(UTC).isoformat())


def evidence_text(ci: ChartInterpretation) -> str:
    """Text appended to a figure's evidence for QA.  Explicitly marked as visual estimates."""
    if not ci.points:
        return ""
    checks = {c.label: c for c in ci.table_checks}
    parts = []
    for p in ci.points:
        s = f"{(p.series + ' / ') if p.series else ''}{p.label} ≈ {p.value}{(' ' + p.unit) if p.unit else ''}"
        c = checks.get(p.label)
        if c and c.status == "consistent":
            s += f" [table reports {c.table_value}; use the table value]"
        elif c and c.status == "conflict":
            s += f" [conflicts with table value {c.table_value}]"
        parts.append(s)
    return "VISUAL ESTIMATE (read from chart image, approximate): " + "; ".join(parts)


def dumps(ci: ChartInterpretation) -> str:
    return json.dumps(ci.model_dump(by_alias=True))

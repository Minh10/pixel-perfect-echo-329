"""Visual RAG extension: chart interpretation with a vision-language model + table cross-checks.

* The figure crop is rendered from the original PDF (PyMuPDF), sent to the configured LLM provider with a
  JSON schema, and every returned value is typed `visual_estimate` — never a reported figure.
* Cross-check: a point matches one parsed FinancialFact only when the row label, fiscal year, scale, and
  currency agree and exactly one fact remains. A nearer number from another year is not a candidate.
  Relative difference within VISUAL_TOLERANCE => "consistent"; the same-year fact outside that band =>
  "conflict"; anything else => "no_table_evidence". The estimate stays an estimate.
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

from app.evaluation.metrics import parse_number
from app.indexing.store import ChunkStore
from app.qa.llm import ImagePart, LLMProvider
from app.qa.schemas import ChartInterpretation, ChartPoint, TableCheck

VISUAL_TOLERANCE = 0.10

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["is_chart", "chart_type", "title", "summary", "x_axis", "y_axis", "points"],
    "properties": {
        "is_chart": {"type": "boolean"},
        "chart_type": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "summary": {"type": ["string", "null"]},
        "x_axis": {"type": ["string", "null"]},
        "y_axis": {"type": ["string", "null"]},
        "points": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["series", "label", "value", "unit", "period", "printed_on_chart"],
            "properties": {"series": {"type": ["string", "null"]}, "label": {"type": "string"},
                           "value": {"type": "string"}, "unit": {"type": ["string", "null"]},
                           "period": {"type": ["string", "null"]},
                           "printed_on_chart": {"type": "boolean"}}}},
    },
}

PROMPT = """You are reading one image cropped from a company financial report.
If the image is not a data chart, set is_chart to false, summary to a short statement that no chart values can be
read, and return no points.
Otherwise extract the chart type, title, axis labels, and each visible category. For every point give the category
label exactly as printed, the series name when several series are visible, the reporting period or year printed for
that point, and the unit if the title, axis, or legend states one.
If a number is printed as a data label, copy it exactly and set printed_on_chart true. If you estimate a value from
bar length or position, set printed_on_chart false. If a value cannot be read, set value to "cannot be read" and do
not guess a number.
The summary may mention only numbers you placed in points. Do not copy numbers from the caption below.
Caption / surrounding text (context only): {context}"""

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


def _norm_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _year_from(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\b(?:19|20)\d{2}\b", value)
    return match.group(0) if match else None


def _fact_year(fact: dict) -> str | None:
    period = fact.get("period") or {}
    year = period.get("fiscalYear", period.get("fiscal_year"))
    if isinstance(year, int):
        return str(year)
    return _year_from(str(period.get("label") or ""))


def _scale_ok(unit: str | None, fact: dict) -> bool:
    scale = fact.get("scale") or "unknown"
    percent = bool(fact.get("isPercent") if "isPercent" in fact else fact.get("is_percent"))
    text = (unit or "").lower()
    if percent or scale == "percent":
        return "percent" in text or "%" in text
    if "percent" in text or "%" in text:
        return False
    if "billion" in text:
        return scale == "billions"
    if "million" in text:
        return scale == "millions"
    if "thousand" in text:
        return scale == "thousands"
    return True


def _currency_ok(unit: str | None, fact: dict) -> bool:
    text = unit or ""
    currency = fact.get("currency")
    if "GBP" in text.upper() or "£" in text:
        return currency == "GBP"
    if "USD" in text.upper() or "$" in text:
        return currency in {"USD", "dollar"}
    if "EUR" in text.upper() or "€" in text:
        return currency == "EUR"
    return True


def _blank_check(point: ChartPoint) -> TableCheck:
    return TableCheck(label=point.label, estimate=point.value, table_value=None, table_chunk_id=None,
                      relative_difference=None, status="no_table_evidence")


def cross_check(points: list[ChartPoint], facts: list[dict]) -> list[TableCheck]:
    """Align a chart point to one FinancialFact. A nearer number from another year is not a candidate."""
    out = []
    for point in points:
        estimate = parse_number(point.value)
        year = _year_from(point.period)
        label = _norm_label(point.label)
        if estimate is None or not year or len(label) < 2:
            out.append(_blank_check(point))
            continue
        matches = []
        for fact in facts:
            status = fact.get("valueStatus") or fact.get("value_status")
            if status != "parsed" or fact.get("value") is None:
                continue
            fact_label = _norm_label(str(fact.get("rowLabel") or fact.get("row_label") or ""))
            if fact_label != label or _fact_year(fact) != year:
                continue
            if not _scale_ok(point.unit, fact) or not _currency_ok(point.unit, fact):
                continue
            matches.append(fact)
        if len(matches) != 1 or len({fact.get("scope") for fact in matches}) != 1:
            out.append(_blank_check(point))
            continue
        fact = matches[0]
        reported = Decimal(str(fact["value"]))
        gap = abs(reported - estimate)
        relative = float(gap / abs(reported)) if reported != 0 else (0.0 if estimate == 0 else float("inf"))
        out.append(TableCheck(
            label=point.label, estimate=point.value, table_value=str(reported),
            table_chunk_id=fact.get("tableId") or fact.get("table_id"),
            relative_difference=round(relative, 4),
            status="consistent" if relative <= VISUAL_TOLERANCE else "conflict",
            fact_id=fact.get("factId") or fact.get("fact_id"), page=fact.get("page"), period=year,
            absolute_difference=str(gap),
        ))
    return out


def _number_tokens(text: str) -> set[str]:
    found = set()
    for token in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        parsed = parse_number(token)
        if parsed is not None:
            found.add(format(parsed, "f"))
    return found


def grounded_summary(model_summary: str | None, reading: dict, points: list[ChartPoint],
                     checks: list[TableCheck]) -> str:
    """Keep a model sentence only when every number in it is one of the extracted points or matched facts."""
    allowed: set[str] = set()
    for point in points:
        parsed = parse_number(point.value)
        if parsed is not None:
            allowed.add(format(parsed, "f"))
    for check in checks:
        parsed = parse_number(check.table_value or "")
        if parsed is not None:
            allowed.add(format(parsed, "f"))
    text = (model_summary or "").strip()
    if text and _number_tokens(text) <= allowed:
        return text
    if not points:
        return "No chart values were extracted. Nothing numerical is stated."
    parts = []
    for point in points:
        parsed = parse_number(point.value)
        if parsed is None:
            parts.append(f"{point.label}: the value could not be read")
            continue
        kind = "printed on the chart" if point.printed_on_chart else "estimated from the graphic"
        unit = f" {point.unit}" if point.unit else ""
        period = f" in {point.period}" if point.period else ""
        parts.append(f"{point.label}{period} {point.value}{unit} ({kind})")
    title = reading.get("title") or reading.get("chart_type") or "Chart"
    summary = f"{title}. " + "; ".join(parts) + "."
    for check in checks:
        if check.status == "consistent":
            summary += f" {check.label} is close to reported {check.table_value}."
        elif check.status == "conflict":
            summary += f" {check.label} differs from reported {check.table_value}."
    return summary


def interpret_chart(document_id: str, block: dict, page_no: int, pdf: Path, llm: LLMProvider,
                    store: ChunkStore, context: str) -> ChartInterpretation:
    bb = block["bbox"]
    png = render_crop(pdf, page_no, (bb["l"], bb["t"], bb["r"], bb["b"]))
    res = llm.generate_json("You extract data from chart images precisely and never guess beyond what is visible.",
                            [ImagePart(png), PROMPT.format(context=context[:800] or "(none)")], SCHEMA, "chart_reading")
    data = res.data if isinstance(res.data, dict) else {}
    points = []
    if data.get("is_chart"):
        for item in data.get("points") or []:
            if not item.get("label"):
                continue
            points.append(ChartPoint(series=item.get("series"), label=item["label"], value=str(item.get("value") or ""),
                                     unit=item.get("unit"), period=item.get("period"),
                                     printed_on_chart=bool(item.get("printed_on_chart"))))
    checks = cross_check(points, store.facts_for_document(document_id))
    summary = grounded_summary(None if not data.get("is_chart") else data.get("summary"), data, points, checks)
    if not data.get("is_chart"):
        summary = "The image is not a data chart, so no values were extracted."
    return ChartInterpretation(
        document_id=document_id, block_id=block["id"], chart_type=data.get("chart_type"), title=data.get("title"),
        summary=summary, points=points, table_checks=checks,
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

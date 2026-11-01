"""Turn a parser-neutral `RawParse` into the public `ParseResult` (pages, blocks, evidence).

Rules that keep evidence honest:
  * Every block and evidence item carries full provenance (doc id, sha256, page, bbox, parser, method, job).
  * Text and table cells are copied verbatim from the parser.  No normalisation of numbers.
  * Evidence is a *candidate region* (table, figure, or text containing financial-looking numbers);
    `extracted` stays null and `confidence` is only set from a parser-reported score.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from app.processing.geometry import Box
from app.processing.model import PageInspection, RawBlock, RawParse, RawTable
from app.schemas import (
    DocumentPage,
    Evidence,
    EvidenceDetection,
    FigureClassification,
    FigureData,
    PageBlock,
    PageConfidence,
    ParserInfo,
    ParseResult,
    Provenance,
    TableCell,
    TableData,
    TableRow,
)

API_PREFIX = "/api/v1"

_CURRENCY = r"[£$€¥₫]|\b(?:GBP|USD|EUR|JPY|CNY|VND|CHF|AUD|CAD|SGD|HKD)\b"
_SCALE = r"(?:million|billion|trillion|thousand|bn|mn|mm|m|k)\b"  # "366m", "1.2 bn"
_PCT = r"\d\s?%|\bper\s?cent\b|\bpercent\b|\bbasis points?\b|\bbps\b"
_FORMATTED = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\(\d[\d,.]*\)"
NUMERIC_DISCLOSURE_RE = re.compile(rf"(?:{_CURRENCY}|{_PCT}|{_FORMATTED})|(?:\d[\d,.]*\s*(?:{_SCALE}))", re.IGNORECASE)
NUMERIC_RULE = "numeric-disclosure-v1: currency | percent/bps | thousands-separated or parenthesised number | number+scale word"

_HEADING_ROLES = {"title", "section_header"}
_TEXT_EVIDENCE_ROLES = {"text", "list_item", "footnote"}


def kind_for(role: str) -> str:
    if role in _HEADING_ROLES:
        return "heading"
    if role == "table":
        return "table"
    if role in ("picture", "chart"):
        return "figure"
    return "paragraph"


def is_numeric_disclosure(text: str) -> bool:
    return bool(NUMERIC_DISCLOSURE_RE.search(text))


def table_to_schema(t: RawTable, scale: tuple[float, float]) -> TableData:
    grid = [["" for _ in range(t.num_cols)] for _ in range(t.num_rows)]
    header_flags: dict[int, list[bool]] = {}
    for c in t.cells:
        if 0 <= c.row < t.num_rows and 0 <= c.col < t.num_cols:
            grid[c.row][c.col] = c.text
            header_flags.setdefault(c.row, []).append(c.column_header)
    header_rows = 0
    for r in range(t.num_rows):
        flags = header_flags.get(r)
        if flags and all(flags):
            header_rows += 1
        else:
            break
    if header_rows:
        columns = []
        for col in range(t.num_cols):
            parts: list[str] = []
            for r in range(header_rows):
                if grid[r][col] and grid[r][col] not in parts:
                    parts.append(grid[r][col])
            columns.append(" ".join(parts))
    else:
        columns = [""] * t.num_cols
    rows = [TableRow(label=grid[r][0] if t.num_cols else "", values=grid[r][1:]) for r in range(header_rows, t.num_rows)]
    sx, sy = scale
    cells = [
        TableCell(
            row=c.row, col=c.col, row_span=c.row_span, col_span=c.col_span, text=c.text,
            column_header=c.column_header, row_header=c.row_header,
            bbox=_scaled(c.bbox, sx, sy).to_schema() if c.bbox else None,
        )
        for c in t.cells
    ]
    return TableData(columns=columns, rows=rows, num_rows=t.num_rows, num_cols=t.num_cols,
                     header_rows=header_rows, cells=cells)


def _scaled(b: Box, sx: float, sy: float) -> Box:
    return b if (sx, sy) == (1.0, 1.0) else Box(b.l * sx, b.t * sy, b.r * sx, b.b * sy)


def _table_excerpt(td: TableData) -> str:
    labels = [r.label for r in td.rows if r.label][:4]
    head = f"{td.num_rows}×{td.num_cols} table"
    cols = [c for c in td.columns if c]
    if cols:
        head += " · columns: " + ", ".join(cols[:5])
    if labels:
        head += " · rows: " + ", ".join(labels) + ("…" if len(td.rows) > 4 else "")
    return head


def assemble(
    raw: RawParse, inspections: list[PageInspection], *, document_id: str, job_id: str, sha256: str,
) -> ParseResult:
    pages: list[DocumentPage] = []
    evidence: list[Evidence] = []
    warnings = list(raw.warnings)
    current_section = ""
    parser_info = ParserInfo(name=raw.parser, version=raw.parser_version, options=raw.options)  # type: ignore[arg-type]

    for insp in inspections:
        n = insp.number
        pw, ph = raw.page_sizes.get(n, (insp.width, insp.height))
        sx, sy = insp.width / pw, insp.height / ph
        if abs(pw - insp.width) > 1 or abs(ph - insp.height) > 1:
            warnings.append(f"Page {n}: parser page size {pw:.1f}x{ph:.1f} differs from PDF {insp.width:.1f}x{insp.height:.1f}; boxes rescaled")
        if not insp.has_text_layer:
            warnings.append(f"Page {n}: no text layer (scanned/image-only); text requires OCR"
                            + ("" if raw.options.get("ocr") else ", which is disabled"))
        raw_blocks: list[RawBlock] = raw.blocks.get(n, [])
        ids = [f"p{n}-b{i + 1:03d}" for i in range(len(raw_blocks))]
        page_section = None
        blocks: list[PageBlock] = []

        for i, rb in enumerate(raw_blocks):
            box = _scaled(rb.bbox, sx, sy).clamp(insp.width, insp.height)
            prov = Provenance(
                document_id=document_id, source_sha256=sha256, page=n, bbox=box.to_schema(),
                bbox_normalized=box.normalized(insp.width, insp.height), page_width=round(insp.width, 2),
                page_height=round(insp.height, 2), charspan=rb.charspan, source_ref=rb.source_ref,
                parser=raw.parser, parser_version=raw.parser_version, method=rb.method, job_id=job_id,  # type: ignore[arg-type]
            )
            kind = kind_for(rb.role)
            caption_id = ids[rb.caption_index] if rb.caption_index is not None and rb.caption_index < len(ids) else None
            caption_text = raw_blocks[rb.caption_index].text if caption_id else None
            block = PageBlock(
                id=ids[i], kind=kind, role=rb.role if rb.role in _KNOWN_ROLES else "other",  # type: ignore[arg-type]
                text=rb.text, level=rb.level, bbox=prov.bbox, bbox_normalized=prov.bbox_normalized,
                provenance=prov, caption_block_id=caption_id,
            )
            if rb.table is not None:
                block.table = table_to_schema(rb.table, (sx, sy))
            if kind == "figure":
                block.figure = FigureData(
                    caption=caption_text,
                    classification=[FigureClassification(class_name=c, confidence=p, created_by=b)
                                    for c, p, b in rb.figure_classes],
                    image_url=f"{API_PREFIX}/documents/{document_id}/blocks/{ids[i]}/image",
                )
            blocks.append(block)

            if kind == "heading" and rb.text:
                current_section = rb.text.strip()
                page_section = page_section or current_section

            ev = _evidence_for(block, caption_text, n)
            if ev:
                evidence.append(ev)

        sc = raw.scores.get(n)
        pages.append(
            DocumentPage(
                number=n, section=page_section or current_section, width=round(insp.width, 2),
                height=round(insp.height, 2), rotation=insp.rotation, has_text_layer=insp.has_text_layer,
                char_count=insp.char_count, image_count=insp.image_count,
                confidence=PageConfidence(**{k: _finite(v) for k, v in sc.__dict__.items()}) if sc else None,
                image_url=f"{API_PREFIX}/documents/{document_id}/pages/{n}/image", blocks=blocks,
            )
        )

    return ParseResult(
        document_id=document_id, job_id=job_id, source_sha256=sha256, parser=parser_info,
        created_at=datetime.now(UTC), warnings=warnings, pages=pages, evidence=evidence,
    )


_KNOWN_ROLES = {
    "title", "section_header", "text", "list_item", "caption", "footnote", "page_header", "page_footer",
    "formula", "code", "table", "picture", "chart", "other",
}


def _finite(v: float | None) -> float | None:
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def _evidence_for(block: PageBlock, caption: str | None, page: int) -> Evidence | None:
    base = {"id": f"ev-{block.id}", "page": page, "block_id": block.id, "provenance": block.provenance}
    method = block.provenance.method
    if block.kind == "table" and block.table is not None:
        return Evidence(**base, category="table", label=caption or f"Table on page {page}",
                        excerpt=_table_excerpt(block.table), detection=EvidenceDetection(method=method))
    if block.kind == "figure":
        classes = ", ".join(c.class_name for c in (block.figure.classification if block.figure else [])[:1])
        label = caption or (f"Figure on page {page} ({classes})" if classes else f"Figure on page {page}")
        return Evidence(**base, category="figure", label=label,
                        excerpt=caption or "Figure region (no caption detected; content not extracted)",
                        detection=EvidenceDetection(method=method))
    if block.role in _TEXT_EVIDENCE_ROLES and block.text and is_numeric_disclosure(block.text):
        text = block.text.strip()
        return Evidence(**base, category="disclosure", label=f"Numeric statement, page {page}",
                        excerpt=text if len(text) <= 280 else text[:277] + "…",
                        detection=EvidenceDetection(method=f"{method} + rule", rule=NUMERIC_RULE))
    return None

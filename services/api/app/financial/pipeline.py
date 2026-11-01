"""Document-level fact normalization: parse.json + source PDF words -> {table_id: TableNormalization}."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from app.financial.facts import document_unit_statements, normalize_table, units_for_page
from app.financial.schema import TableNormalization
from app.schemas import ParseResult


def normalize_document(document_id: str, issuer: str | None, source_sha256: str, parse: ParseResult,
                       pdf_path: Path) -> dict[str, TableNormalization]:
    out: dict[str, TableNormalization] = {}
    with pymupdf.open(pdf_path) as d:
        statements = document_unit_statements([p.get_text() for p in d])
        for page in parse.pages:
            if not any(b.kind == "table" and b.table for b in page.blocks):
                continue
            words = [w[:5] for w in d[page.number - 1].get_text("words")]
            for i, b in enumerate(page.blocks):
                if b.kind != "table" or b.table is None:
                    continue
                caption = next((x.text for x in page.blocks if x.id == b.caption_block_id), None) or ""
                prev = " ".join((x.text or "") for x in page.blocks[max(0, i - 2):i] if x.kind != "table" and x.text)
                lead_in = ""
                body_before = [x for x in page.blocks[:i] if x.kind not in ("table", "figure")
                               and x.role not in ("page_header", "page_footer") and len(x.text or "") > 40]
                if not body_before and page.number > 1:  # table at the top of a page: lead-in is on the previous page
                    pp = next((q for q in parse.pages if q.number == page.number - 1), None)
                    blocks = pp.blocks if pp else []
                    last_tab = max((j for j, x in enumerate(blocks) if x.kind == "table"), default=-1)
                    # only text AFTER the previous page's last table (otherwise it introduces that table)
                    tail = [x.text for x in blocks[last_tab + 1:] if x.kind == "text" and x.text
                            and x.role not in ("page_header", "page_footer") and len(x.text) > 40]
                    lead_in = " ".join(tail[-1:])[-300:]
                out[b.id] = normalize_table(
                    b, page.number, words, document_id=document_id, issuer=issuer, source_sha256=source_sha256,
                    parser=parse.parser.name, parser_version=parse.parser.version,
                    context_text=" ".join(x for x in (caption, prev) if x)[-400:],
                    document_units=units_for_page(statements, page.number), lead_in_text=lead_in)
    return out

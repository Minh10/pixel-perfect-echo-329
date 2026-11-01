"""PyMuPDF page inspection and deterministic text-layer parser.

`inspect_pages` always runs (page sizes, rotation, text-layer presence, image counts).
`parse_with_pymupdf` is a fallback parser that uses no ML models:
  * text blocks: PDF text layer (`page.get_text("dict")`), headings by font-size heuristic
  * tables: `page.find_tables()` (ruling-line based); cell text = words inside each cell rect
  * figures: placed raster images and large vector-drawing clusters
Every block records the method that produced it so consumers can weigh it accordingly.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pymupdf

from app.processing.geometry import Box
from app.processing.model import PageInspection, RawBlock, RawCell, RawParse, RawTable

CAPTION_RE = re.compile(r"^\s*(table|figure|fig\.|chart|exhibit|graph|note)\s*[\dA-Z]", re.IGNORECASE)
MIN_FIGURE_PT = 36.0


def pymupdf_version() -> str:
    return str(pymupdf.version[0])


def inspect_pages(pdf_path: Path) -> list[PageInspection]:
    out: list[PageInspection] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text("text")
            out.append(
                PageInspection(
                    number=page.number + 1,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    rotation=int(page.rotation),
                    char_count=len("".join(text.split())),
                    image_count=len(page.get_image_info()),
                )
            )
    return out


def _words_text(words: list[tuple], rect: Box) -> str:
    """Text of words whose area lies mostly inside rect, in reading order."""
    picked = []
    for w in words:
        wb = Box(w[0], w[1], w[2], w[3])
        if wb.fraction_inside(rect) > 0.5:
            picked.append(w)
    picked.sort(key=lambda w: (w[5], w[6], w[7]))  # block, line, word number
    return " ".join(w[4] for w in picked).strip()


def _extract_tables(page: pymupdf.Page, words: list[tuple]) -> list[RawBlock]:
    blocks: list[RawBlock] = []
    try:
        finder = page.find_tables()
    except Exception:  # table finder failures must not fail the whole page
        return blocks
    for t in finder.tables:
        cells: list[RawCell] = []
        for r_idx, row in enumerate(t.rows):
            for c_idx, cell in enumerate(row.cells):
                if cell is None:  # covered by a span or a gap
                    continue
                cb = Box(*cell)
                cells.append(
                    RawCell(
                        row=r_idx, col=c_idx, row_span=1, col_span=1,
                        text=_words_text(words, cb),
                        column_header=(r_idx == 0 and not t.header.external),
                        bbox=cb,
                    )
                )
        blocks.append(
            RawBlock(
                page=page.number + 1, role="table", bbox=Box(*t.bbox), method="pymupdf:find_tables",
                table=RawTable(num_rows=t.row_count, num_cols=t.col_count, cells=cells),
            )
        )
    return blocks


def _extract_figures(page: pymupdf.Page, tables: list[RawBlock]) -> list[RawBlock]:
    page_area = page.rect.width * page.rect.height
    figs: list[RawBlock] = []
    for info in page.get_image_info():
        b = Box(*info["bbox"]).clamp(page.rect.width, page.rect.height)
        if b.width >= MIN_FIGURE_PT and b.height >= MIN_FIGURE_PT and b.area >= 0.01 * page_area:
            figs.append(RawBlock(page=page.number + 1, role="picture", bbox=b, method="pymupdf:image-placement"))
    try:
        clusters = page.cluster_drawings()
    except Exception:
        clusters = []
    for rect in clusters:
        b = Box(*rect).clamp(page.rect.width, page.rect.height)
        if b.width < 72 or b.height < 72 or b.area < 0.04 * page_area:
            continue
        if any(b.fraction_inside(t.bbox) > 0.5 for t in tables):  # table rulings
            continue
        if any(b.fraction_inside(f.bbox) > 0.5 for f in figs):
            continue
        figs.append(RawBlock(page=page.number + 1, role="picture", bbox=b, method="pymupdf:vector-drawing-cluster"))
    return figs


def parse_with_pymupdf(pdf_path: Path) -> RawParse:
    blocks_by_page: dict[int, list[RawBlock]] = {}
    sizes: dict[int, tuple[float, float]] = {}
    with pymupdf.open(pdf_path) as doc:
        pages_dicts = []
        size_hist: Counter[float] = Counter()
        for page in doc:
            d = page.get_text("dict", sort=True)
            pages_dicts.append(d)
            for b in d["blocks"]:
                if b["type"] == 0:
                    for line in b["lines"]:
                        for s in line["spans"]:
                            size_hist[round(s["size"], 1)] += len(s["text"].strip())
        body_size = size_hist.most_common(1)[0][0] if size_hist else 10.0
        max_size = max(size_hist) if size_hist else body_size

        for page, d in zip(doc, pages_dicts, strict=True):
            n = page.number + 1
            sizes[n] = (float(page.rect.width), float(page.rect.height))
            words = page.get_text("words", sort=True)
            tables = _extract_tables(page, words)
            figures = _extract_figures(page, tables)
            regions = [*tables, *figures]
            text_blocks: list[RawBlock] = []
            for b in d["blocks"]:
                if b["type"] != 0:
                    continue
                bb = Box(*b["bbox"])
                if any(bb.fraction_inside(r.bbox) > 0.5 for r in regions):
                    continue  # text belongs to a table/figure region
                lines = [" ".join(s["text"] for s in ln["spans"]).strip() for ln in b["lines"]]
                text = " ".join(x for x in lines if x)
                if not text:
                    continue
                span_size = max(s["size"] for ln in b["lines"] for s in ln["spans"])
                role, level = "text", None
                if CAPTION_RE.match(text) and len(text) < 300:
                    role = "caption"
                elif span_size >= body_size * 1.25 and len(text) < 160 and len(lines) <= 3:
                    if n == 1 and span_size >= max_size:
                        role = "title"
                    else:
                        role, level = "section_header", 1
                text_blocks.append(
                    RawBlock(page=n, role=role, bbox=bb, text=text, level=level, method="pymupdf:text-layer")
                )
            page_blocks = sorted([*text_blocks, *regions], key=lambda rb: (round(rb.bbox.t, 1), rb.bbox.l))
            _link_captions(page_blocks)
            blocks_by_page[n] = page_blocks

    return RawParse(
        parser="pymupdf",
        parser_version=pymupdf_version(),
        options={"headingHeuristic": "font-size>=1.25x body", "tables": "find_tables", "ocr": False},
        page_sizes=sizes,
        blocks=blocks_by_page,
    )


def _link_captions(blocks: list[RawBlock], max_gap: float = 36.0) -> None:
    captions = [i for i, b in enumerate(blocks) if b.role == "caption"]
    for b in blocks:
        if b.role not in ("table", "picture"):
            continue
        best, best_gap = None, max_gap
        for i in captions:
            c = blocks[i].bbox
            if min(b.bbox.r, c.r) - max(b.bbox.l, c.l) <= 0:  # no horizontal overlap
                continue
            gap = c.t - b.bbox.b if c.t >= b.bbox.b else b.bbox.t - c.b
            if 0 <= gap < best_gap:
                best, best_gap = i, gap
        b.caption_index = best

"""Layout-aware chunking (chunk set "layout") and the flat text-window baseline (chunk set "flat").

Layout chunks follow document structure, never arbitrary character windows:
  * text   — consecutive body blocks under one section on one page, up to a word budget; a block is never
             split unless it alone exceeds the budget (then at sentence boundaries).
  * table  — one chunk per table, or row groups of a large table.  Every table chunk repeats the title/
             context, detected unit phrase and column headers (reporting periods), so a value is never
             separated from its row label, its period column or its unit.
  * figure — caption + parser classification + surrounding text on the same page.
Every chunk records its source blocks (page, block id, bbox) for citations, its section path, and the
document/company/period identifiers.

Flat chunks are the classic baseline: the PDF's raw page text (PyMuPDF), sliding word windows, with the
same document header line as layout chunks so comparisons isolate the effect of layout/structure.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from app.processing.geometry import Box
from app.schemas import DocumentPage, PageBlock, ParseResult

CHUNKER_VERSION = "layout-v2"  # v2: content-based header rows + period recovery from context
FLAT_CHUNKER_VERSION = "flat-v1"

TEXT_WORD_BUDGET = 220
TABLE_WORD_BUDGET = 320
TABLE_GROUP_WORD_BUDGET = 200
FLAT_WINDOW, FLAT_STRIDE = 200, 150

CURRENCY_ONLY = {"$", "€", "£", "¥", "US$", "USD", "₫", "C$", "A$"}
UNIT_RE = re.compile(
    r"\(?\s*(?:(?:US)?\$|dollars?|amounts?|€|£|USD|EUR|GBP)?\s*(?:in\s+)?"
    r"(thousands|millions|billions|000s|'000|mn|bn)\b[^)]{0,60}\)?",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"^(?:FY\s?)?(19|20)\d{2}[A-Z]?$|^Q[1-4]\s?(19|20)\d{2}$", re.IGNORECASE)
CONTEXT_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
NUM_RE = re.compile(r"^[\s$€£¥(+\-–—]*\d[\d,.\s]*\)?\s*%?$")
BOILERPLATE_RE = re.compile(r"^(table of contents|\d{1,4}|page \d+( of \d+)?)$", re.IGNORECASE)
SENT_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z(])")


@dataclass
class DocMeta:
    document_id: str
    title: str
    company: str | None
    period: str | None
    doc_type: str | None
    source_sha256: str
    parser: str
    parser_version: str
    parse_job_id: str

    def header(self) -> str:
        parts = [p for p in (self.company, self.period, self.doc_type, self.title) if p]
        return " · ".join(dict.fromkeys(parts))


@dataclass
class BlockRef:
    page: int
    block_id: str | None
    bbox: tuple[float, float, float, float]
    page_width: float
    page_height: float
    role: str

    def to_dict(self) -> dict:
        l, t, r, b = self.bbox
        return {"page": self.page, "blockId": self.block_id, "bbox": {"l": l, "t": t, "r": r, "b": b},
                "bboxNormalized": {"x": l / self.page_width, "y": t / self.page_height,
                                   "width": (r - l) / self.page_width, "height": (b - t) / self.page_height},
                "pageWidth": self.page_width, "pageHeight": self.page_height, "role": self.role}


@dataclass
class Chunk:
    chunk_id: str
    chunk_set: str            # "layout" | "flat"
    kind: str                 # "text" | "table" | "figure" | "window"
    document_id: str
    company: str | None
    period: str | None
    pages: list[int]
    section_path: list[str]
    content: str              # the evidence text shown to readers / the LLM
    search_text: str          # header + content: what BM25 and the embedder see
    blocks: list[BlockRef]
    meta: dict = field(default_factory=dict)   # table/figure structure
    chunker_version: str = CHUNKER_VERSION
    ordinal: int = 0


def _cid(*parts: object) -> str:
    return "chk_" + hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:24]


def _ref(page: DocumentPage, b: PageBlock, bbox: Box | None = None) -> BlockRef:
    bb = bbox or Box(b.bbox.l, b.bbox.t, b.bbox.r, b.bbox.b)
    return BlockRef(page.number, b.id, (round(bb.l, 2), round(bb.t, 2), round(bb.r, 2), round(bb.b, 2)),
                    page.width, page.height, b.role)


def _words(s: str) -> int:
    return len(s.split())


# --------------------------------------------------------------------------- furniture
def _furniture_texts(pages: list[DocumentPage]) -> set[str]:
    """Short lines repeated on >=30% of pages (running headers/footers), detected generically."""
    if len(pages) < 4:
        return set()
    counts: Counter[str] = Counter()
    for p in pages:
        seen = {(b.text or "").strip().lower() for b in p.blocks if b.text and len(b.text) < 80}
        counts.update(seen)
    return {t for t, c in counts.items() if c >= max(3, 0.3 * len(pages))}


def _is_furniture(b: PageBlock, furniture: set[str]) -> bool:
    t = (b.text or "").strip()
    return (b.role in ("page_header", "page_footer") or not t or bool(BOILERPLATE_RE.match(t))
            or t.lower() in furniture)


# --------------------------------------------------------------------------- tables
@dataclass
class NormTable:
    columns: list[str]
    rows: list[tuple[int, str, list[str]]]  # (original row index, label, values)
    header_rows: int
    col_map: list[int]                       # normalized col -> original col


def normalize_table(b: PageBlock) -> NormTable:
    """Clean a parsed table for indexing: merge currency-symbol cells into their numbers, drop empty
    columns and detect header rows (periods).  Cell text itself is never altered beyond that merge."""
    t = b.table
    assert t is not None
    grid = [["" for _ in range(t.num_cols)] for _ in range(t.num_rows)]
    for c in t.cells:
        if 0 <= c.row < t.num_rows and 0 <= c.col < t.num_cols:
            grid[c.row][c.col] = c.text.strip()
    for row in grid:
        for j, v in enumerate(row):
            if v in CURRENCY_ONLY:
                k = next((k for k in range(j + 1, len(row)) if row[k]), None)
                if k is not None and NUM_RE.match(row[k]):
                    row[k] = f"{v}{row[k]}" if v != "$" else f"${row[k]}"
                    row[j] = ""
            elif v == "%" and j > 0:
                k = next((k for k in range(j - 1, -1, -1) if row[k]), None)
                if k is not None and NUM_RE.match(row[k]):
                    row[k] += "%"
                    row[j] = ""
    keep = [j for j in range(t.num_cols) if any(r[j] for r in grid)]
    grid = [[r[j] for j in keep] for r in grid]

    def is_header_row(r: list[str]) -> bool:
        vals = [v for v in r[1:] if v]
        return bool(vals) and all(not NUM_RE.match(v) or YEAR_RE.match(v.strip()) for v in vals)

    # A header row must *look* like one (no non-year numbers), whatever the parser flagged: PyMuPDF flags
    # row 0 whenever the header is not outside the table, which turned data rows into column labels (v1 bug).
    header_rows = 0
    for i, r in enumerate(grid[:4]):
        if is_header_row(r):
            header_rows = i + 1
        else:
            break
    columns = []
    for j in range(len(keep)):
        parts = [grid[i][j] for i in range(header_rows) if grid[i][j]]
        columns.append(" ".join(dict.fromkeys(parts)))
    rows = [(i, grid[i][0] if grid[i] else "", grid[i][1:]) for i in range(header_rows, len(grid))]
    return NormTable(columns=columns, rows=rows, header_rows=header_rows, col_map=keep)


def detect_units(*texts: str | None) -> str | None:
    for t in texts:
        if t:
            m = UNIT_RE.search(t)
            if m:
                return m.group(0).strip()
    return None


def _row_line(label: str, values: list[str], columns: list[str]) -> str:
    pairs = []
    for j, v in enumerate(values):
        if not v:
            continue
        col = columns[j + 1] if j + 1 < len(columns) else ""
        pairs.append(f"{col} = {v}" if col else v)
    if not pairs:
        return f"[{label}]" if label else ""
    return f"{label}: " + "; ".join(pairs) if label else "; ".join(pairs)


# --------------------------------------------------------------------------- layout chunker
def chunk_layout(parse: ParseResult, meta: DocMeta) -> list[Chunk]:
    chunks: list[Chunk] = []
    furniture = _furniture_texts(parse.pages)
    section: list[tuple[int, str]] = []  # heading stack (level, text)
    header = meta.header()

    def path() -> list[str]:
        return [t for _, t in section]

    for page in parse.pages:
        blocks = page.blocks
        captions = {b.caption_block_id for b in blocks if b.caption_block_id}
        buf: list[PageBlock] = []

        def flush() -> None:
            if not buf:
                return
            _emit_text(chunks, buf, page, meta, path(), header)
            buf.clear()

        for i, b in enumerate(blocks):
            if b.kind == "heading":
                flush()
                if _is_furniture(b, furniture):
                    continue
                lvl = 0 if b.role == "title" else (b.level or 1)
                while section and section[-1][0] >= lvl:
                    section.pop()
                section.append((lvl, (b.text or "").strip()[:160]))
            elif b.kind == "table" and b.table is not None:
                flush()
                prev = [x for x in blocks[max(0, i - 2):i] if x.kind != "table" and x.text]
                _emit_table(chunks, b, page, meta, path(), header, blocks, prev)
            elif b.kind == "figure":
                flush()
                _emit_figure(chunks, b, page, meta, path(), header, blocks, i)
            else:
                if b.id in captions or _is_furniture(b, furniture):
                    continue  # captions are folded into their table/figure chunk
                if buf and _words(" ".join(x.text or "" for x in buf)) + _words(b.text or "") > TEXT_WORD_BUDGET:
                    flush()
                buf.append(b)
        flush()
    for n, c in enumerate(chunks):
        c.ordinal = n
    return chunks


def _emit_text(chunks: list[Chunk], buf: list[PageBlock], page: DocumentPage, meta: DocMeta,
               spath: list[str], header: str) -> None:
    pieces: list[tuple[str, list[PageBlock]]] = []
    for b in buf:
        text = (b.text or "").strip()
        if _words(text) <= TEXT_WORD_BUDGET:
            pieces.append((text, [b]))
            continue
        cur: list[str] = []
        for sent in SENT_SPLIT_RE.split(text):  # oversized single block: split at sentence boundaries
            if cur and _words(" ".join(cur)) + _words(sent) > TEXT_WORD_BUDGET:
                pieces.append((" ".join(cur), [b]))
                cur = []
            cur.append(sent)
        if cur:
            pieces.append((" ".join(cur), [b]))
    # merge consecutive pieces up to budget (pieces of a split block stay separate units)
    groups: list[tuple[list[str], list[PageBlock]]] = []
    for text, bs in pieces:
        if groups and _words(" ".join(groups[-1][0])) + _words(text) <= TEXT_WORD_BUDGET and bs[0].id not in {x.id for x in groups[-1][1]}:
            groups[-1][0].append(text)
            groups[-1][1].extend(bs)
        else:
            groups.append(([text], list(bs)))
    for part, (texts, bs) in enumerate(groups):
        content = "\n".join(texts)
        sec = " > ".join(spath)
        search = f"{header} | p.{page.number}" + (f" | {sec}" if sec else "") + f"\n{content}"
        chunks.append(Chunk(
            chunk_id=_cid(meta.document_id, CHUNKER_VERSION, "text", page.number, *[b.id for b in bs], part),
            chunk_set="layout", kind="text", document_id=meta.document_id, company=meta.company,
            period=meta.period, pages=[page.number], section_path=spath, content=content, search_text=search,
            blocks=[_ref(page, b) for b in {x.id: x for x in bs}.values()],
        ))


def _emit_table(chunks: list[Chunk], b: PageBlock, page: DocumentPage, meta: DocMeta, spath: list[str],
                header: str, blocks: list[PageBlock], prev: list[PageBlock]) -> None:
    nt = normalize_table(b)
    caption = next((x.text for x in blocks if x.id == b.caption_block_id), None)
    context = " ".join((x.text or "").strip() for x in prev) or None
    if context and nt.rows and nt.rows[0][1] and nt.rows[0][1] in context:
        context = context[:context.index(nt.rows[0][1])].strip() or None  # drop leaked table rows
    if context:
        context = context[-240:]
    columns_source = "table" if any(nt.columns[1:]) else None
    if columns_source is None and context:
        # Periods printed above the table ("Years ended December 31, 2022 2021 2020"): use them only if the
        # count matches the value columns exactly; otherwise leave columns unlabelled rather than guess.
        years = list(dict.fromkeys(CONTEXT_YEAR_RE.findall(context)))
        if years and len(years) == len(nt.columns) - 1:
            nt.columns = [nt.columns[0], *years]
            columns_source = "context"
    units = detect_units(caption, " ".join(nt.columns), *(r[1] for r in nt.rows[:3]), context)
    title = caption or context or (spath[-1] if spath else None)
    col_line = " | ".join(c for c in nt.columns[1:] if c)
    head = [f"[Table] {title}" if title else "[Table]"]
    if units:
        head.append(f"Units: {units}")
    if col_line:
        head.append(f"Columns: {col_line}")
    lines: list[tuple[int, str, str | None]] = []  # (orig row idx, line, group label)
    group = None
    for orig, label, values in nt.rows:
        if label and not any(values):
            group = label
            lines.append((orig, f"[{label}]", group))
        else:
            ln = _row_line(label, values, nt.columns)
            if ln:
                lines.append((orig, ln, group))
    cells_by_row: dict[int, list[Box]] = {}
    for c in b.table.cells:  # type: ignore[union-attr]
        if c.bbox and c.text:
            cells_by_row.setdefault(c.row, []).append(Box(c.bbox.l, c.bbox.t, c.bbox.r, c.bbox.b))

    def row_bbox(rows: list[int]) -> Box | None:
        boxes = [bx for r in rows for bx in cells_by_row.get(r, [])]
        if not boxes:
            return None
        out = boxes[0]
        for bx in boxes[1:]:
            out = out.union(bx)
        return out

    if not lines:
        return  # a table with no non-empty rows carries no evidence
    body = "\n".join(ln for _, ln, _ in lines)
    sec = " > ".join(spath)
    base_meta = {"caption": caption, "title": title, "units": units, "columns": nt.columns, "columnsSource": columns_source,
                 "tableBlockId": b.id, "totalRows": len(nt.rows), "headerRows": nt.header_rows}
    if _words(body) + _words(" ".join(head)) <= TABLE_WORD_BUDGET:
        groups = [lines]
    else:
        groups, cur = [], []
        for item in lines:
            starts_group = item[1].startswith("[") and cur
            if cur and (_words(" ".join(x[1] for x in cur)) + _words(item[1]) > TABLE_GROUP_WORD_BUDGET or starts_group):
                groups.append(cur)
                cur = []
            cur.append(item)
        if cur:
            groups.append(cur)
    for part, g in enumerate(groups):
        rows = [x[0] for x in g]
        grp = g[0][2]
        gh = list(head)
        if len(groups) > 1 and grp and not g[0][1].startswith("["):
            gh.append(f"[{grp}] (continued)")
        content = "\n".join(gh + [x[1] for x in g])
        search = f"{header} | p.{page.number}" + (f" | {sec}" if sec else "") + f"\n{content}"
        bbox = row_bbox(rows) if len(groups) > 1 else None
        refs = [_ref(page, b, bbox)]
        chunks.append(Chunk(
            chunk_id=_cid(meta.document_id, CHUNKER_VERSION, "table", page.number, b.id, part),
            chunk_set="layout", kind="table", document_id=meta.document_id, company=meta.company,
            period=meta.period, pages=[page.number], section_path=spath, content=content, search_text=search,
            blocks=refs,
            meta={**base_meta, "part": part, "parts": len(groups), "rowRange": [min(rows), max(rows)] if rows else None},
        ))


def _emit_figure(chunks: list[Chunk], b: PageBlock, page: DocumentPage, meta: DocMeta, spath: list[str],
                 header: str, blocks: list[PageBlock], i: int) -> None:
    caption = b.figure.caption if b.figure else None
    classes = [c.class_name for c in (b.figure.classification if b.figure else [])][:2]
    ctx_blocks = [x for x in (blocks[i - 1:i] + blocks[i + 1:i + 3]) if x.kind == "paragraph" and x.text
                  and x.id != b.caption_block_id]
    context = " ".join((x.text or "").strip() for x in ctx_blocks)[:600]
    parts = [f"[Figure] {caption}" if caption else "[Figure] (no caption detected)"]
    if classes:
        parts.append("Detected type: " + ", ".join(classes))
    if context:
        parts.append(f"Context: {context}")
    parts.append("Note: figure content (values) is not extracted from the image; see the crop.")
    content = "\n".join(parts)
    sec = " > ".join(spath)
    refs = [_ref(page, b)] + [_ref(page, x) for x in blocks if x.id == b.caption_block_id]
    chunks.append(Chunk(
        chunk_id=_cid(meta.document_id, CHUNKER_VERSION, "figure", page.number, b.id),
        chunk_set="layout", kind="figure", document_id=meta.document_id, company=meta.company,
        period=meta.period, pages=[page.number], section_path=spath, content=content,
        search_text=f"{header} | p.{page.number}" + (f" | {sec}" if sec else "") + f"\n{content}",
        blocks=refs,
        meta={"caption": caption, "classification": classes, "figureBlockId": b.id,
              "imageUrl": b.figure.image_url if b.figure else None},
    ))


# --------------------------------------------------------------------------- flat baseline
def chunk_flat(pdf_path: Path, meta: DocMeta) -> list[Chunk]:
    import pymupdf

    chunks: list[Chunk] = []
    header = meta.header()
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            n = page.number + 1
            words = page.get_text("words", sort=True)
            if not words:
                continue
            w, h = float(page.rect.width), float(page.rect.height)
            start = 0
            while True:
                win = words[start:start + FLAT_WINDOW]
                l, t = min(x[0] for x in win), min(x[1] for x in win)
                r, b = max(x[2] for x in win), max(x[3] for x in win)
                content = " ".join(x[4] for x in win)
                chunks.append(Chunk(
                    chunk_id=_cid(meta.document_id, FLAT_CHUNKER_VERSION, n, start),
                    chunk_set="flat", kind="window", document_id=meta.document_id, company=meta.company,
                    period=meta.period, pages=[n], section_path=[], content=content,
                    search_text=f"{header} | p.{n}\n{content}",
                    blocks=[BlockRef(n, None, (round(l, 2), round(t, 2), round(r, 2), round(b, 2)), w, h, "window")],
                    chunker_version=FLAT_CHUNKER_VERSION,
                ))
                if start + FLAT_WINDOW >= len(words):
                    break
                start += FLAT_STRIDE
    for i, c in enumerate(chunks):
        c.ordinal = i
    return chunks

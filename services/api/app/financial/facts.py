"""Geometric table normalization: parsed table cells (+ page words) -> FinancialFacts.

Why geometry: the parsed grid's column indices are NOT consistent across rows (PyMuPDF splits a '$' into its own
cell on some rows only, shifting the number by one column).  Values are therefore aligned into "slots" by the
x-position of their right edge (financial numbers are right-aligned), and each slot's header is built from
  (a) header rows inside the table and (b) page words printed above the table whose x-centre lies over the slot.
Periods are read ONLY from text aligned with the slot.  A year that appears in the table title but not over the
column does not bind (the column stays period-unknown).  Cumulative / plan-to-date / YTD headers are typed as such.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.financial.numbers import parse_amount
from app.financial.schema import (
    NORMALIZATION_VERSION,
    FinancialFact,
    PeriodInfo,
    TableNormalization,
    ValueSlot,
)
from app.schemas import BBox, PageBlock

Word = tuple[float, float, float, float, str]  # x0, y0, x1, y1, text

CURRENCY_CELLS = {"$": "$", "US$": "US$", "€": "€", "£": "£", "¥": "¥", "C$": "C$", "A$": "A$"}
NIL = {"—", "–", "-", "— ", "n/a", "N/A", "nm", "NM", "*"}
MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December|"
          "Jan\\.?|Feb\\.?|Mar\\.?|Apr\\.?|Jun\\.?|Jul\\.?|Aug\\.?|Sept?\\.?|Oct\\.?|Nov\\.?|Dec\\.?")
DATE_RE = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}}),?\s+((?:19|20)\d{{2}})\b", re.IGNORECASE)
NUMDATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/((?:19|20)\d{2})\b")
YEAR_RE = re.compile(r"(?<![\d/])((?:19|20)\d{2})(?![\d/])")
CUMULATIVE_RE = re.compile(r"\b(to[- ]date|through|cumulative|inception|since)\b", re.IGNORECASE)
QUARTER_RE = re.compile(r"\b(three months|quarter|q[1-4])\b", re.IGNORECASE)
YTD_RE = re.compile(r"\b(six months|nine months|year[- ]to[- ]date|ytd)\b", re.IGNORECASE)
ANNUAL_RE = re.compile(r"\b(years? ended|fiscal years? ended|twelve months|full[- ]year|for the years?)\b", re.IGNORECASE)
POINT_RE = re.compile(r"\b(balance sheets?|financial position|as of|at december|at year[- ]end)\b", re.IGNORECASE)
YEAR_ONLY = re.compile(r"(?:FY\s?)?(?:19|20)\d{2}")
UNIT_RE = re.compile(r"\b(in\s+)?(thousands|millions|billions|000s|'000|mn|bn)\b", re.IGNORECASE)
MONTH_NUM = {m[:3].lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
     "December"], start=1)}


@dataclass
class _Item:
    row: int
    cols: list[int]
    text: str
    l: float
    t: float
    r: float
    b: float


@dataclass
class _Row:
    index: int
    label: str
    items: list[_Item] = field(default_factory=list)


def _merge_row(cells: list) -> list[_Item]:
    """Merge currency-symbol, '%' and ')' fragments into the adjacent number; keep original cell coordinates."""
    items: list[_Item] = []
    pending: tuple[str, object] | None = None
    for c in cells:
        txt = (c.text or "").strip()
        if not txt or c.bbox is None:
            continue
        bb = c.bbox
        if txt in CURRENCY_CELLS:
            pending = (CURRENCY_CELLS[txt], c)
            continue
        if txt in ("%", "%)", ")%", ")") and items:
            prev = items[-1]
            if txt == "%":
                prev.text = prev.text + "%"
            elif prev.text.count("(") > prev.text.count(")"):
                prev.text = prev.text + ")" + ("%" if "%" in txt else "")
            else:
                prev.text = prev.text + txt
            prev.cols.append(c.col)
            prev.r = max(prev.r, bb.r)
            continue
        it = _Item(row=c.row, cols=[c.col], text=txt, l=bb.l, t=bb.t, r=bb.r, b=bb.b)
        if pending:
            sym, pc = pending
            it.text = sym + txt if not txt.startswith("(") else f"({sym}{txt[1:]}"
            it.cols.insert(0, pc.col)
            it.l = min(it.l, pc.bbox.l)
            pending = None
        items.append(it)
    return items


def _is_valueish(text: str) -> bool:
    return parse_amount(text) is not None or text.strip() in NIL


def _cluster_slots(items: Sequence[_Item], min_overlap: float = 0.5) -> list[list[_Item]]:
    """Group value cells into columns by horizontal interval overlap (robust to ')' or '%' hanging past the
    right edge and to '$' cells merged on some rows only)."""
    groups: list[list[_Item]] = []
    spans: list[list[float]] = []
    for it in sorted(items, key=lambda i: (i.l + i.r) / 2):
        w = max(it.r - it.l, 1.0)
        for g, sp in zip(groups, spans, strict=True):
            ov = min(it.r, sp[1]) - max(it.l, sp[0])
            if ov > 0 and ov / min(w, max(sp[1] - sp[0], 1.0)) >= min_overlap:
                g.append(it)
                sp[0], sp[1] = min(sp[0], it.l), max(sp[1], it.r)
                break
        else:
            groups.append([it])
            spans.append([it.l, it.r])
    order = sorted(range(len(groups)), key=lambda k: spans[k][0])
    return [groups[k] for k in order]


def _period_from(header: str | None, context: str, source: str) -> PeriodInfo:
    if not header:
        return PeriodInfo(label=None, period_type="unknown", source="unknown")
    dates = [(m.group(3), MONTH_NUM.get(m.group(1)[:3].lower()), m.group(2)) for m in DATE_RE.finditer(header)]
    dates += [(m.group(3), int(m.group(1)), m.group(2)) for m in NUMDATE_RE.finditer(header)]
    years = {int(y) for y in YEAR_RE.findall(header)} | {int(d[0]) for d in dates}
    end_date = None
    if len(dates) == 1 and dates[0][1]:
        y, mth, d = dates[0]
        end_date = f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"
    fiscal_year = next(iter(years)) if len(years) == 1 else None
    if fiscal_year is None and end_date is None:
        return PeriodInfo(label=header, period_type="unknown", source="unknown")
    if CUMULATIVE_RE.search(header):
        ptype = "cumulative"
    elif YTD_RE.search(header):
        ptype = "ytd"
    elif QUARTER_RE.search(header):
        ptype = "quarterly"
    elif ANNUAL_RE.search(header):
        ptype = "annual"
    elif CUMULATIVE_RE.search(context) and not ANNUAL_RE.search(context):
        ptype = "cumulative"
    elif YTD_RE.search(context):
        ptype = "ytd"
    elif QUARTER_RE.search(context):
        ptype = "quarterly"
    elif ANNUAL_RE.search(context):
        ptype = "annual"
    elif end_date and (POINT_RE.search(context) or "ended" not in (header + " " + context).lower()):
        ptype = "point_in_time"
    else:
        ptype = "unknown"
    return PeriodInfo(label=header, fiscal_year=fiscal_year, end_date=end_date, period_type=ptype, source=source)  # type: ignore[arg-type]


PERIOD_WORDS = re.compile(r"\b(ended|months|quarter|year|to date|through|cumulative|weeks)\b", re.IGNORECASE)


def _phrase_groups(words: Sequence[Word], gap: float = 18.0) -> list[list[Word]]:
    out: list[list[Word]] = []
    for w in sorted(words, key=lambda w: w[0]):
        if out and w[0] - out[-1][-1][2] <= gap:
            out[-1].append(w)
        else:
            out.append([w])
    return out


def _lines(words: Sequence[Word]) -> list[list[Word]]:
    out: dict[int, list[Word]] = {}
    for w in words:
        out.setdefault(int(round(w[3] / 3.0)), []).append(w)
    return [sorted(v, key=lambda w: w[0]) for _, v in sorted(out.items())]


def _scale_from(text: str) -> tuple[str, str] | None:
    m = UNIT_RE.search(text)
    if not m:
        return None
    unit = m.group(2).lower()
    scale = {"thousands": "thousands", "000s": "thousands", "'000": "thousands", "millions": "millions",
             "mn": "millions", "billions": "billions", "bn": "billions"}[unit]
    start = text.rfind("(", 0, m.start())
    end = text.find(")", m.end())
    snippet = text[start:end + 1] if 0 <= start and end > 0 and end - start < 90 else text[max(0, m.start() - 20):m.end() + 30]
    return scale, snippet.strip()


SEGMENT_RE = re.compile(r"\b(segments?|divisions?|by segment)\b", re.IGNORECASE)
CONSOLIDATED_RE = re.compile(r"\bconsolidated\b|\bgroup (?=(income|balance|cash|statement|results|financial))",
                             re.IGNORECASE)


def scope_from(text: str) -> tuple[str, str | None]:
    """Reporting scope stated in table context: segment beats consolidated; otherwise unknown."""
    m = SEGMENT_RE.search(text or "")
    if m:
        return "segment", m.group(0)
    m = CONSOLIDATED_RE.search(text or "")
    if m:
        return "consolidated", m.group(0).strip()
    return "unknown", None


def _currency_from(text: str, items: Sequence[_Item]) -> tuple[str | None, str | None]:
    for code, rx in (("USD", r"\b(USD|U\.S\. dollars?|US dollars?)\b|US\$"), ("EUR", r"\b(EUR|euros?)\b|€"),
                     ("GBP", r"\b(GBP|pounds sterling|sterling)\b|£"), ("JPY", r"\b(JPY|yen)\b|¥")):
        m = re.search(rx, text, re.IGNORECASE)
        if m:
            return code, m.group(0)
    m = re.search(r"\bdollars?\b", text, re.IGNORECASE)
    if m:
        return "dollar", m.group(0)
    if any(i.text.lstrip("(").startswith("$") for i in items):
        return "dollar", "$ in table cells"
    return None, None


def normalize_table(block: PageBlock, page_number: int, page_words: Sequence[Word] | None, *, document_id: str,
                    issuer: str | None, source_sha256: str, parser: str, parser_version: str,
                    context_text: str = "", band: float = 80.0, lead_in_text: str = "",
                    document_units: tuple[int, str, str] | None = None) -> TableNormalization:
    """document_units: (page, scale, verbatim sentence) of the last document-level statement such as
    "tabular dollars are in millions" on or before this page; used only when the table states no units."""
    td = block.table
    assert td is not None
    by_row: dict[int, list] = {}
    for c in td.cells:
        by_row.setdefault(c.row, []).append(c)
    rows: list[_Row] = []
    for r in sorted(by_row):
        cells = sorted(by_row[r], key=lambda c: c.col)
        label_cell = next((c for c in cells if c.col == 0), None)
        label = (label_cell.text or "").strip() if label_cell else ""
        rest = [c for c in cells if c.col != 0]
        rows.append(_Row(index=r, label=label, items=_merge_row(rest)))
    def is_data_row(rw: _Row) -> bool:
        return any(_is_valueish(it.text) and not YEAR_ONLY.fullmatch(it.text.strip()) for it in rw.items)

    first_data = next((i for i, rw in enumerate(rows) if is_data_row(rw)), len(rows))
    header_rows, data_rows = rows[:first_data], rows[first_data:]
    value_items = [it for rw in data_rows for it in rw.items if _is_valueish(it.text)]
    groups = _cluster_slots(value_items)
    slots = [{"x0": min(i.l for i in g), "x1": max(i.r for i in g), "header": []} for g in groups]

    def slot_of(l: float, r: float) -> int | None:
        """Slot whose x-range contains the centre of [l, r] (with a small margin); nearest centre on ties."""
        cx = (l + r) / 2
        cands = [k for k, sl in enumerate(slots) if sl["x0"] - 10 <= cx <= sl["x1"] + 10]
        if not cands:
            return None
        return min(cands, key=lambda k: abs(cx - (slots[k]["x0"] + slots[k]["x1"]) / 2))

    item_slot: dict[int, int] = {}
    for k, g in enumerate(groups):
        for it in g:
            item_slot[id(it)] = k
    # (a) header rows inside the table
    stub_context: list[str] = []
    for rw in header_rows:
        if rw.label:
            stub_context.append(rw.label)
        for it in rw.items:
            k = slot_of(it.l, it.r)
            if k is not None:
                slots[k]["header"].append((it.t, it.l, it.text, "column_header"))
    # (b) page words printed above the table, over each value column
    if page_words and slots:
        top = block.bbox.t
        width = block.bbox.r - block.bbox.l
        above = [w for w in page_words if w[3] <= top + 2 and w[1] >= top - band and w[2] >= block.bbox.l - 5]
        for line in reversed(_lines(above)):  # closest line first; stop at the first paragraph-like line
            span = line[-1][2] - line[0][0]
            if len(line) >= 8 and span > 0.6 * width:
                break
            stub = [w for w in line if (w[0] + w[2]) / 2 < slots[0]["x0"] - 15]
            stub_context.extend(w[4] for w in stub)
            over = [w for w in line if w not in stub]
            if not over:
                continue
            if any(ch.isdigit() for w in over for ch in w[4]):
                for w in over:  # years / dates: bind word by word to the column below it
                    k = slot_of(w[0], w[2])
                    if k is None:
                        stub_context.append(w[4])
                    else:
                        slots[k]["header"].append((w[1], w[0], w[4], "column_header_geometric"))
                continue
            text = " ".join(w[4] for w in over)
            phrases = _phrase_groups(over)
            if PERIOD_WORDS.search(text) and len(phrases) >= 2:
                # spanning period headers such as "Three Months Ended | Six Months Ended": nearest phrase per column
                for k, sl in enumerate(slots):
                    c = (sl["x0"] + sl["x1"]) / 2
                    ph = min(phrases, key=lambda g: abs(c - (g[0][0] + g[-1][2]) / 2))
                    slots[k]["header"].append((ph[0][1], 0.0, " ".join(w[4] for w in ph), "column_header_geometric"))
            else:
                stub_context.append(text)  # titles, units lines, a single spanning header: table-level context
    stub_text = " ".join(dict.fromkeys(stub_context))
    ctx = " ".join(x for x in (stub_text, context_text) if x)
    slot_models: list[ValueSlot] = []
    for k, s in enumerate(slots):
        parts = sorted(s["header"])
        header = " ".join(p[2] for p in parts) or None
        source = "column_header_geometric" if any(p[3] == "column_header_geometric" for p in parts) else "column_header"
        slot_models.append(ValueSlot(index=k, x0=round(s["x0"], 2), x1=round(s["x1"], 2), header_text=header,
                                     period=_period_from(header, ctx, source)))
    unit_src = " ".join([stub_text, *(s.header_text or "" for s in slot_models), context_text])
    sc = _scale_from(unit_src)
    scale, units_text = (sc if sc else ("unknown", None))
    doc_units_src = None
    if scale == "unknown" and document_units is not None:
        scale = document_units[1]
        doc_units_src = f"document statement p{document_units[0]}: {document_units[2]}"
    currency, currency_src = _currency_from(" ".join([stub_text, context_text]), value_items)
    scope, scope_src = scope_from(ctx)
    facts: list[FinancialFact] = []
    group = None
    collisions: list[str] = []
    for rw in data_rows:
        per_slot: dict[int, int] = {}
        for it in rw.items:
            if id(it) in item_slot:
                per_slot[item_slot[id(it)]] = per_slot.get(item_slot[id(it)], 0) + 1
        clash = {k for k, n in per_slot.items() if n > 1}
        if clash:
            collisions.append(f"row {rw.index}: {sorted(clash)}")
        if rw.label and not rw.items:
            group = rw.label
            continue
        for it in rw.items:
            k = item_slot.get(id(it))
            if k is None:
                continue
            raw = it.text
            p = parse_amount(raw)
            if p is not None:
                status, value = "parsed", str(p.value)
            elif raw.strip() in NIL:
                status, value = "nil", None
            elif re.search(r"\d", raw):
                status, value = "malformed", None
            else:
                status, value = "non_numeric", None
            is_pct = bool(p and p.percent)
            label_l = rw.label.lower()
            f_scale = "percent" if is_pct else ("per_share" if "per share" in label_l else scale)
            fid = "fact_" + hashlib.sha256(
                f"{document_id}|{block.id}|{rw.index}|{k}|{it.cols[0]}|{NORMALIZATION_VERSION}".encode()).hexdigest()[:24]
            period = slot_models[k].period
            if k in clash:  # two values share one column slot: the period binding is ambiguous -> unknown
                period = PeriodInfo(label=slot_models[k].header_text, period_type="unknown", source="unknown")
            facts.append(FinancialFact(
                fact_id=fid, document_id=document_id, issuer=issuer, source_sha256=source_sha256,
                table_id=block.id, page=page_number, row_index=rw.index, col_indices=it.cols, slot_index=k,
                row_label=rw.label, row_group=group, column_header=slot_models[k].header_text, cell_text=raw,
                value=value, value_status=status, is_percent=is_pct, period=period,  # type: ignore[arg-type]
                scale=f_scale,  # type: ignore[arg-type]
                scale_source=(units_text or doc_units_src) if f_scale == scale else ("percent sign" if is_pct else "row label 'per share'"),
                currency=currency, currency_source=currency_src, scope=scope, scope_source=scope_src,  # type: ignore[arg-type]
                bbox=BBox(l=round(it.l, 2), t=round(it.t, 2), r=round(it.r, 2), b=round(it.b, 2)),
                parser=parser, parser_version=parser_version))
    warnings = []
    unknown = [s.index for s in slot_models if s.period.period_type == "unknown" and s.period.fiscal_year is None]
    if unknown:
        warnings.append(f"value columns {unknown} have no aligned period header")
    if collisions:
        warnings.append("ambiguous column binding (several values in one column) for " + "; ".join(collisions[:5]))
    if scale == "unknown":
        warnings.append("no units statement found for the table")
    elif doc_units_src:
        warnings.append(f"units taken from {doc_units_src}")
    # lead_in_text (text that precedes the table on the PREVIOUS page) is kept as descriptive context only: it
    # is never used for units, currency, scope or periods, which could belong to a different table
    title = " ".join(x for x in (lead_in_text, ctx) if x) or None
    return TableNormalization(table_id=block.id, page=page_number, title_context=title, units_text=units_text,
                              scale=scale, currency=currency, scope=scope, slots=slot_models, facts=facts,  # type: ignore[arg-type]
                              warnings=warnings)


DOC_UNITS_RE = re.compile(r"tabular (?:dollars|amounts)[^.]{0,80}?\b(thousands|millions|billions)\b[^.]{0,80}\.",
                          re.IGNORECASE)


def document_unit_statements(page_texts: Sequence[str]) -> list[tuple[int, str, str]]:
    """Explicit document-wide units declarations, e.g. 'tabular dollars are in millions, except per share'."""
    out = []
    for i, t in enumerate(page_texts, start=1):
        for m in DOC_UNITS_RE.finditer(" ".join(t.split())):
            out.append((i, m.group(1).lower(), m.group(0)))
    return out


def units_for_page(statements: Sequence[tuple[int, str, str]], page: int) -> tuple[int, str, str] | None:
    prior = [s for s in statements if s[0] <= page]
    return prior[-1] if prior else None

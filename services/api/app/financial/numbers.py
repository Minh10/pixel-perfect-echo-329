"""Strict financial number parsing and fail-closed numeric token scanning.

`parse_amount` accepts only well-formed financial numbers:
    1,577   1577   -1,577   (1,577)   $1,577   $(3,547)   ($3,547)   -$3,547   US$12.5
    12.4%   (0.6)%   (0.6) %   (0.6%)   -0.6%   0   0.00   +12.4%
and rejects ambiguous or malformed ones (bad thousands grouping "1,57,7", unbalanced parentheses "(7.0",
double signs "-(3)", repeated separators "12..4").  It never strips characters it does not understand.

`scan_numeric_tokens` finds EVERY numeric-looking span in free text (e.g. an LLM answer) and classifies it:
    value      a parsed amount or percentage
    year       a bare 4-digit year 1900-2100 (also inside FY2022 / Q2 2023)
    date       a day or month number inside a written date ("December 31, 2022" -> 31)
    reference  an identifier, not a quantity: Note 12, Item 7, page 56, Table 1, E3, 10-K, Rule 10b5-1
    malformed  numeric-looking but not a well-formed number -> callers must FAIL CLOSED
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

TokenKind = Literal["value", "year", "date", "reference", "malformed"]

_DASHES = str.maketrans({"−": "-", "–": "-", "—": "-", " ": " ", "\xa0": " "})
_CURRENCY = r"(?:US\$|U\.S\.\$|C\$|A\$|HK\$|S\$|\$|€|£|¥|₹|₫)"
_DIGITS = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_AMOUNT_RE = re.compile(
    rf"""^\s*
    (?P<sign1>[+-])?\s*
    (?P<open>\()?\s*
    (?P<cur1>{_CURRENCY})?\s*
    (?P<sign2>[+-])?\s*
    (?P<open2>\()?\s*
    (?P<cur2>{_CURRENCY})?\s*
    (?P<num>{_DIGITS})
    \s*(?P<pct1>%)?\s*
    (?P<close2>\))?\s*
    (?P<close>\))?\s*
    (?P<pct2>%)?\s*$""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class ParsedNumber:
    value: Decimal
    percent: bool
    currency: str | None
    negative: bool


def parse_amount(text: str) -> ParsedNumber | None:
    """Parse one financial number or return None.  See module docstring for accepted forms."""
    t = text.translate(_DASHES).strip()
    if not t:
        return None
    m = _AMOUNT_RE.match(t)
    if not m:
        return None
    g = m.groupdict()
    opens = (g["open"] is not None) + (g["open2"] is not None)
    closes = (g["close"] is not None) + (g["close2"] is not None)
    if opens != closes or opens > 1:
        return None  # unbalanced or nested parentheses
    signs = [s for s in (g["sign1"], g["sign2"]) if s]
    if len(signs) > 1 or (signs and opens):
        return None  # "-(3)" or "+-3" are ambiguous
    if g["cur1"] and g["cur2"]:
        return None
    if g["pct1"] and g["pct2"]:
        return None
    try:
        v = Decimal(g["num"].replace(",", ""))
    except InvalidOperation:  # pragma: no cover - regex guarantees digits
        return None
    negative = bool(opens) or (signs == ["-"])
    if negative and v != 0:
        v = -v
    return ParsedNumber(value=v, percent=bool(g["pct1"] or g["pct2"]), currency=g["cur1"] or g["cur2"],
                        negative=negative and v != 0)


def parse_number(text: str) -> Decimal | None:
    p = parse_amount(text)
    return p.value if p else None


# --------------------------------------------------------------------------- scanning free text
_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december|"
           "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec")
_REF_WORDS = ("note|notes|item|items|table|tables|figure|fig|exhibit|page|pages|p|pp|section|part|rule|form|"
              "schedule|article|level|chapter|appendix|row|line|column|step|tier|footnote")
# A candidate span: optional sign/paren/currency, digits with separators, optional %/paren.
_CAND = re.compile(
    rf"[+\-]?\(?\s?(?:{_CURRENCY})?\s?[+\-]?\(?\d[\d,.]*\d?(?:\s?%)?\)?(?:\s?%)?"
)
_SCALE_WORDS = re.compile(r"\s*(thousand|million|billion|trillion|bn|mn|m|k)\b", re.IGNORECASE)


@dataclass(frozen=True)
class NumberToken:
    text: str
    start: int
    end: int
    kind: TokenKind
    value: Decimal | None = None
    percent: bool = False
    scale_word: str | None = None


def _prev_word(text: str, i: int) -> str:
    m = re.search(r"([A-Za-z.]+)\s*[#:]?\s*$", text[:i])
    return m.group(1).lower().rstrip(".") if m else ""


def scan_numeric_tokens(text: str) -> list[NumberToken]:
    t = text.translate(_DASHES)
    out: list[NumberToken] = []
    for m in _CAND.finditer(t):
        raw = m.group(0).rstrip()
        s, e = m.start(), m.start() + len(raw)
        lead = len(raw) - len(raw.lstrip())
        raw, s = raw.lstrip(), s + lead
        # trim trailing sentence punctuation that the greedy class may include ("1,577." / "2,535,")
        while raw and raw[-1] in ".," and not re.search(r"\d[.,]\d$", raw):
            raw, e = raw[:-1], e - 1
        # trim a leading '-' that belongs to a range or hyphenated word ("2020-2022", "10-K")
        before = t[s - 1] if s > 0 else " "
        after = t[e] if e < len(t) else " "
        if raw.startswith("-") and before.isalnum():
            raw, s = raw[1:], s + 1
        if not any(ch.isdigit() for ch in raw):
            continue
        before = t[s - 1] if s > 0 else " "
        # hyphen-joined to a word or number: "COVID-19", "10b5-1" are identifiers; "2020-2022" stays a year range
        if before == "-" and s >= 2 and t[s - 2].isalnum():
            core = re.sub(r"\D", "", raw)
            kind: TokenKind = "year" if re.fullmatch(r"(19|20)\d{2}", core) else "reference"
            out.append(NumberToken(raw, s, e, kind, Decimal(core) if kind == "year" else None))
            continue
        # identifiers glued to letters: FY2022, Q2, E3, 10-K, COVID-19, 401(k), H1
        if before.isalpha() or (after.isalpha() and after not in "kKmMbB") or (after == "-" and e + 1 < len(t) and t[e + 1].isalpha()):
            core = re.sub(r"\D", "", raw)
            if re.fullmatch(r"(19|20)\d{2}", core) and before.isalpha():
                out.append(NumberToken(raw, s, e, "year", Decimal(core)))
            else:
                out.append(NumberToken(raw, s, e, "reference"))
            continue
        if re.match(r"\([A-Za-z]\)", t[e:e + 3]):  # 401(k), 10(b): statutory identifiers
            out.append(NumberToken(raw, s, e, "reference"))
            continue
        prev = _prev_word(t, s)
        if prev in _REF_WORDS.split("|") and re.fullmatch(r"\d+[A-Za-z]?", raw.strip("()")):
            out.append(NumberToken(raw, s, e, "reference"))
            continue
        if prev in _MONTHS.split("|") and re.fullmatch(r"\d{1,2},?", raw):
            out.append(NumberToken(raw, s, e, "date", Decimal(raw.rstrip(","))))
            continue
        if re.fullmatch(r"(19|20)\d{2}", raw):
            out.append(NumberToken(raw, s, e, "year", Decimal(raw)))
            continue
        # m/d/yyyy or yyyy-mm-dd style dates
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", raw) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            out.append(NumberToken(raw, s, e, "date"))
            continue
        p = parse_amount(raw)
        if p is None:
            out.append(NumberToken(raw, s, e, "malformed"))
            continue
        sw = _SCALE_WORDS.match(t, e)
        out.append(NumberToken(raw, s, e, "value", p.value, p.percent, sw.group(1).lower() if sw else None))
    return out


def numbers_in(text: str) -> list[Decimal]:
    """All parsed numeric values (amounts, percentages and years) in text; references/dates excluded."""
    return [tok.value for tok in scan_numeric_tokens(text) if tok.kind in ("value", "year") and tok.value is not None]

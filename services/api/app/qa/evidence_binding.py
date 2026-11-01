"""Evidence-anchored operand validation (replaces the PR #2 phrase-list association checks).

An operand claim from the model quotes: the value text, the source row label (verbatim), the period, the metric
it represents, its scale and (optionally) currency.  Validation BINDS the claim to exactly one source fact:

  table evidence -> structured FinancialFacts of the cited table chunk (geometric column/period binding);
  text evidence  -> the single clause that contains the value, its metric phrase and its time expression.

Rules (each failure => the pipeline repairs once, then abstains; it never guesses):
  * value + row label must identify one fact; 0 matches = not found, >1 = ambiguous;
  * the fact's period must be KNOWN and equal the claimed period (a title year never binds a column);
  * cumulative / YTD / quarterly values are accepted only when the question asks for that period type;
  * metric paraphrases are accepted only via the explicit vocabulary (app/financial/vocabulary.py);
  * scale must equal the fact's stated scale (unknown scale fails closed); currency conversion is rejected;
  * derived metrics are validated on the FINAL value via calculation specs, never by requiring every input
    operand to carry the question's metric name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.financial.facts import _period_from  # noqa: PLC2701 - shared period parser
from app.financial.numbers import parse_amount, scan_numeric_tokens
from app.financial.vocabulary import (
    DEFINITION_RE,
    DERIVED,
    canonical_metrics,
    content_tokens,
    derived_metric,
)

YEAR_RE = re.compile(r"(?<![\d/])((?:19|20)\d{2})(?![\d/])")
CUMULATIVE_ASK = re.compile(r"\b(cumulative|to[- ]date|since inception|plan[- ]to[- ]date|through)\b", re.IGNORECASE)
YTD_ASK = re.compile(r"\b(year[- ]to[- ]date|ytd|six months|nine months|first half|first nine)\b", re.IGNORECASE)
QUARTER_ASK = re.compile(r"\b(quarter|three months|q[1-4])\b", re.IGNORECASE)
PRIOR_ASK = re.compile(r"\b(prior|previous|preceding|last) (fiscal )?year\b|year[- ]over[- ]year|\byoy\b", re.IGNORECASE)
CURRENCY_WORDS = {"USD": r"\b(usd|u\.s\. dollars?|us dollars?)\b|us\$", "EUR": r"\b(eur|euros?)\b|€",
                  "GBP": r"\b(gbp|sterling|pounds?)\b|£", "JPY": r"\b(jpy|yen)\b|¥"}
SCOPE_WORDS = {"consolidated": r"\b(consolidated|group[- ]wide|company[- ]wide)\b|^\s*group\b",
               "segment": r"\b(segments?|divisions?|business units?)\b"}


@dataclass
class OperandClaim:
    id: str
    quote: str
    row_label: str
    period: str | None
    metric: str
    scale: str
    currency: str | None = None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9%$().,&/-]+", " ", (s or "").lower().replace("\xa0", " ")).strip()


def _years(s: str | None) -> set[int]:
    return {int(y) for y in YEAR_RE.findall(s or "")}


def currencies_in(text: str) -> set[str]:
    return {code for code, rx in CURRENCY_WORDS.items() if re.search(rx, text or "", re.IGNORECASE)}


def _currency_ok(fact_currency: str | None, asserted: set[str]) -> tuple[bool, str]:
    if not asserted:
        return True, "no currency asserted"
    if fact_currency is None:
        return False, f"currency {sorted(asserted)} asserted but not stated in the source"
    if fact_currency == "dollar":
        bad = asserted - {"USD"}
        return (not bad, "dollar-denominated source" if not bad else f"source is in dollars, not {sorted(bad)}")
    return (asserted <= {fact_currency},
            f"source currency {fact_currency}" if asserted <= {fact_currency}
            else f"currency conversion unsupported: {sorted(asserted)} vs source {fact_currency}")


def _period_ok(fact_period: dict, claim_period: str | None, question: str) -> list[dict]:
    """One `operand_period_matches` check (year AND period type) plus `operand_period_in_question`."""
    fy, end, ptype = fact_period.get("fiscalYear"), fact_period.get("endDate"), fact_period.get("periodType", "unknown")
    label = fact_period.get("label")
    cy = _years(claim_period)

    def res(ok: bool, detail: str) -> list[dict]:
        return [{"check": "operand_period_matches", "ok": ok, "detail": detail}]

    if not claim_period or not cy:
        return res(False, "operand does not state its period")
    if fy is None and end is None:
        return res(False, "the source column has no aligned period header; period cannot be verified")
    src_year = fy if fy is not None else int(end[:4])
    if cy != {src_year}:
        return res(False, f"claimed {sorted(cy)} vs column period {label!r} ({src_year})")
    if ptype == "cumulative" and not CUMULATIVE_ASK.search(question):
        return res(False, f"cumulative column {label!r} used for a non-cumulative question")
    if ptype == "ytd" and not YTD_ASK.search(question):
        return res(False, f"year-to-date column {label!r} used for a non-YTD question")
    if ptype == "quarterly" and not QUARTER_ASK.search(question):
        return res(False, f"quarterly column {label!r} used for a non-quarterly question")
    checks = res(True, f"column period {label!r} ({src_year}, {ptype}"
                       + (", type not stated in source)" if ptype == "unknown" else ")"))
    qy = _years(question)
    if qy and not cy <= qy:
        allowed = bool(PRIOR_ASK.search(question)) and all(y + 1 in qy for y in cy)
        checks.append({"check": "operand_period_in_question", "ok": allowed,
                       "detail": f"operand year {sorted(cy)} vs question years {sorted(qy)}"
                       + ("" if allowed else "; not asked")})
    return checks


def _metric_ok(claim: OperandClaim, source_text: str) -> tuple[bool, str]:
    mt, st = content_tokens(claim.metric), content_tokens(source_text)
    if mt and mt <= st:
        return True, "metric named by the source row"
    mc, sc = canonical_metrics(claim.metric), canonical_metrics(source_text)
    if mc and mc & sc:
        return True, f"paraphrase via vocabulary {sorted(mc & sc)}"
    return False, f"metric {claim.metric!r} is not supported by source {source_text[:80]!r}"


def _scale_ok(fact_scale: str, claim_scale: str) -> tuple[bool, str]:
    if fact_scale == "unknown":
        return False, "the source does not state units/scale; not verified"
    if fact_scale == "per_share":
        return claim_scale in ("per_share", "units"), f"source scale per_share vs operand {claim_scale}"
    return fact_scale == claim_scale, f"source scale {fact_scale} vs operand {claim_scale}"


# --------------------------------------------------------------------------- table binding
def bind_table(claim: OperandClaim, facts: list[dict], question: str, context: str = "") -> tuple[list[dict], dict | None]:
    p = parse_amount(claim.quote)
    nums = [p.value] if p else [t.value for t in scan_numeric_tokens(claim.quote) if t.kind == "value"]
    if len(nums) != 1:
        return [{"check": "operand_cell_located", "ok": False, "detail": f"quote {claim.quote!r} is not one number"}], None
    target = nums[0]
    if re.fullmatch(r"(19|20)\d{2}", claim.quote.strip()):
        return [{"check": "operand_cell_located", "ok": False, "detail": "quote is a calendar year"}], None
    rl = _norm(claim.row_label)
    by_value = [f for f in facts if f.get("valueStatus") == "parsed" and f.get("value") is not None
                and abs(Decimal(f["value"])) == abs(target)]
    if not rl:
        return [{"check": "operand_cell_located", "ok": False, "detail": "operand does not quote its row label"}], None
    matched = [f for f in by_value if rl and (rl in _norm(f["rowLabel"] + " " + (f.get("rowGroup") or ""))
                                              or (_norm(f["rowLabel"]) and _norm(f["rowLabel"]) in rl))]
    if len(matched) > 1:  # the claim may name the row group (section) to disambiguate
        narrowed = [f for f in matched if f.get("rowGroup") and _norm(f["rowGroup"]) in rl]
        matched = narrowed or matched
    if len(matched) != 1:
        why = ("value not found in this table" if not by_value else
               "value not found in the quoted row" if not matched else "value/row match more than one cell")
        return [{"check": "operand_cell_located", "ok": False, "detail": f"{why} ({claim.quote} / {claim.row_label!r})"}], None
    f = matched[0]
    checks = [{"check": "operand_cell_located", "ok": True,
               "detail": f"row {f['rowLabel']!r} column {f.get('columnHeader')!r} cell {f['cellText']!r}"}]
    ok, d = _metric_ok(claim, " ".join(x for x in (f["rowLabel"], f.get("rowGroup") or "", context) if x))
    checks.append({"check": "operand_metric_supported", "ok": ok, "detail": d})
    checks += _period_ok(f.get("period") or {}, claim.period, question)
    ok, d = _scale_ok(f.get("scale", "unknown"), claim.scale)
    checks.append({"check": "operand_units_match", "ok": ok, "detail": d})
    if not f.get("isPercent"):
        asserted = currencies_in(" ".join(x for x in (claim.currency, claim.metric, claim.row_label) if x))
        ok, d = _currency_ok(f.get("currency"), asserted)
        checks.append({"check": "operand_currency_matches", "ok": ok, "detail": d})
        qcur = currencies_in(question)
        if qcur:
            ok, d = _currency_ok(f.get("currency"), qcur)
            checks.append({"check": "question_currency_supported", "ok": ok, "detail": d})
    claimed_scope = {k for k, rx in SCOPE_WORDS.items() if re.search(rx, claim.metric + " " + claim.row_label, re.IGNORECASE)}
    fs = f.get("scope", "unknown")
    if claimed_scope and fs not in claimed_scope:
        checks.append({"check": "operand_scope_matches", "ok": False,
                       "detail": f"claimed {sorted(claimed_scope)} vs source scope {fs}"
                       + (" (not stated in the source)" if fs == "unknown" else "")})
    else:
        checks.append({"check": "operand_scope_matches", "ok": True, "detail": f"source scope {fs}"})
    return checks, f


# --------------------------------------------------------------------------- narrative binding
_CLAUSE_SPLIT = re.compile(r",?\s+(?:and|while|whereas|but)\s+|;\s+", re.IGNORECASE)


def bind_text(claim: OperandClaim, text: str, question: str) -> tuple[list[dict], dict | None]:
    p = parse_amount(claim.quote)
    nums = [p.value] if p else [t.value for t in scan_numeric_tokens(claim.quote) if t.kind == "value"]
    if len(nums) != 1:
        return [{"check": "operand_cell_located", "ok": False, "detail": f"quote {claim.quote!r} is not one number"}], None
    target = nums[0]
    found = []
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text):
        parts = _CLAUSE_SPLIT.split(sent)
        clauses = parts if sum(bool(re.search(r"\d", c)) for c in parts) > 1 else [sent]
        for cl in clauses:
            toks = [t for t in scan_numeric_tokens(cl) if t.kind == "value" and abs(t.value) == abs(target)]
            if toks:
                found.append((sent, cl, toks[0]))
    if len(found) != 1:
        why = "value not found in the text" if not found else "value appears in more than one statement"
        return [{"check": "operand_cell_located", "ok": False, "detail": f"{why} ({claim.quote})"}], None
    sent, clause, tok = found[0]
    checks = [{"check": "operand_cell_located", "ok": True, "detail": f"clause {clause[:90]!r}"}]
    rl = _norm(claim.row_label)
    ok = bool(rl) and rl in _norm(clause)
    checks.append({"check": "operand_row_label_quoted", "ok": ok,
                   "detail": "metric phrase quoted from the clause holding the value" if ok
                   else f"{claim.row_label!r} not in the clause holding the value ({clause[:80]!r})"})
    ok, d = _metric_ok(claim, clause)
    checks.append({"check": "operand_metric_supported", "ok": ok, "detail": d})
    # the time expression nearest the value: its comma-delimited segment, then its clause, then the sentence;
    # each level is used only if it names exactly one year (otherwise abstain -- never pick one of several)
    seg = next((x for x in re.split(r",\s+", clause) if tok.text.strip() in x), clause)
    years: set[int] = set()
    for scope_text in (seg, clause, sent):
        ys = {int(t.value) for t in scan_numeric_tokens(scope_text) if t.kind == "year"}
        if ys:
            years = ys if len(ys) == 1 else set()
            break
    period = {"fiscalYear": next(iter(years)) if len(years) == 1 else None, "endDate": None,
              "periodType": "unknown", "label": clause[:80]}
    checks += _period_ok(period, claim.period, question)
    after = clause[clause.find(tok.text) + len(tok.text):][:16].lower()
    if tok.percent:
        src_scale = "percent"
    elif tok.scale_word or re.match(r"\s*(million|billion|thousand)", after):
        w = (tok.scale_word or re.match(r"\s*(million|billion|thousand)", after).group(1)).lower()
        src_scale = {"million": "millions", "m": "millions", "mn": "millions", "billion": "billions", "bn": "billions",
                     "thousand": "thousands", "k": "thousands"}.get(w, "unknown")
    else:
        src_scale = "units"
    ok = src_scale == claim.scale or (src_scale == "units" and claim.scale in ("units", "ratio", "per_share"))
    checks.append({"check": "operand_units_match", "ok": ok, "detail": f"statement scale {src_scale} vs operand {claim.scale}"})
    asserted = currencies_in(" ".join(x for x in (claim.currency, claim.metric) if x))
    src_cur = next(iter(currencies_in(clause)), None) or ("dollar" if "$" in clause else None)
    ok, d = _currency_ok(src_cur, asserted) if not tok.percent else (True, "percentage")
    checks.append({"check": "operand_currency_matches", "ok": ok, "detail": d})
    return checks, {"value": str(tok.value), "period": period, "scale": src_scale, "currency": src_cur}


# --------------------------------------------------------------------------- calculation specification
def calculation_checks(question: str, final_ref: str | None, final_metric: str | None, steps: list,
                       operand_metrics: dict[str, set[str]], operand_years: dict[str, set[int]]) -> list[dict]:
    """Validate the final value against the question: derived-metric spec, or base-metric identity."""
    checks: list[dict] = []
    dm = derived_metric(question)
    step_by_id = {s.id: s for s in steps}
    if dm and final_ref in step_by_id:
        ops, groups = DERIVED[dm]
        final_op = step_by_id[final_ref].op
        all_metrics = set().union(*operand_metrics.values()) if operand_metrics else set()
        missing = [sorted(g) for g in groups if not (g & all_metrics)]
        ok = final_op in ops and not missing
        detail = f"{dm}: final op {final_op}" + (f"; missing inputs {missing}" if missing else "")
        if dm == "growth":
            inputs = step_by_id[final_ref].args
            ms = [operand_metrics.get(a, set()) for a in inputs]
            ys = [operand_years.get(a, set()) for a in inputs]
            same_metric = len(ms) == 2 and bool(ms[0] & ms[1]) or (len(ms) == 2 and not ms[0] and not ms[1])
            ok = final_op == "percent_change" and same_metric and len(ys) == 2 and ys[0] != ys[1]
            detail = f"growth: {final_op} over the same metric in two periods ({ys})"
        checks.append({"check": "calculation_spec_valid", "ok": ok, "detail": detail})
    elif final_ref in step_by_id and DEFINITION_RE.search(question):
        named = canonical_metrics(question)
        used = set().union(*operand_metrics.values()) if operand_metrics else set()
        ok = not named or used <= named | {"revenue"} or bool(used & named)
        checks.append({"check": "calculation_spec_valid", "ok": ok,
                       "detail": f"question defines the formula; inputs {sorted(used)} vs named {sorted(named)}"})
    elif final_ref in step_by_id:
        checks.append({"check": "calculation_spec_valid", "ok": True,
                       "detail": "no registered specification for this calculation (inputs validated individually)"})
    qm = canonical_metrics(question) - {"free_cash_flow"}
    if final_ref and final_ref not in step_by_id and qm and not dm:
        om = operand_metrics.get(final_ref, set())
        ok = bool(om & qm) or not om
        checks.append({"check": "final_metric_matches_question", "ok": ok,
                       "detail": f"question {sorted(qm)} vs final value metric {sorted(om)}"})
    return checks


# --------------------------------------------------------------------------- legacy / text-table API
def facts_from_table_text(text: str, units: str | None = None) -> list[dict]:
    """Parse a serialized table chunk into fact dicts (periods ONLY from explicit column labels)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0] if lines and lines[0].lower().startswith("[table]") else ""
    unit_line = next((ln[6:].strip() for ln in lines if ln.lower().startswith("units:")), units or "")
    from app.financial.facts import _scale_from

    sc = _scale_from(unit_line or "")
    scale = sc[0] if sc else "unknown"
    types: dict[str, str] = {}
    pl = next((ln for ln in lines if ln.lower().startswith("periods:")), None)
    if pl:
        for part in pl[8:].split(" | "):
            m = re.match(r"(.*) \[(\w+)\]$", part.strip())
            if m:
                types[m.group(1)] = m.group(2)
    from app.financial.facts import _currency_from, scope_from

    currency = _currency_from(f"{title} {unit_line}", [])[0] or ("dollar" if "$" in text else None)
    scope = scope_from(title)[0]
    cl = next((ln for ln in lines if ln.lower().startswith("columns:")), None)
    columns = [c.strip() for c in cl[8:].split("|")] if cl else []
    out, group = [], None
    for ln in lines:
        low = ln.lower()
        if low.startswith(("[table]", "units:", "columns:", "periods:", "[figure]")):
            continue
        if ln.startswith("[") and ln.endswith("]"):
            group = ln[1:-1] if "continued" not in ln else group
            continue
        if ":" in ln:
            label, rest = ln.split(":", 1)
        elif group and re.search(r"\d", ln):
            label, rest = group, ln  # values listed under a label-only row
        else:
            continue
        segs = [x.strip() for x in rest.split(";") if x.strip()]
        positional = all(" = " not in x for x in segs) and len(segs) == len(columns)
        for i, seg in enumerate(segs):
            # explicit "column = value" pairs; positional binding only when the value count equals the
            # Columns line exactly (otherwise the column is unknown -- never inferred from the title)
            col, val = (seg.split(" = ", 1) if " = " in seg else (columns[i] if positional else None, seg))
            p = parse_amount(val)
            per = _period_from(col, title, "column_header") if col else {}
            per = per.model_dump(by_alias=True) if hasattr(per, "model_dump") else {"periodType": "unknown"}
            if col in types:
                per["periodType"] = types[col]
            out.append({"factId": None, "rowLabel": label.strip(), "rowGroup": group, "columnHeader": col,
                        "cellText": val, "value": str(p.value) if p else None, "valueStatus": "parsed" if p else "non_numeric",
                        "isPercent": bool(p and p.percent), "period": per,
                        "scale": "percent" if (p and p.percent) else ("per_share" if "per share" in label.lower() else scale),
                        "currency": currency, "scope": scope, "slotIndex": i})
    return out


def claim_from_label(label: str, quote: str, scale: str) -> OperandClaim:
    """Map the PR #2 single 'label' (metric + year) onto a structured claim."""
    years = YEAR_RE.findall(label)
    row = re.sub(r"\((?:[^)]*)\)", " ", label)
    row = YEAR_RE.sub(" ", row)
    row = re.sub(r"\b(USD|EUR|GBP|millions?|thousands?|billions?)\b", " ", row, flags=re.IGNORECASE)
    row = re.sub(r"\s+", " ", row).strip()
    return OperandClaim(id="op", quote=quote, row_label=row, period=" ".join(years) or None, metric=row,
                        scale=scale, currency=" ".join(currencies_in(label)) or None)


def operand_association_checks(*, kind: str, label: str, quote: str, scale: str, text: str, question: str,
                               units: str | None = None, facts: list[dict] | None = None,
                               claim: OperandClaim | None = None) -> list[dict]:
    """Compatibility entry point: bind one operand against table facts (or a serialized table) or a statement."""
    claim = claim or claim_from_label(label, quote, scale)
    if kind == "table":
        checks, _ = bind_table(claim, facts if facts is not None else facts_from_table_text(text, units), question,
                               context=text.splitlines()[0] if text else "")
        return checks
    if kind in ("text", "window"):
        checks, _ = bind_text(claim, text, question)
        return checks
    return []

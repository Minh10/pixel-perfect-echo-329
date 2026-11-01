"""Evidence-grounded financial QA.

    question -> document routing -> retrieval (layout chunks) -> labelled evidence (E1..Ek)
             -> LLM structured plan {status, answer, citations, operands, calculations, final}
             -> deterministic validation + calculation -> (one repair round) -> answer | abstention

Guarantees enforced in code (not by prompt alone):
  * every operand is a number quoted verbatim from a retrieved evidence item;
  * every calculation is a whitelisted operation executed with Decimal (no model-generated code runs);
  * every number in the answer text is grounded (cited evidence, operand, or rounded calculation result);
  * every citation points to a retrieved chunk with page/block/bbox provenance;
  * visual (chart-read) values are labelled as estimates, never as reported figures;
  * no confidence score is produced; abstention is explicit.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from decimal import Decimal

from app.config import Settings
from app.evaluation.metrics import numbers_in, parse_number
from app.indexing.store import ChunkStore
from app.qa import calculator as calc
from app.qa.evidence import chunk_ref, ranked, route_documents
from app.qa.llm import LLMError, LLMProvider, LLMRefusal, cost_usd
from app.qa.schemas import (
    Abstention,
    AnswerValue,
    Calculation,
    Citation,
    Operand,
    QARequest,
    QAResponse,
    Usage,
    ValidationReport,
)
from app.retrieval.search import Retriever

SCALE_ENUM = ["units", "thousands", "millions", "billions", "percent", "ratio", "per_share"]

PLAN_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "answer", "insufficiency_reason", "citations", "operands", "calculations", "final"],
    "properties": {
        "status": {"type": "string", "enum": ["answered", "insufficient_evidence"]},
        "answer": {"type": "string"},
        "insufficiency_reason": {"type": ["string", "null"]},
        "citations": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["evidence_id", "quote"],
            "properties": {"evidence_id": {"type": "string"}, "quote": {"type": "string"}}}},
        "operands": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "evidence_id", "quote", "label", "scale", "value_kind"],
            "properties": {"id": {"type": "string"}, "evidence_id": {"type": "string"}, "quote": {"type": "string"},
                           "label": {"type": "string"}, "scale": {"type": "string", "enum": SCALE_ENUM},
                           "value_kind": {"type": "string", "enum": ["reported", "visual_estimate"]}}}},
        "calculations": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "op", "args", "periods", "description"],
            "properties": {"id": {"type": "string"}, "op": {"type": "string", "enum": sorted(calc.OPS)},
                           "args": {"type": "array", "items": {"type": "string"}},
                           "periods": {"type": ["integer", "null"]}, "description": {"type": "string"}}}},
        "final": {"type": "object", "additionalProperties": False, "required": ["ref", "unit"],
                  "properties": {"ref": {"type": ["string", "null"]}, "unit": {"type": ["string", "null"]}}},
    },
}

SYSTEM_PROMPT = """You answer questions about company financial filings strictly from the numbered evidence excerpts provided.

Rules:
1. Use only the evidence. Do not use outside knowledge for any figure or fact.
2. If the evidence does not contain what the question needs, set status to "insufficient_evidence", leave operands and calculations empty, and explain what is missing in insufficiency_reason. Answering from partial or loosely related evidence is worse than abstaining.
3. Every number you rely on must be an operand whose quote is the exact number string as it appears in one evidence item (for example "(1,577)" or "$5,363" or "12.4%"). Set its scale from the excerpt's Units line or wording (thousands, millions, billions, percent, ratio, per_share, or units) and give a label naming the line item and period.
4. Never do arithmetic yourself. Express each calculation as a step using only the allowed operations, referencing operand ids or earlier step ids; the system executes the steps exactly. For percent_change and percent_of the argument order is [old, new] and [part, whole].
5. In "answer", write a concise answer. State a number only if it is an operand, the (rounded) result of one of your steps, or appears in a cited excerpt. Parentheses denote negative amounts or outflows.
6. Evidence is labelled TABLE (reported statement values), TEXT (narrative statements) or FIGURE. Values marked VISUAL ESTIMATE were read from a chart image and are approximate: use value_kind "visual_estimate", say "approximately", and never present them as exact reported figures. Prefer TABLE values over narrative text and over visual estimates when they conflict, and say which you used.
7. Cite every evidence item that supports the answer, each with a short verbatim quote from that item.
8. Set final.ref to the operand or step id holding the headline number (null if the answer is not numeric) and final.unit to its unit (for example "USD millions")."""


@dataclass
class EvidenceItem:
    label: str
    row: dict
    text: str  # what the model saw for this item (content + any visual estimates)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _render_evidence(items: list[EvidenceItem], budget: int) -> str:
    out, used = [], 0
    for it in items:
        r = it.row
        head = (f"[{it.label}] {r['kind'].upper()} | {r['company'] or '?'} | period {r['period'] or '?'} | "
                f"page {', '.join(map(str, r['pages']))}" + (f" | section: {' > '.join(r['section_path'])}" if r['section_path'] else ""))
        block = f"{head}\n{it.text}\n"
        if used + len(block) > budget and out:
            break
        out.append(block)
        used += len(block)
    return "\n".join(out)


class QAPipeline:
    def __init__(self, s: Settings, store: ChunkStore, retriever: Retriever, llm: LLMProvider,
                 documents: list[dict], visual_lookup=None) -> None:
        self.s, self.store, self.retriever, self.llm = s, store, retriever, llm
        self.documents = documents
        self.titles = {d["id"]: d["title"] for d in documents}
        self.visual_lookup = visual_lookup  # (document_id, block_id) -> interpretation text | None

    # ------------------------------------------------------------------ main entry
    def answer(self, req: QARequest) -> QAResponse:
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        warnings: list[str] = []
        routed = [] if req.document_ids else route_documents(req.question, self.documents)
        doc_ids = req.document_ids or ([d["documentId"] for d in routed] or None)
        if not req.document_ids and not routed:
            warnings.append("no company in the question matched a document; searched the whole corpus")
        method = req.method or self.s.qa_method
        chunk_set = req.chunk_set or self.s.qa_chunk_set
        k = req.top_k or self.s.qa_top_k
        t = time.perf_counter()
        res = self.retriever.search(req.question, method=method, chunk_set=chunk_set, document_ids=doc_ids, k=k)
        timings["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)
        warnings += res.warnings
        rows = self.store.get(h.chunk_id for h in res.hits)
        retrieved = ranked(res, rows, self.titles)
        considered = routed or [{"documentId": d} for d in (doc_ids or [])]
        usage = Usage(provider=self.llm.provider, model=self.llm.model, input_tokens=None, output_tokens=None, llm_calls=0)
        if not res.hits:
            return self._abstain(req, "no_evidence", "retrieval returned no evidence", considered, retrieved, usage,
                                 timings, warnings, t0)
        items = []
        for i, h in enumerate(res.hits, start=1):
            row = rows[h.chunk_id]
            text = row["content"]
            if row["kind"] == "figure" and req.include_figures and self.visual_lookup:
                vis = self.visual_lookup(row["document_id"], row["meta"].get("figureBlockId"))
                if vis:
                    text += "\n" + vis
            items.append(EvidenceItem(label=f"E{i}", row=row, text=text))
        by_label = {it.label: it for it in items}
        user = (f"Question: {req.question}\n\nEvidence excerpts:\n\n{_render_evidence(items, self.s.qa_max_evidence_chars)}"
                "\nReturn the JSON object described by the schema.")
        tokens_in = tokens_out = 0
        report = None
        plan = None
        feedback = ""
        llm_ms = 0.0
        for attempt in range(2):  # initial answer + at most one repair round
            try:
                out = self.llm.generate_json(SYSTEM_PROMPT, [user + feedback], PLAN_SCHEMA, "grounded_answer")
            except LLMRefusal as exc:
                return self._abstain(req, "model_refused", str(exc), considered, retrieved, usage, timings, warnings, t0)
            except LLMError:
                raise
            usage.llm_calls += 1
            usage.model = out.model
            llm_ms += out.latency_ms
            tokens_in += out.input_tokens or 0
            tokens_out += out.output_tokens or 0
            warnings += out.notes
            plan = out.data
            if plan.get("status") == "insufficient_evidence":
                usage.input_tokens, usage.output_tokens = tokens_in, tokens_out
                usage.cost_usd = cost_usd(self.s, tokens_in, tokens_out)
                timings["llm_ms"] = round(llm_ms, 1)
                return self._abstain(req, "insufficient_evidence", plan.get("insufficiency_reason") or "model abstained",
                                     considered, retrieved, usage, timings, warnings, t0)
            report, built = self._validate(plan, by_label, req.question)
            if report.passed:
                report.repaired = attempt == 1
                break
            failed = [c for c in report.checks if not c["ok"]]
            feedback = ("\n\nYour previous answer failed these automatic checks; fix them or abstain:\n"
                        + "\n".join(f"- {c['check']}: {c['detail']}" for c in failed))
        usage.input_tokens, usage.output_tokens = tokens_in, tokens_out
        usage.cost_usd = cost_usd(self.s, tokens_in, tokens_out)
        timings["llm_ms"] = round(llm_ms, 1)
        if report is None or not report.passed:
            detail = "; ".join(f"{c['check']}: {c['detail']}" for c in (report.checks if report else []) if not c["ok"])
            resp = self._abstain(req, "validation_failed", detail or "invalid model output", considered, retrieved,
                                 usage, timings, warnings, t0)
            resp.validation = report
            return resp
        operands, calcs, citations, value = built
        answer = plan["answer"].strip()
        if value and value.value_kind == "visual_estimate":
            answer += " (Visual estimate read from a chart image; not a reported figure.)"
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return QAResponse(status="answered", question=req.question, answer=answer, value=value, operands=operands,
                          calculations=calcs, citations=citations, abstention=None, documents_considered=considered,
                          retrieved=retrieved, validation=report, usage=usage, timings_ms=timings, warnings=warnings)

    # ------------------------------------------------------------------ validation
    def _validate(self, plan: dict, by_label: dict[str, EvidenceItem], question: str):
        checks: list[dict] = []

        def check(name: str, ok: bool, detail: str = "") -> bool:
            checks.append({"check": name, "ok": ok, "detail": detail})
            return ok

        cites: dict[str, str | None] = {}
        for c in plan.get("citations", []):
            eid, quote = c.get("evidence_id"), (c.get("quote") or "").strip()
            if not check("citation_exists", eid in by_label, f"{eid} is not a provided evidence id"):
                continue
            if quote:
                check("citation_quote_verbatim", _norm(quote) in _norm(by_label[eid].text),
                      f"quote not found in {eid}: {quote[:80]!r}")
            cites[eid] = quote or None
        operands: dict[str, calc.Operand] = {}
        op_out: list[Operand] = []
        for o in plan.get("operands", []):
            eid, quote = o.get("evidence_id"), (o.get("quote") or "").strip()
            if not check("operand_evidence_exists", eid in by_label, f"operand {o.get('id')} cites unknown {eid}"):
                continue
            item = by_label[eid]
            if not check("operand_quote_verbatim", bool(quote) and _norm(quote) in _norm(item.text),
                         f"operand {o['id']} quote {quote!r} not found verbatim in {eid}"):
                continue
            nums = numbers_in(quote) if parse_number(quote) is None else [parse_number(quote)]
            if not check("operand_is_single_number", len(nums) == 1, f"operand {o['id']} quote {quote!r} must contain exactly one number"):
                continue
            vk = o.get("value_kind", "reported")
            if vk == "visual_estimate":
                check("visual_estimate_from_figure", item.row["kind"] == "figure" and "VISUAL ESTIMATE" in item.text,
                      f"operand {o['id']} marked visual_estimate but {eid} has no chart reading")
            elif item.row["kind"] == "figure" and _norm(quote) not in _norm(item.row["content"]):
                check("chart_value_marked_estimate", False, f"operand {o['id']} comes from a chart reading; mark it visual_estimate")
            if item.row["kind"] == "table" and o.get("label"):
                line = next((ln for ln in item.text.splitlines() if _norm(quote) in _norm(ln)), "")
                lt = set(re.findall(r"[a-z]{3,}", o["label"].lower()))
                overlap = len(lt & set(re.findall(r"[a-z]{3,}", line.lower()))) / max(1, len(lt))
                checks.append({"check": "operand_label_on_same_row", "ok": True,
                               "detail": f"{o['id']}: label/row token overlap {overlap:.2f}" + (" (low)" if overlap < 0.3 else "")})
            operands[o["id"]] = calc.Operand(id=o["id"], value=nums[0], scale=o.get("scale", "units"), value_kind=vk)
            op_out.append(Operand(id=o["id"], value=str(nums[0]), quote=quote, label=o.get("label", ""), evidence_id=eid,
                                  scale=o.get("scale", "units"), value_kind=vk, evidence_kind=item.row["kind"]))
            cites.setdefault(eid, quote)
        steps = [calc.Step(id=c["id"], op=c["op"], args=list(c.get("args", [])), periods=c.get("periods"),
                           description=c.get("description", "")) for c in plan.get("calculations", [])]
        execution = None
        try:
            execution = calc.execute(list(operands.values()), steps)
            check("calculations_valid", True, f"{len(steps)} step(s) executed")
        except calc.CalculationError as exc:
            check("calculations_valid", False, str(exc))
        check("has_citations", bool(cites), "an answer must cite at least one evidence item")
        value = None
        final = plan.get("final") or {}
        ref = final.get("ref")
        if ref and execution is not None:
            if ref in operands:
                o = operands[ref]
                value = AnswerValue(value=str(o.value), unit=final.get("unit"), source=ref,
                                    value_kind="visual_estimate" if o.value_kind == "visual_estimate" else "reported")
            elif ref in execution.results:
                r = execution.results[ref]
                value = AnswerValue(value=str(r.value.normalize() if r.value == r.value.to_integral() else round(r.value, 6)),
                                    unit=final.get("unit"), source=ref,
                                    value_kind="visual_estimate" if r.value_kind == "visual_estimate" else "calculated")
            else:
                check("final_ref_exists", False, f"final.ref {ref!r} is neither an operand nor a step")
        # every number in the answer text must be grounded
        if execution is not None:
            allowed: set[Decimal] = set()
            for eid in cites:
                allowed |= set(numbers_in(by_label[eid].text))
            allowed |= set(numbers_in(question))
            for o in operands.values():
                allowed |= calc.rounding_variants(o.value) | {abs(o.value)}
            for r in execution.results.values():
                for v in (r.value, abs(r.value), r.value * 100, abs(r.value) * 100):
                    allowed |= calc.rounding_variants(v)
                    if r.scale in ("millions", "thousands", "billions"):
                        base = v * calc.SCALES[r.scale]
                        for sc in ("thousands", "millions", "billions"):
                            allowed |= calc.rounding_variants(base / calc.SCALES[sc])
            ungrounded = []
            for n in numbers_in(plan.get("answer", "")):
                if n in allowed or abs(n) in allowed or any(abs(n - a) < Decimal("0.0000001") for a in allowed):
                    continue
                ungrounded.append(str(n))
            check("answer_numbers_grounded", not ungrounded,
                  f"numbers not found in cited evidence or calculations: {', '.join(ungrounded[:6])}" if ungrounded else "")
        passed = all(c["ok"] for c in checks)
        citations = [Citation(evidence_id=eid, quote=q, evidence_kind=by_label[eid].row["kind"],
                              chunk=chunk_ref(by_label[eid].row, self.titles)) for eid, q in cites.items()]
        calcs = []
        if execution is not None:
            for r in execution.results.values():
                calcs.append(Calculation(id=r.id, op=r.op, description=r.description,
                                         inputs=[{"ref": a, "value": str(v)} for a, v in r.inputs],
                                         result=str(round(r.value, 6)), scale=r.scale, value_kind=r.value_kind))
        return ValidationReport(passed=passed, checks=checks), (op_out, calcs, citations, value)

    def _abstain(self, req, reason, detail, considered, retrieved, usage, timings, warnings, t0) -> QAResponse:
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return QAResponse(status="abstained", question=req.question, answer=None, value=None, operands=[],
                          calculations=[], citations=[], abstention=Abstention(reason=reason, detail=detail),
                          documents_considered=considered, retrieved=retrieved, validation=None, usage=usage,
                          timings_ms=timings, warnings=warnings)


def plan_schema_json() -> str:
    return json.dumps(PLAN_SCHEMA, indent=2)

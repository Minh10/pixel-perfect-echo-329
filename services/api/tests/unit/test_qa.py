"""Stage 3: deterministic calculator, grounding validation, abstention, providers (no network)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.financial.pipeline import normalize_document
from app.indexing.chunker import CHUNKER_VERSION, DocMeta, chunk_layout
from app.indexing.store import ChunkStore
from app.processing.assemble import assemble
from app.processing.pymupdf_parser import inspect_pages, parse_with_pymupdf
from app.qa import calculator as calc
from app.qa.evidence import route_documents
from app.qa.llm import AnthropicProvider, LLMRefusal, LLMUnavailable, OpenAICompatibleProvider, cost_usd
from app.qa.pipeline import PLAN_SCHEMA, QAPipeline, operand_association_checks
from app.qa.schemas import QARequest
from app.retrieval.search import Retriever
from app.storage.db import Repository
from tests.helpers import ScriptedLLM

FIX = Path(__file__).parents[1] / "fixtures" / "annual_report_excerpt.pdf"


# --------------------------------------------------------------------------- calculator
def O(i: str, v: str, scale: str = "millions", kind: str = "reported") -> calc.Operand:  # noqa: N802
    return calc.Operand(i, Decimal(v), scale, kind)


def test_calculator_operations_exact() -> None:
    ex = calc.execute([O("a", "591"), O("b", "703"), O("r", "4812")], [
        calc.Step("g", "percent_change", ["a", "b"]),
        calc.Step("m", "percent_of", ["b", "r"]),
        calc.Step("d", "subtract", ["b", "a"]),
        calc.Step("s", "sum", ["a", "b", "d"]),
    ])
    assert ex.results["d"].value == Decimal("112")
    assert round(ex.results["g"].value, 4) == Decimal("18.9509")
    assert round(ex.results["m"].value, 2) == Decimal("14.61") and ex.results["m"].scale == "percent"
    assert ex.results["s"].value == Decimal("1406")


@pytest.mark.parametrize(("steps", "msg"), [
    ([calc.Step("x", "divide", ["a", "z"])], "undefined"),
    ([calc.Step("x", "exec", ["a"])], "not allowed"),
    ([calc.Step("x", "add", ["a", "y"]), calc.Step("y", "add", ["a", "a"])], "unknown reference"),  # forward ref
    ([calc.Step("x", "subtract", ["a", "a", "a"])], "arguments"),
    ([calc.Step("x", "add", ["a", "p"])], "incompatible"),
])
def test_calculator_rejects_invalid_plans(steps, msg) -> None:
    with pytest.raises(calc.CalculationError, match=msg):
        calc.execute([O("a", "10"), O("z", "0"), O("p", "5", "percent")], steps)


def test_calculator_converts_mixed_scales_and_propagates_visual_kind() -> None:
    ex = calc.execute([O("a", "1.5", "billions"), O("b", "250", "millions", "visual_estimate")],
                      [calc.Step("t", "add", ["a", "b"])])
    assert ex.results["t"].value == Decimal("1750000000") and ex.results["t"].scale == "units"
    assert ex.results["t"].value_kind == "visual_estimate"


def test_cagr() -> None:
    ex = calc.execute([O("a", "100"), O("b", "121")], [calc.Step("c", "cagr", ["a", "b"], periods=2)])
    assert abs(ex.results["c"].value - Decimal(10)) < Decimal("1e-9")


# --------------------------------------------------------------------------- pipeline fixtures
@pytest.fixture
def qa_env(tmp_path: Path):
    s = Settings(data_dir=tmp_path, embedder="none", qa_method="bm25")
    repo = Repository(s.db_path)
    repo.create_document_with_job({"id": "doc_syn", "title": "Synthetic AR", "issuer": "Fictional Example Holdings plc",
                                   "period": "2025", "doc_type": "Annual Report", "filename": "f.pdf", "size_bytes": 1,
                                   "sha256": "0" * 64, "page_count": 3}, "pymupdf", 1)
    parse = assemble(parse_with_pymupdf(FIX), inspect_pages(FIX), document_id="doc_syn", job_id="job_x", sha256="0" * 64)
    meta = DocMeta("doc_syn", "Synthetic AR", "Fictional Example Holdings plc", "2025", "Annual Report", "0" * 64,
                   "pymupdf", "2.0", "job_x")
    store = ChunkStore(s.db_path)
    norms = normalize_document("doc_syn", "Fictional Example Holdings plc", "0" * 64, parse, FIX)
    store.replace_document_facts("doc_syn", [f for n in norms.values() for f in n.facts])
    store.replace_document_chunks("doc_syn", "layout", CHUNKER_VERSION, chunk_layout(parse, meta, norms),
                                  {"source_sha256": "0" * 64, "parser": "pymupdf", "parser_version": "2.0",
                                   "parse_job_id": "job_x"})
    docs = [dict(repo.get_document("doc_syn"), status="ready")]
    return s, store, docs


Q = "By how much did Fictional Example Holdings' operating profit grow from 2024 to 2025?"


def good_plan(e: str) -> dict:
    return {"status": "answered", "insufficiency_reason": None,
            "answer": "Operating profit rose from 591 to 703 (GBP m), an increase of 18.95%.",
            "citations": [{"evidence_id": e, "quote": "Operating profit: 2025 = 703; 2024 = 591"}],
            "operands": [{"id": "op24", "evidence_id": e, "quote": "591", "row_label": "Operating profit",
                          "period": "2024", "metric": "operating profit", "currency": None,
                          "scale": "millions", "value_kind": "reported"},
                         {"id": "op25", "evidence_id": e, "quote": "703", "row_label": "Operating profit",
                          "period": "2025", "metric": "operating profit", "currency": None,
                          "scale": "millions", "value_kind": "reported"}],
            "calculations": [{"id": "g", "op": "percent_change", "args": ["op24", "op25"], "periods": None,
                              "description": "growth 2024->2025"}],
            "final": {"ref": "g", "unit": "percent", "metric": "operating profit growth"}}


class LabelAware(ScriptedLLM):
    """Builds its plan after seeing the prompt, so evidence ids match the real retrieval order."""

    def __init__(self, builders) -> None:
        super().__init__([])
        self.builders = list(builders)

    def generate_json(self, system, parts, schema, schema_name):
        import re

        from app.qa.llm import LLMResult

        prompt = "".join(p for p in parts if isinstance(p, str))
        self.prompts.append(prompt)
        e = re.search(r"\[(E\d+)\] TABLE", prompt).group(1)
        b = self.builders.pop(0)
        if isinstance(b, Exception):
            raise b
        return LLMResult(data=b(e), model=self.model, provider=self.provider, input_tokens=100, output_tokens=50,
                         latency_ms=1.0)


def run(qa_env, builders, visual=None, question=Q):
    s, store, docs = qa_env
    llm = LabelAware(builders)
    return QAPipeline(s, store, Retriever(s, store=store), llm, docs, visual_lookup=visual).answer(QARequest(question=question)), llm


def test_grounded_answer_with_deterministic_calculation(qa_env) -> None:
    r, llm = run(qa_env, [good_plan])
    assert r.status == "answered", r.validation
    assert r.value.value_kind == "calculated" and Decimal(r.value.value).quantize(Decimal("0.0001")) == Decimal("18.9509")
    assert [o.value for o in r.operands] == ["591", "703"] and r.operands[0].evidence_kind == "table"
    # operands are bound to stored FinancialFacts of the cited table (geometric column/period binding)
    assert all(o.binding == "fact" and o.fact_id for o in r.operands), r.operands
    assert [o.period for o in r.operands] == ["2024", "2025"]
    c = r.citations[0]
    assert c.chunk.pages == [2] and c.chunk.regions[0].block_id == "p2-b003"
    assert c.chunk.regions[0].workspace_evidence_id == "ev-p2-b003"
    assert r.usage.llm_calls == 1 and r.usage.cost_usd is None  # no prices configured -> no invented cost
    assert "TABLE" in llm.prompts[0] and "Units:" in llm.prompts[0]


def test_fabricated_number_triggers_repair_then_abstains(qa_env) -> None:
    def bad(e):
        p = good_plan(e)
        p["answer"] = "Operating profit grew 18.95% to 703, driven by 812 new contracts."
        return p

    r, llm = run(qa_env, [bad, bad])
    assert r.status == "abstained" and r.abstention.reason == "validation_failed"
    assert "812" in r.abstention.detail and r.answer is None and r.value is None
    assert len(llm.prompts) == 2 and "failed these automatic checks" in llm.prompts[1]


def test_repair_round_can_fix_answer(qa_env) -> None:
    def bad(e):
        p = good_plan(e)
        p["operands"][1]["quote"] = "7,030"  # not in the evidence
        return p

    r, _ = run(qa_env, [bad, good_plan])
    assert r.status == "answered" and r.validation.repaired is True


@pytest.mark.parametrize("mutate", [
    lambda p: p["operands"][0].__setitem__("evidence_id", "E99"),
    lambda p: p["citations"][0].__setitem__("quote", "Operating profit was a record 9,999"),
    lambda p: p["calculations"][0].__setitem__("op", "eval"),
    lambda p: p["final"].__setitem__("ref", "nope"),
    lambda p: p.__setitem__("citations", []) or p.__setitem__("operands", []) or p.__setitem__("calculations", [])
    or p["final"].__setitem__("ref", None),
])
def test_invalid_plans_are_rejected(qa_env, mutate) -> None:
    def b(e):
        p = good_plan(e)
        mutate(p)
        return p

    r, _ = run(qa_env, [b, b])
    assert r.status == "abstained" and r.abstention.reason == "validation_failed"


def _relabel(qa_env, mutate, question=Q):
    def b(e):
        p = good_plan(e)
        mutate(p)
        return p

    return run(qa_env, [b, b], question=question)


def test_pipeline_rejects_wrong_metric_year_unit_scope_and_unsupported_math(qa_env) -> None:
    # M3.5: check names follow the evidence-binding validator (operand_cell_located = value not in the quoted row)
    r, _ = _relabel(qa_env, lambda p: p["operands"][1].update(row_label="Revenue", metric="revenue"))
    assert r.status == "abstained" and "operand_cell_located" in r.abstention.detail
    r, _ = _relabel(qa_env, lambda p: p["operands"][1].__setitem__("period", "2024"))
    assert r.status == "abstained" and "operand_period_matches" in r.abstention.detail
    r, _ = _relabel(qa_env, lambda p: [o.__setitem__("scale", "thousands") for o in p["operands"]])
    assert r.status == "abstained" and "operand_units_match" in r.abstention.detail
    r, _ = _relabel(qa_env, lambda p: p["operands"][1].__setitem__("metric", "segment operating profit"))
    assert r.status == "abstained" and "operand_scope_matches" in r.abstention.detail
    r, _ = _relabel(qa_env, lambda p: p["calculations"][0].__setitem__("op", "npv"))
    assert r.status == "abstained" and "calculations_valid" in r.abstention.detail


TABLE = """[Table] Table 1: Summary income statement (GBP m), synthetic data
Units: GBP millions.
Columns: 2025 | 2024 | Change
Revenue: 2025 = 4,812; 2024 = 4,281; Change = +12.4%
Operating profit: 2025 = 703; 2024 = 591; Change = +18.9%
"""
PROSE = ("Group revenue increased 12.4% to GBP 4,812 million in 2025, while operating profit rose to "
         "GBP 703 million.")
Q_OP = "What was Fictional Example Holdings' operating profit in 2025?"


def _assoc(**kwargs):
    base = dict(kind="table", label="Operating profit 2025", quote="703", scale="millions", text=TABLE, question=Q_OP)
    base.update(kwargs)
    return operand_association_checks(**base)


def _failed(checks, name):
    return [c for c in checks if c["check"] == name and not c["ok"]]


def test_correct_metric_and_year_are_accepted() -> None:
    checks = _assoc()
    assert all(c["ok"] for c in checks), checks


def test_correct_number_wrong_metric_is_rejected() -> None:
    checks = _assoc(label="Revenue 2025", question="What was revenue in 2025?")
    assert _failed(checks, "operand_cell_located")


def test_correct_metric_wrong_fiscal_year_is_rejected() -> None:
    assert _failed(_assoc(label="Operating profit 2024"), "operand_period_matches")
    assert _failed(_assoc(question="What was operating profit in 2030?"), "operand_period_in_question")


def test_different_units_or_currencies_are_rejected() -> None:
    assert _failed(_assoc(scale="thousands"), "operand_units_match")
    assert _failed(_assoc(label="Operating profit 2025 USD"), "operand_currency_matches")
    assert _failed(_assoc(question="What was operating profit in 2025 in USD?"), "question_currency_supported")


def test_different_reporting_scope_is_rejected() -> None:
    assert _failed(_assoc(label="Segment operating profit 2025"), "operand_scope_matches")
    grouped = _assoc(label="Group operating profit 2025", text="[Table] Group income statement\n" + TABLE)
    assert all(c["ok"] for c in grouped), grouped


def test_wrong_row_or_column_and_ambiguous_values_are_rejected() -> None:
    assert _failed(_assoc(label="Revenue 2025", quote="703"), "operand_cell_located")
    # M3.5: the quoted row label now disambiguates a value that also appears in another row ...
    other_row = TABLE + "Other income: 2025 = 703; 2024 = 10\n"
    assert all(c["ok"] for c in _assoc(text=other_row))
    # ... and a value/row pair that matches more than one cell is ambiguous -> rejected
    duplicated = TABLE + "Operating profit: 2025 = 703; 2024 = 12\n"
    checks = _assoc(text=duplicated)
    assert _failed(checks, "operand_cell_located")
    assert "more than one" in checks[0]["detail"]


def test_missing_evidence_is_not_verified() -> None:
    checks = _assoc(quote="2025")
    assert _failed(checks, "operand_cell_located")
    prose_miss = operand_association_checks(kind="text", label="Revenue 2025", quote="703", scale="millions",
                                            text=PROSE, question="What was revenue in 2025?")
    assert _failed(prose_miss, "operand_row_label_quoted")
    prose_ok = operand_association_checks(kind="text", label="Operating profit 2025", quote="703", scale="millions",
                                          text=PROSE, question=Q_OP)
    assert all(c["ok"] for c in prose_ok), prose_ok


def test_headers_away_from_the_value_still_verify() -> None:
    text = "\n".join([
        "[Table] Summary income statement",
        "Units: GBP millions.",
        "Columns: 2025 | 2024",
        "[Operating profit]",
        "703; 591",
    ])
    checks = _assoc(text=text)
    assert all(c["ok"] for c in checks), checks
    # M3.5 (AUD-02): a year that appears only in the table TITLE does not identify the value's column, so the
    # PR #2 expectation that this verifies is reversed -- the period is unverifiable and the operand is rejected.
    single = "\n".join(["[Table] Operating profit 2025", "Units: GBP millions.", "[Operating profit]", "703"])
    checks = _assoc(text=single)
    assert _failed(checks, "operand_period_matches"), checks


def test_model_abstention_and_refusal(qa_env) -> None:
    def abstain(e):
        return {"status": "insufficient_evidence", "answer": "", "insufficiency_reason": "No 2026 data in evidence.",
                "citations": [], "operands": [], "calculations": [], "final": {"ref": None, "unit": None}}

    r, _ = run(qa_env, [abstain])
    assert r.status == "abstained" and r.abstention.reason == "insufficient_evidence" and r.answer is None
    r, _ = run(qa_env, [LLMRefusal("declined")])
    assert r.abstention.reason == "model_refused"


def test_visual_estimates_are_labelled_and_enforced(qa_env) -> None:
    vis = lambda d, b: "VISUAL ESTIMATE (read from chart image, approximate): South ≈ 158 (GBP m)"  # noqa: E731
    q = "Approximately how much revenue did the South segment have in Figure 1 of Fictional Example Holdings?"

    def fig_plan(kind):
        def b(_e):
            import re

            e = re.search(r"\[(E\d+)\] FIGURE", llm_holder[0].prompts[-1]).group(1)
            return {"status": "answered", "insufficiency_reason": None, "answer": "Approximately 158 GBP m.",
                    "citations": [{"evidence_id": e, "quote": "South ≈ 158"}],
                    "operands": [{"id": "s", "evidence_id": e, "quote": "158", "label": "South revenue (chart)",
                                  "scale": "millions", "value_kind": kind}],
                    "calculations": [], "final": {"ref": "s", "unit": "GBP millions"}}
        return b

    s, store, docs = qa_env
    for kind, expected in (("visual_estimate", "answered"), ("reported", "abstained")):
        llm = LabelAware([fig_plan(kind), fig_plan(kind)])
        llm_holder = [llm]
        r = QAPipeline(s, store, Retriever(s, store=store), llm, docs, visual_lookup=vis).answer(QARequest(question=q))
        assert r.status == expected
        if expected == "answered":
            assert r.value.value_kind == "visual_estimate" and "not a reported figure" in r.answer
            assert r.citations[0].evidence_kind == "figure"


def test_no_evidence_abstains_without_calling_llm(qa_env) -> None:
    s, store, docs = qa_env
    llm = ScriptedLLM([])
    r = QAPipeline(s, store, Retriever(s, store=store), llm, docs).answer(QARequest(question="zzzz qqqq xxxx"))
    assert r.status == "abstained" and r.abstention.reason == "no_evidence" and llm.prompts == []


def test_document_router() -> None:
    docs = [{"id": "d1", "issuer": "3M", "period": "2018", "title": "", "status": "ready"},
            {"id": "d2", "issuer": "3M", "period": "2022", "title": "", "status": "ready"},
            {"id": "d3", "issuer": "American Express", "period": "2022", "title": "", "status": "ready"},
            {"id": "d4", "issuer": "AMD", "period": "2022", "title": "", "status": "ready"}]
    assert [d["documentId"] for d in route_documents("What is the FY2018 capex for 3M?", docs)] == ["d1", "d2"]
    assert [d["documentId"] for d in route_documents("How did American Express's tax rate change?", docs)] == ["d3"]
    assert route_documents("Does AMD have a healthy quick ratio?", docs)[0]["documentId"] == "d4"
    assert route_documents("What is the largest company?", docs) == []
    assert route_documents("Is Amazon's demand cyclical?", docs) == []  # 'amd' must match a whole word


# --------------------------------------------------------------------------- providers (no network)
def test_plan_schema_is_strict() -> None:
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False and set(node["required"]) == set(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(PLAN_SCHEMA)


def test_anthropic_provider_requires_explicit_key_and_ignores_ambient_base_url(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://ambient.invalid")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-should-not-be-used")
    monkeypatch.delenv("FINAUDIT_LLM_API_KEY", raising=False)
    s = Settings(llm_provider="anthropic", llm_model="claude-opus-5-5")
    with pytest.raises(LLMUnavailable, match="no API key"):
        AnthropicProvider(s)
    monkeypatch.setenv("FINAUDIT_LLM_API_KEY", "test-key")
    p = AnthropicProvider(s)
    assert str(p._client.base_url).startswith("https://api.anthropic.com") and p.fallback is True
    with pytest.raises(LLMUnavailable, match="MODEL"):
        AnthropicProvider(Settings(llm_provider="anthropic", llm_model=None))


def test_openai_compatible_provider_parses_structured_output() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(req.content)
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(200, json={"model": "local-model", "choices": [{"finish_reason": "stop", "message": {
            "content": '{"ok": true}'}}], "usage": {"prompt_tokens": 12, "completion_tokens": 3}})

    p = OpenAICompatibleProvider(Settings(llm_provider="openai", llm_model="m", llm_base_url="http://x/v1"))
    p._client = httpx.Client(base_url="http://x/v1", transport=httpx.MockTransport(handler))
    r = p.generate_json("sys", ["hi"], {"type": "object"}, "t")
    assert r.data == {"ok": True} and r.input_tokens == 12 and r.output_tokens == 3


def test_cost_only_from_configured_prices() -> None:
    assert cost_usd(Settings(), 1000, 1000) is None
    assert cost_usd(Settings(llm_price_input_per_mtok=4.0, llm_price_output_per_mtok=20.0), 1_000_000, 100_000) == 6.0

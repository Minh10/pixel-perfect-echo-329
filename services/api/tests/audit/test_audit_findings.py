"""Reproductions of correctness defects found in the independent audit (AI_VALIDATION_REPORT.md).

Milestone 3.5: a marker is removed only once its test genuinely passes (B1, B2 fixed by app/financial/numbers.py
and app/qa/grounding.py).

Each test asserts the CORRECT behaviour and is marked xfail(strict=True): it documents a confirmed bug,
keeps CI green, and turns red (XPASS) as soon as the bug is fixed, so the marker must then be removed.
Chunk texts are copied verbatim from the real filings' layout chunks (see eval/audit/validation_audit.py).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.evaluation.metrics import numbers_in, parse_number
from app.qa.pipeline import operand_association_checks

AMD_BALANCE_SHEET = """[Table] December 31, 2022 December 25,
[ASSETS]
[Current assets:]
Cash and cash equivalents: $4,835; $2,535
Short-term investments: 1,020; 1,073
Total current assets: 15,019; 8,583"""

PEPSICO_RESTRUCTURING = """[Table] Table of Contents
Columns: 2022 | 2021 | 2020 | Plan to Date through 12/31/2022
FLNA: 2022 = $46; 2021 = $28; 2020 = $83; Plan to Date through 12/31/2022 = $210
Europe: 2022 = 109; 2021 = 81; 2020 = 48; Plan to Date through 12/31/2022 = 343"""

THREE_M_CASH_FLOW = """[Table] Table of Contents 3M Company and Subsidiaries Consolidated Statement of Cash Flow s Years ended December 31
Units: (Millions)
Columns: 2018 | 2017 | 2016
[Cash Flows from Investing Activities]
Purchases of property, plant and equipment (PP&E): 2018 = (1,577); 2017 = (1,373); 2016 = (1,420)"""


def _ok(checks: list[dict], name: str) -> bool:
    return next(c["ok"] for c in checks if c["check"] == name)


# --------------------------------------------------------------------------- AUDIT-B1 (number parsing)
@pytest.mark.parametrize(("text", "value"), [("(0.6)%", "-0.6"), ("(5.3)%", "-5.3"), ("$(3,547)", "-3547")])
def test_b1_parse_negative_percent_and_dollar_prefixed_parentheses(text: str, value: str) -> None:
    assert parse_number(text) == Decimal(value)


def test_b1_numbers_in_keeps_negative_percentages() -> None:
    assert numbers_in("Operating margins: (5.3)%; (4.7)%") == [Decimal("-5.3"), Decimal("-4.7")]


# --------------------------------------------------------------------------- AUDIT-B2 (grounding bypass)
def test_b2_fabricated_negative_percentage_is_not_grounded(qa_env) -> None:  # noqa: F811
    import re

    from app.qa.pipeline import QAPipeline
    from app.qa.schemas import QARequest
    from app.retrieval.search import Retriever
    from tests.helpers import ScriptedLLM

    class Planner(ScriptedLLM):
        def generate_json(self, system, parts, schema, schema_name):
            e = re.search(r"\[(E\d+)\] TABLE", parts[0]).group(1)
            self.responses = [{
                "status": "answered", "insufficiency_reason": None,
                "answer": "Operating profit was 703 (GBP m) in 2025; the effective tax rate was (9.9)%.",  # 9.9 invented
                "citations": [{"evidence_id": e, "quote": "Operating profit: 2025 = 703"}],
                "operands": [{"id": "a", "evidence_id": e, "quote": "703", "label": "Operating profit 2025",
                              "scale": "millions", "value_kind": "reported"}],
                "calculations": [], "final": {"ref": "a", "unit": "GBP millions"}}] * 2
            return super().generate_json(system, parts, schema, schema_name)

    s, store, docs = qa_env
    r = QAPipeline(s, store, Retriever(s, store=store), Planner([]), docs).answer(
        QARequest(question="What was Fictional Example Holdings' operating profit in 2025?"))
    assert r.status == "abstained", "an invented (9.9)% must fail answer_numbers_grounded"


# --------------------------------------------------------------------------- AUDIT-B3 (period false accept)
@pytest.mark.xfail(strict=True, reason="AUDIT-B3: unlabelled period columns let the 2021 value pass as 2022")
def test_b3_wrong_period_rejected_when_columns_are_unlabelled() -> None:
    checks = operand_association_checks(kind="table", label="Cash and cash equivalents 2022", quote="$2,535",
                                        scale="units", text=AMD_BALANCE_SHEET,
                                        question="What was AMD's cash and cash equivalents at the end of 2022?")
    assert not _ok(checks, "operand_period_matches")


@pytest.mark.xfail(strict=True, reason="AUDIT-B4: a cumulative 'Plan to Date through 12/31/2022' column is accepted as FY2022")
def test_b4_cumulative_column_is_not_a_fiscal_year() -> None:
    checks = operand_association_checks(kind="table", label="FLNA restructuring charges 2022", quote="$210",
                                        scale="units", text=PEPSICO_RESTRUCTURING,
                                        question="What were PepsiCo's FLNA restructuring charges in 2022?")
    assert not _ok(checks, "operand_period_matches")


# --------------------------------------------------------------------------- AUDIT-B5 (calculation false reject)
@pytest.mark.xfail(strict=True, reason="AUDIT-B5: every operand must name the question's metric, so derived metrics always fail")
def test_b5_operand_of_a_derived_metric_is_not_rejected() -> None:
    checks = operand_association_checks(
        kind="table", label="Purchases of property, plant and equipment (PP&E) 2018", quote="(1,577)", scale="millions",
        text=THREE_M_CASH_FLOW,
        question="What was 3M's free cash flow in 2018, operating cash flow minus purchases of property, plant and equipment?")
    assert all(c["ok"] for c in checks), [c for c in checks if not c["ok"]]


# --------------------------------------------------------------------------- AUDIT-B6 (chunker percent merge)
@pytest.mark.xfail(strict=True, reason="AUDIT-B6: a '%)' cell is not merged, producing '(7.0; %)'")
def test_b6_percent_closing_paren_cell_is_merged() -> None:
    from app.indexing.chunker import _row_line, normalize_table
    from app.schemas import BBox, NormalizedBBox, PageBlock, Provenance, TableCell, TableData

    cells = [TableCell(row=0, col=0, text="Core operating margins"), TableCell(row=0, col=1, text="(7.0"),
             TableCell(row=0, col=2, text="%)")]
    bb = BBox(l=0, t=0, r=1, b=1)
    nb = NormalizedBBox(x=0, y=0, width=0.1, height=0.1)
    prov = Provenance(document_id="d", source_sha256="0" * 64, page=1, bbox=bb, bbox_normalized=nb, page_width=10,
                      page_height=10, parser="pymupdf", parser_version="2", method="m", job_id="j")
    pb = PageBlock(id="b", kind="table", role="table", bbox=bb, bbox_normalized=nb, provenance=prov,
                   table=TableData(columns=[], rows=[], num_rows=1, num_cols=3, header_rows=0, cells=cells))
    nt = normalize_table(pb)
    line = _row_line(nt.rows[0][1], nt.rows[0][2], nt.columns)
    assert line == "Core operating margins: (7.0)%", line


from tests.unit.test_qa import qa_env  # noqa: E402,F401 - fixture reuse

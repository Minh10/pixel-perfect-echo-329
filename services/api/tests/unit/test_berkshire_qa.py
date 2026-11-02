"""Replay real public PDF evidence without network/model calls or live service mutation."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.qa.pipeline import EvidenceItem, QAPipeline

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "berkshire_q1_2025_qa.json").read_text())


def environment(metric, period, value):
    fact = next(f for f in FIXTURE["facts"] if f["rowLabel"].startswith(metric)
                and f["period"]["label"] == period and f["value"] == value)
    chunk = next(c for c in FIXTURE["chunks"] if any(r["blockId"] == fact["tableId"] for r in c["regions"]))
    facts = [f for f in FIXTURE["facts"] if f["tableId"] == fact["tableId"]]
    row = {
        "chunk_id": chunk["chunkId"], "chunk_set": chunk["chunkSet"], "kind": "table",
        "document_id": chunk["documentId"], "company": chunk["company"], "period": chunk["period"],
        "pages": chunk["pages"], "section_path": chunk["sectionPath"], "content": chunk["content"],
        "blocks": [{"page": r["page"], "blockId": r["blockId"], "bbox": r["bbox"],
                    "bboxNormalized": r["bboxNormalized"]} for r in chunk["regions"]],
        "meta": dict(chunk["table"], factIds=[f["factId"] for f in facts]),
        "source_sha256": chunk["sourceSha256"], "parser": chunk["parser"],
        "parser_version": chunk["parserVersion"], "index_version": chunk["indexVersion"],
    }
    store = SimpleNamespace(facts=lambda ids: {f["factId"]: f for f in facts if f["factId"] in ids})
    pipeline = QAPipeline(SimpleNamespace(qa_claim_support_min=0.5), store, None, None, [])
    quote = f"{fact['rowLabel']}: {period} = {fact['cellText']}"
    plan = {
        "status": "answered", "answer": f"{metric} for {period} was {fact['cellText']} million dollars.",
        "citations": [{"evidence_id": "E1", "quote": quote}],
        "operands": [{"id": "amount", "evidence_id": "E1", "quote": quote,
                      "row_label": fact["rowLabel"], "period": period, "metric": metric,
                      "currency": None, "scale": "millions", "value_kind": "reported"}],
        "calculations": [], "final": {"ref": "amount", "unit": "dollar millions", "metric": metric},
    }
    return pipeline, {"E1": EvidenceItem("E1", row, chunk["content"])}, plan, fact


@pytest.mark.parametrize(("metric", "period", "value", "page"), [
    ("Net earnings attributable to Berkshire shareholders", "First Quarter 2025", "4603", 1),
    ("Operating earnings", "First Quarter 2024", "11222", 1),
    ("BNSF", "First Quarter 2025", "1214", 2),
])
def test_real_pdf_numerical_answer_and_citation(metric, period, value, page):
    pipeline, items, plan, fact = environment(metric, period, value)
    report, (_, _, citations, answer_value) = pipeline._validate(plan, items, plan["answer"])
    assert report.passed, report.checks
    assert answer_value.value == value
    assert citations[0].chunk.pages == [page]
    assert citations[0].quote in citations[0].chunk.content
    assert citations[0].chunk.source_sha256 == fact["sourceSha256"]


@pytest.mark.parametrize("change", ["period", "scale", "citation", "amount"])
def test_real_pdf_wrong_period_units_quote_or_value_still_rejected(change):
    pipeline, items, plan, _ = environment("BNSF", "First Quarter 2025", "1214")
    plan = copy.deepcopy(plan)
    if change == "period":
        plan["operands"][0]["period"] = "First Quarter 2024"
    elif change == "scale":
        plan["operands"][0]["scale"] = "billions"
    elif change == "citation":
        plan["citations"][0]["quote"] = "BNSF had record profits of 9999"
    else:
        plan["operands"][0]["quote"] = "9999"
    report, _ = pipeline._validate(plan, items, "What were BNSF earnings for First Quarter 2025?")
    assert not report.passed
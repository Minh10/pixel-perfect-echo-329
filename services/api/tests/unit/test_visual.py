"""Stage 4: chart interpretation flow (scripted VLM test double) and table cross-checks."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from app.indexing.store import ChunkStore
from app.qa.llm import ImagePart
from app.qa.schemas import ChartPoint
from app.visual.charts import ChartStore, cross_check, evidence_text, interpret_chart, render_crop
from tests.unit.test_qa import qa_env  # noqa: F401 - fixture reuse

FIX = Path(__file__).parents[1] / "fixtures" / "annual_report_excerpt.pdf"


def P(label: str, value: str, period: str | None = "2025") -> ChartPoint:  # noqa: N802
    return ChartPoint(series=None, label=label, value=value, unit="GBP millions", period=period,
                      printed_on_chart=True)


def fact(label: str, value: str, year: int) -> dict:
    return {"rowLabel": label, "value": value, "valueStatus": "parsed", "isPercent": False,
            "scale": "millions", "currency": "GBP", "scope": "segment", "page": 2,
            "factId": f"{label}-{year}", "tableId": "p2-t1",
            "period": {"fiscalYear": year, "label": str(year)}}


FACTS = [fact("North", "2410", 2025), fact("North", "2300", 2024),
         fact("South", "1580", 2025), fact("South", "1500", 2024)]


def test_cross_check_uses_the_same_year_not_the_nearer_number() -> None:
    checks = {c.label: c for c in cross_check([P("North", "2400"), P("West", "21")], FACTS)}
    assert checks["North"].status == "consistent" and checks["North"].table_value == "2410"
    assert checks["North"].fact_id == "North-2025"
    south = [c for c in cross_check([P("South", "1200")], FACTS)][0]
    assert south.status == "conflict" and south.table_value == "1580"
    assert south.table_value != "1500"
    assert cross_check([P("West", "21")], FACTS)[0].status == "no_table_evidence"
    earlier = cross_check([P("North", "2290", "2024")], FACTS)[0]
    assert earlier.table_value == "2300" and earlier.status == "consistent"


def test_missing_period_or_unreadable_value_is_not_matched() -> None:
    assert cross_check([P("North", "2410", None)], FACTS)[0].status == "no_table_evidence"
    unread = cross_check([P("North", "cannot be read")], FACTS)[0]
    assert unread.status == "no_table_evidence" and unread.table_value is None


def test_crop_matches_figure_region() -> None:
    png = render_crop(FIX, 3, (72, 120, 472, 360), dpi=72)
    pix = pymupdf.Pixmap(png)
    assert abs(pix.width - 400) <= 2 and abs(pix.height - 240) <= 2


class ScriptedVLM:
    provider, model = "scripted", "scripted-vlm-test-double"

    def __init__(self) -> None:
        self.parts = None

    def generate_json(self, system, parts, schema, schema_name):
        from app.qa.llm import LLMResult

        self.parts = parts
        return LLMResult(data={"is_chart": True, "chart_type": "bar", "title": "Revenue by segment",
                               "summary": "North is about 999 which is not on the chart.",
                               "points": [{"series": None, "label": "North", "value": "240", "unit": "GBP millions",
                                           "period": "2025", "printed_on_chart": False}]},
                         model=self.model, provider=self.provider, input_tokens=1, output_tokens=1, latency_ms=1)


def test_interpret_chart_sends_crop_and_marks_estimates(qa_env) -> None:  # noqa: F811
    s, store, _ = qa_env
    vlm = ScriptedVLM()
    block = {"id": "p3-b002", "bbox": {"l": 72, "t": 120, "r": 472, "b": 360}}
    ci = interpret_chart("doc_syn", block, 3, FIX, vlm, ChunkStore(s.db_path), "Figure 1: Revenue by segment")
    assert isinstance(vlm.parts[0], ImagePart) and vlm.parts[0].png[:4] == b"\x89PNG"
    assert ci.points[0].value_kind == "visual_estimate" and ci.crop_url.endswith("/blocks/p3-b002/image")
    assert ci.table_checks[0].status == "no_table_evidence"  # the fixture has no segment table
    assert "999" not in (ci.summary or "") and "240" in (ci.summary or "")
    assert evidence_text(ci).startswith("VISUAL ESTIMATE")
    cs = ChartStore(s.db_path)
    cs.put(ci)
    assert cs.get("doc_syn", "p3-b002").points[0].label == "North"


def test_non_chart_image_extracts_no_values(qa_env) -> None:  # noqa: F811
    s, _, _ = qa_env

    class NotChart(ScriptedVLM):
        def generate_json(self, system, parts, schema, schema_name):
            from app.qa.llm import LLMResult

            return LLMResult(data={"is_chart": False, "chart_type": None, "title": None, "summary": "not a chart",
                                   "points": [{"label": "North", "value": "10", "printed_on_chart": True}]},
                             model=self.model, provider=self.provider, input_tokens=1, output_tokens=1, latency_ms=1)

    block = {"id": "p1-b001", "bbox": {"l": 72, "t": 120, "r": 472, "b": 360}}
    ci = interpret_chart("doc_syn", block, 1, FIX, NotChart(), ChunkStore(s.db_path), "Cover page")
    assert ci.points == [] and ci.table_checks == []
    assert ci.summary == "The image is not a data chart, so no values were extracted."

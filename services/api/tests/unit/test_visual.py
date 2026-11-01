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


def P(label: str, value: str) -> ChartPoint:  # noqa: N802
    return ChartPoint(series=None, label=label, value=value, unit="GBP m", printed_on_chart=False)


TABLES = [{"chunk_id": "t1", "content": "[Table] Segments\nColumns: 2025 | 2024\nNorth: 2025 = 2,410; 2024 = 2,300\n"
                                        "South: 2025 = 1,580; 2024 = 1,500"}]


def test_cross_check_statuses() -> None:
    checks = {c.label: c for c in cross_check([P("North", "2400"), P("South", "1200"), P("West", "21")], TABLES)}
    assert checks["North"].status == "consistent" and checks["North"].table_value == "2410"
    assert checks["South"].status == "conflict" and checks["South"].relative_difference > 0.1
    assert checks["West"].status == "no_table_evidence" and checks["West"].table_value is None


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
                               "points": [{"series": None, "label": "North", "value": "240", "unit": "GBP m",
                                           "printed_on_chart": False}]},
                         model=self.model, provider=self.provider, input_tokens=1, output_tokens=1, latency_ms=1)


def test_interpret_chart_sends_crop_and_marks_estimates(qa_env) -> None:  # noqa: F811
    s, store, _ = qa_env
    vlm = ScriptedVLM()
    block = {"id": "p3-b002", "bbox": {"l": 72, "t": 120, "r": 472, "b": 360}}
    ci = interpret_chart("doc_syn", block, 3, FIX, vlm, ChunkStore(s.db_path), "Figure 1: Revenue by segment")
    assert isinstance(vlm.parts[0], ImagePart) and vlm.parts[0].png[:4] == b"\x89PNG"
    assert ci.points[0].value_kind == "visual_estimate" and ci.crop_url.endswith("/blocks/p3-b002/image")
    assert ci.table_checks[0].status == "no_table_evidence"  # the fixture has no segment table
    assert evidence_text(ci).startswith("VISUAL ESTIMATE")
    cs = ChartStore(s.db_path)
    cs.put(ci)
    assert cs.get("doc_syn", "p3-b002").points[0].label == "North"

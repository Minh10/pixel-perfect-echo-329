"""PyMuPDF parser against fixtures whose ground-truth layout is known (see *.layout.json)."""

import json
from pathlib import Path

import pytest

from app.processing.assemble import assemble
from app.processing.pymupdf_parser import inspect_pages, parse_with_pymupdf

TOL = 2.0  # points


def _close(actual, expected, tol: float = TOL) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected, strict=True))


@pytest.fixture(scope="module")
def parsed():
    pdf = Path(__file__).parents[1] / "fixtures" / "annual_report_excerpt.pdf"
    return assemble(parse_with_pymupdf(pdf), inspect_pages(pdf), document_id="doc_f", job_id="job_f", sha256="0" * 64)


@pytest.fixture(scope="module")
def truth():
    return json.loads((Path(__file__).parents[1] / "fixtures" / "annual_report_excerpt.layout.json").read_text())


def test_page_metadata(parsed) -> None:
    assert [p.number for p in parsed.pages] == [1, 2, 3]
    p = parsed.pages[0]
    assert (p.width, p.height, p.rotation, p.has_text_layer) == (595.28, 841.89, 0, True)
    assert parsed.pages[2].image_count == 1


def test_table_bbox_matches_ground_truth_and_cells_verbatim(parsed, truth) -> None:
    table = next(b for b in parsed.pages[1].blocks if b.kind == "table")
    exp = truth["pages"]["2"]["table"]
    assert _close((table.bbox.l, table.bbox.t, table.bbox.r, table.bbox.b), exp["bbox"])
    assert table.provenance.page == 2 and table.provenance.method == "pymupdf:find_tables"
    grid = [[table.table.columns[i] for i in range(4)]] + [[r.label, *r.values] for r in table.table.rows]
    assert grid == exp["rows"]  # every cell exactly as drawn, e.g. "(3,018)", "+12.4%"
    assert all(c.bbox is not None for c in table.table.cells)


def test_figure_region_and_caption(parsed, truth) -> None:
    fig = next(b for b in parsed.pages[2].blocks if b.kind == "figure")
    assert _close((fig.bbox.l, fig.bbox.t, fig.bbox.r, fig.bbox.b), truth["pages"]["3"]["figure"]["bbox"])
    assert fig.figure.caption == "Figure 1: Revenue by segment, 2025 (synthetic)"
    assert fig.figure.classification == []  # no classifier in PyMuPDF path: nothing invented


def test_headings_sections_and_no_duplicate_table_text(parsed, truth) -> None:
    p2 = parsed.pages[1]
    heading = p2.blocks[0]
    assert heading.kind == "heading" and heading.text == "Financial review"
    assert p2.section == "Financial review" and parsed.pages[2].section == "Segment performance"
    # rows of the table must not be duplicated as paragraphs
    assert not any(b.kind == "paragraph" and b.text and b.text.startswith("Revenue 4,812") for b in p2.blocks)


def test_evidence_categories(parsed) -> None:
    cats = [(e.page, e.category) for e in parsed.evidence]
    assert cats == [(2, "disclosure"), (2, "table"), (3, "figure"), (3, "disclosure")]
    assert all(e.extracted is None and e.confidence is None for e in parsed.evidence)
    assert parsed.evidence[1].label == "Table 1: Summary income statement (GBP m), synthetic data"


def test_scanned_page_flagged_without_inventing_text() -> None:
    pdf = Path(__file__).parents[1] / "fixtures" / "scanned_statement.pdf"
    res = assemble(parse_with_pymupdf(pdf), inspect_pages(pdf), document_id="d", job_id="j", sha256="0" * 64)
    page = res.pages[0]
    assert page.has_text_layer is False and page.char_count == 0
    assert not any(b.text for b in page.blocks)
    assert any("no text layer" in w for w in res.warnings)

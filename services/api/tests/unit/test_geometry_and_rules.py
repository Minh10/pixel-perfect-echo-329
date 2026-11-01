import pytest

from app.processing.assemble import is_numeric_disclosure, table_to_schema
from app.processing.geometry import Box
from app.processing.model import RawCell, RawTable


def test_bottom_left_to_top_left() -> None:
    # PDF user space: y grows upward. A box 100pt from the bottom on an 800pt page.
    b = Box.from_bottom_left(l=50, t=200, r=150, b=100, page_height=800)
    assert (b.l, b.t, b.r, b.b) == (50, 600, 150, 700)


def test_normalized_and_clamped() -> None:
    n = Box(-10, 0, 300, 450).normalized(600, 900)
    assert n.x == 0 and n.y == 0
    assert n.width == pytest.approx(0.5)
    assert n.height == pytest.approx(0.5)


def test_fraction_inside() -> None:
    assert Box(0, 0, 10, 10).fraction_inside(Box(0, 0, 5, 10)) == pytest.approx(0.5)
    assert Box(0, 0, 10, 10).fraction_inside(Box(20, 20, 30, 30)) == 0


@pytest.mark.parametrize(
    "text",
    [
        "Revenue increased 12.4% to £4,812 million",
        "Net debt was USD 1.2 bn at year end",
        "Operating margin expanded by 80 basis points",
        "Impairment charge of (3,018) recognised",
        "A final dividend of 18.2p per share; payout 45 percent",
        "Capex of 366m in the year",
    ],
)
def test_numeric_disclosure_positive(text: str) -> None:
    assert is_numeric_disclosure(text)


@pytest.mark.parametrize(
    "text",
    [
        "Chair's statement",
        "For the year ended 31 December 2025",
        "Our strategy is built on three pillars.",
        "See note 12 on page 45",
    ],
)
def test_numeric_disclosure_negative(text: str) -> None:
    assert not is_numeric_disclosure(text)


def test_table_mapping_is_verbatim_and_detects_header_rows() -> None:
    cells = [
        RawCell(0, 0, 1, 1, "", column_header=True), RawCell(0, 1, 1, 2, "Group", column_header=True),
        RawCell(1, 0, 1, 1, "", column_header=True), RawCell(1, 1, 1, 1, "2025", column_header=True),
        RawCell(1, 2, 1, 1, "2024", column_header=True),
        RawCell(2, 0, 1, 1, "Revenue"), RawCell(2, 1, 1, 1, "4,812"), RawCell(2, 2, 1, 1, "(4,281)"),
    ]
    td = table_to_schema(RawTable(num_rows=3, num_cols=3, cells=cells), (1.0, 1.0))
    assert td.header_rows == 2
    assert td.columns == ["", "Group 2025", "2024"]
    assert [r.model_dump() for r in td.rows] == [{"label": "Revenue", "values": ["4,812", "(4,281)"]}]
    assert td.cells[1].col_span == 2


def test_table_without_header() -> None:
    td = table_to_schema(RawTable(2, 2, [RawCell(0, 0, 1, 1, "a"), RawCell(0, 1, 1, 1, "1"),
                                         RawCell(1, 0, 1, 1, "b"), RawCell(1, 1, 1, 1, "2")]), (1.0, 1.0))
    assert td.header_rows == 0 and td.columns == ["", ""] and len(td.rows) == 2

"""The two short-course annual reports are distinct synthetic fixtures, not copies of one filing."""

from pathlib import Path

import pymupdf

ROOT = Path(__file__).parents[1] / "fixtures"


def _text(name: str) -> str:
    doc = pymupdf.open(ROOT / name)
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()


def test_chart_check_fixture_prints_a_mismatch_and_says_synthetic() -> None:
    text = _text("synthetic_chart_check.pdf")
    assert "SYNTHETIC TEST FIXTURE" in text
    assert "not a real company" in text
    assert "150" in text and "240" in text and "158" in text and "21" in text


def test_course_reports_are_distinct_and_labelled_synthetic() -> None:
    earlier = _text("synthetic_ar_2024.pdf")
    later = _text("synthetic_ar_2025.pdf")
    assert earlier != later
    for text in (earlier, later):
        assert "SYNTHETIC TEST FIXTURE" in text
        assert "not a real company" in text
        assert "GBP millions" in text
    assert "Annual Report 2024" in earlier and "3,200" in earlier and "2,900" in earlier
    assert "410" in earlier and "360" in earlier
    assert "Annual Report 2025" in later and "3,550" in later and "3,200" in later
    assert "470" in later and "410" in later

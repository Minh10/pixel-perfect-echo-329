"""Offline replay of the real-filing grounding benchmark (eval/grounding) on frozen evidence.

tests/fixtures/grounding/cases_with_evidence.json holds, for every benchmark case, the exact indexed evidence
(layout-v3 chunk text + its FinancialFacts) extracted from the real filings by eval/grounding/run_benchmark.py,
so CI can re-run the validator without the PDFs.  The test pins the recorded outcome of every case (any change
in validator behaviour must be re-measured and re-recorded) and asserts that no case labelled REJECT is accepted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

API = Path(__file__).parents[2]
FIX = API / "tests" / "fixtures" / "grounding" / "cases_with_evidence.json"
sys.path.insert(0, str(API / "eval" / "grounding"))

from run_benchmark import bind  # noqa: E402

CASES = json.loads(FIX.read_text()) if FIX.exists() else []


def _accepted(item: dict) -> bool:
    return any(all(c["ok"] for c in bind(item["case"], ev)) for ev in item["evidence"])


def test_fixture_covers_both_splits_and_six_filings() -> None:
    assert len(CASES) >= 60
    splits = {c["case"]["split"] for c in CASES}
    assert splits == {"dev", "heldout", "heldout2", "heldout3", "heldout4"}
    real = {c["case"]["doc"] for c in CASES if "synthetic" not in c["case"]["doc"]}
    assert len(real) >= 6


@pytest.mark.parametrize("item", CASES, ids=[c["case"]["id"] for c in CASES])
def test_recorded_outcome_is_reproduced(item: dict) -> None:
    assert _accepted(item) == item["m35_accepted"]


def test_false_accepts_are_only_the_recorded_ones() -> None:
    """Pins the observed false accepts (see audit/milestone-3.5/grounding_benchmark); a new one fails CI."""
    fa = sorted(c["case"]["id"] for c in CASES if c["case"]["expect"] == "reject" and _accepted(c))
    recorded = sorted(c["case"]["id"] for c in CASES if c["case"]["expect"] == "reject" and c["m35_accepted"])
    assert fa == recorded

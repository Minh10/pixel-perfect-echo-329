"""Evaluation metrics and QA scoring (Stage 6)."""

import math
from decimal import Decimal

import pytest

from app.evaluation import metrics as M

D = "doc"


def R(*pages):  # noqa: N802 - ranked list of chunk page-sets
    return [{(D, p)} for p in pages]


def test_recall_hit_mrr_ndcg_page_level_dedup() -> None:
    gold = {(D, 5), (D, 7)}
    ranked = R(1, 5, 5, 7, 9)  # second chunk on p5 must not earn a second gain
    assert M.recall_at_k(ranked, gold, 1) == 0
    assert M.recall_at_k(ranked, gold, 3) == 0.5
    assert M.recall_at_k(ranked, gold, 5) == 1
    assert M.hit_at_k(ranked, gold, 2) == 1 and M.mrr(ranked, gold) == 0.5
    dcg = 1 / math.log2(3) + 1 / math.log2(5)
    idcg = 1 + 1 / math.log2(3)
    assert M.ndcg_at_k(ranked, gold, 10) == pytest.approx(dcg / idcg)
    assert M.mrr(R(1, 2), gold) == 0 and M.ndcg_at_k(R(5, 7), gold, 10) == pytest.approx(1)


@pytest.mark.parametrize(("s", "v"), [("$1577.00", "1577.00"), ("(370)", "-370"), ("16.5%", "16.5"), ("-0.02", "-0.02"),
                                      ("1,488", "1488"), ("+12.4%", "12.4"), ("abc", None)])
def test_parse_number(s, v) -> None:
    assert M.parse_number(s) == (Decimal(v) if v else None)


def test_numeric_match_and_token_f1() -> None:
    assert M.numeric_match(Decimal("1577"), Decimal("1577.00"))
    assert M.numeric_match(Decimal("16.48"), Decimal("16.5"))  # within 1% rounding tolerance
    assert not M.numeric_match(Decimal("9.068"), Decimal("9068"))
    assert M.token_f1("Operating activities for both", "operating activities for both companies") == pytest.approx(8 / 9)


def test_citation_and_abstention_scores() -> None:
    assert M.citation_pr({(D, 1), (D, 2)}, {(D, 2)}) == (0.5, 1.0)
    p, r = M.citation_pr(set(), {(D, 2)})
    assert math.isnan(p) and r == 0
    a = M.abstention_scores([(True, True), (True, False), (False, True), (False, False)])
    assert a["precision"] == 0.5 and a["recall"] == 0.5 and a["false_abstain_rate"] == 0.5


def test_paired_test_detects_consistent_improvement() -> None:
    a = [0.0] * 20 + [1.0] * 10
    b = [1.0] * 30
    res = M.paired_test(a, b, n=2000)
    assert res["diff"] == pytest.approx(20 / 30) and res["p"] < 0.01 and res["ci_low"] > 0
    same = M.paired_test(a, a, n=500)
    assert same["diff"] == 0 and same["p"] == 1.0


def test_qa_scoring_rules() -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[2] / "eval"))
    from run_qa_eval import score_item

    item = {"id": "x", "category": "numerical", "gold_value": "1577.00", "answer": "$1577.00", "gold_pages": [[D, 60]]}
    resp = {"status": "answered", "answer": "Capex was $1,577 million.", "value": {"value": "-1577"},
            "citations": [{"chunk": {"documentId": D, "pages": [60]}}]}
    s = score_item(item, resp)
    assert s["numeric_correct"] is True  # sign-insensitive via answer text "$1,577"
    assert s["citation_precision"] == 1 and s["citation_recall"] == 1
    un = {"id": "u", "category": "unanswerable", "gold_value": None, "answer": None, "gold_pages": []}
    s2 = score_item(un, {"status": "abstained", "citations": []})
    assert s2["should_abstain"] and s2["did_abstain"]


def test_holm_adjustment() -> None:
    adj = M.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == {"a": 0.03, "c": 0.06, "b": 0.06}  # monotone step-down

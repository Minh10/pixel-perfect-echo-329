"""AUD-01: strict financial number parsing and fail-closed token scanning."""

from decimal import Decimal

import pytest

from app.financial.numbers import parse_amount, parse_number, scan_numeric_tokens


@pytest.mark.parametrize(("text", "value", "percent"), [
    ("(0.6)%", "-0.6", True), ("(0.6) %", "-0.6", True), ("(0.6%)", "-0.6", True), ("-0.6%", "-0.6", True),
    ("12.4%", "12.4", True), ("+12.4%", "12.4", True), ("(5.3)%", "-5.3", True),
    ("$(3,547)", "-3547", False), ("($3,547)", "-3547", False), ("-$3,547", "-3547", False),
    ("(1,577)", "-1577", False), ("-1,577", "-1577", False), ("−1,577", "-1577", False),
    ("$5,363", "5363", False), ("$ 4,835", "4835", False), ("US$12.5", "12.5", False),
    ("1,000,000", "1000000", False), ("0", "0", False), ("0.00", "0.00", False), ("(0)", "0", False),
])
def test_parse_valid(text: str, value: str, percent: bool) -> None:
    p = parse_amount(text)
    assert p is not None and p.value == Decimal(value) and p.percent is percent


@pytest.mark.parametrize("text", ["1,57,7", "1,5", "(7.0", "7.0)", "12..4", "-(3)", "+-3", "$$5", "%5", "", "abc",
                                  "((3))", "5%%"])
def test_parse_rejects_malformed(text: str) -> None:
    assert parse_amount(text) is None and parse_number(text) is None


def kinds(text: str) -> list[tuple[str, str]]:
    return [(t.kind, t.text) for t in scan_numeric_tokens(text)]


def test_scanner_classifies_every_numeric_token() -> None:
    toks = kinds("FY2022 (Note 12, Item 7, page 56, E3): revenue $66,608 million, tax rate (9.9)%; margin (5.3) %; "
                 "December 31, 2022; 10-K; COVID-19; Rule 10b5-1; 401(k); 2020-2022; bad 1,57,7.")
    assert ("value", "$66,608") in toks and ("value", "(9.9)%") in toks and ("value", "(5.3) %") in toks
    assert ("malformed", "1,57,7") in toks
    assert ("year", "2022") in toks and ("year", "2020") in toks and ("date", "31") in toks
    refs = {t for k, t in toks if k == "reference"}
    assert {"12", "7", "56", "10", "19", "401"} <= refs
    assert not any(k == "value" and t in {"12", "7", "56", "19", "401"} for k, t in toks)


def test_scanner_values_and_scale_words() -> None:
    toks = scan_numeric_tokens("Capex was (1,577), i.e. -1,577; cash $4.8 billion; zero 0.0.")
    vals = [(t.value, t.scale_word) for t in toks if t.kind == "value"]
    assert vals == [(Decimal("-1577"), None), (Decimal("-1577"), None), (Decimal("4.8"), "billion"), (Decimal("0.0"), None)]


def test_metrics_module_delegates_to_strict_parser() -> None:
    from app.evaluation.metrics import numbers_in
    from app.evaluation.metrics import parse_number as pn

    assert pn("(0.6)%") == Decimal("-0.6") and pn("1,57,7") is None
    assert numbers_in("Operating margins: (5.3)%; (4.7)%; see Note 12") == [Decimal("-5.3"), Decimal("-4.7")]

"""Evidence-anchored operand binding (Milestone 3.5, AUD-02..AUD-05)."""

from __future__ import annotations

from app.qa.calculator import Step
from app.qa.evidence_binding import OperandClaim, bind_table, bind_text, calculation_checks


def fact(row, cell, value, *, year=2022, ptype="annual", label=None, scale="millions", currency="dollar",
         scope="consolidated", group=None, end=None, pct=False, fid=None):
    return {"factId": fid or f"{row}-{label or year}", "rowLabel": row, "rowGroup": group,
            "columnHeader": label or (str(year) if year else None), "cellText": cell, "value": value,
            "valueStatus": "parsed", "isPercent": pct, "scale": "percent" if pct else scale, "currency": currency,
            "scope": scope, "period": {"label": label or (str(year) if year else None), "fiscalYear": year,
                                       "endDate": end, "periodType": ptype}}


CF = [fact("Net cash provided by operating activities", "6,439", "6439", year=2018),
      fact("Net cash provided by operating activities", "6,240", "6240", year=2017),
      fact("Purchases of property, plant and equipment (PP&E)", "(1,577)", "-1577", year=2018),
      fact("Purchases of property, plant and equipment (PP&E)", "(1,373)", "-1373", year=2017)]


def claim(quote, row, period, metric, scale="millions", currency=None):
    return OperandClaim(id="x", quote=quote, row_label=row, period=period, metric=metric, scale=scale,
                        currency=currency)


def failed(checks, name=None):
    return [c for c in checks if not c["ok"] and (name is None or c["check"] == name)]


def test_paraphrase_only_through_explicit_vocabulary() -> None:
    q = "What was 3M's capital expenditure in 2018?"
    checks, f = bind_table(claim("(1,577)", "Purchases of property, plant and equipment", "2018",
                                 "capital expenditure"), CF, q)
    assert not failed(checks) and f["value"] == "-1577"
    # a metric the row does not name and the vocabulary does not map is rejected
    checks, _ = bind_table(claim("(1,577)", "Purchases of property, plant and equipment", "2018", "dividends paid"),
                           CF, q)
    assert failed(checks, "operand_metric_supported")


def test_wrong_column_and_unknown_period_are_rejected() -> None:
    q = "What was 3M's capital expenditure in 2018?"
    assert failed(bind_table(claim("(1,373)", "Purchases of property, plant and equipment", "2018", "capex"), CF, q)[0],
                  "operand_period_matches")
    unlabelled = [fact("Cash and cash equivalents", "$2,535", "2535", year=None, ptype="unknown")]
    checks, _ = bind_table(claim("$2,535", "Cash and cash equivalents", "2022", "cash and cash equivalents"),
                           unlabelled, "What was AMD's cash at the end of 2022?")
    assert failed(checks, "operand_period_matches")
    assert "no aligned period header" in failed(checks, "operand_period_matches")[0]["detail"]


def test_cumulative_ytd_and_quarterly_columns_need_matching_question() -> None:
    cum = [fact("FLNA", "$210", "210", year=2022, ptype="cumulative", label="Plan to Date through 12/31/2022")]
    c = claim("$210", "FLNA", "2022", "restructuring charges")
    assert failed(bind_table(c, cum, "What were FLNA restructuring charges in 2022?")[0], "operand_period_matches")
    assert not failed(bind_table(c, cum, "What were FLNA cumulative restructuring charges through 2022?")[0],
                      "operand_period_matches")
    ytd = [fact("Net sales", "9,100", "9100", year=2023, ptype="ytd", label="Nine Months Ended Oct 28, 2023")]
    c = claim("9,100", "Net sales", "2023", "revenue")
    assert failed(bind_table(c, ytd, "What were net sales in fiscal 2023?")[0], "operand_period_matches")
    assert not failed(bind_table(c, ytd, "What were net sales for the nine months of 2023?")[0],
                      "operand_period_matches")


def test_point_in_time_dates_bind_by_year() -> None:
    bs = [fact("Cash and cash equivalents", "$4,835", "4835", year=2022, end="2022-12-31", ptype="point_in_time",
               label="December 31, 2022"),
          fact("Cash and cash equivalents", "$2,535", "2535", year=2021, end="2021-12-25", ptype="point_in_time",
               label="December 25, 2021")]
    q = "What was AMD's cash and cash equivalents at the end of 2022?"
    assert not failed(bind_table(claim("$4,835", "Cash and cash equivalents", "December 31, 2022", "cash"), bs, q)[0])
    assert failed(bind_table(claim("$2,535", "Cash and cash equivalents", "2022", "cash"), bs, q)[0],
                  "operand_period_matches")


def test_scale_currency_and_scope() -> None:
    q = "What was 3M's capital expenditure in 2018?"
    row = "Purchases of property, plant and equipment"
    assert failed(bind_table(claim("(1,577)", row, "2018", "capex", scale="thousands"), CF, q)[0], "operand_units_match")
    unknown = [dict(CF[2], scale="unknown")]
    assert failed(bind_table(claim("(1,577)", row, "2018", "capex"), unknown, q)[0], "operand_units_match")
    # currency conversion is never accepted
    assert failed(bind_table(claim("(1,577)", row, "2018", "capex", currency="EUR"), CF, q)[0],
                  "operand_currency_matches")
    assert failed(bind_table(claim("(1,577)", row, "2018", "capex"), CF, q + " Answer in euros.")[0],
                  "question_currency_supported")
    assert not failed(bind_table(claim("(1,577)", row, "2018", "capex", currency="USD"), CF, q)[0])
    # claiming segment scope for a consolidated value is rejected
    assert failed(bind_table(claim("(1,577)", row, "2018", "segment capex"), CF, q)[0], "operand_scope_matches")


def test_ambiguous_value_in_row_is_rejected() -> None:
    dup = [fact("Revenue", "100", "100", year=2022, group="Segment A", fid="a"),
           fact("Revenue", "100", "100", year=2022, group="Segment B", fid="b")]
    checks, f = bind_table(claim("100", "Revenue", "2022", "revenue"), dup, "What was revenue in 2022?")
    assert f is None and "more than one" in failed(checks, "operand_cell_located")[0]["detail"]
    checks, f = bind_table(claim("100", "Revenue Segment B", "2022", "revenue"), dup, "What was revenue in 2022?")
    assert f is not None and f["factId"] == "b"


def test_year_is_never_an_operand() -> None:
    facts = [fact("Fiscal year", "2022", "2022", year=2022)]
    checks, _ = bind_table(claim("2022", "Fiscal year", "2022", "fiscal year"), facts, "What was it in 2022?")
    assert failed(checks, "operand_cell_located")


def test_berkshire_repeated_total_binds_same_period_unit_and_scope() -> None:
    row = "Net earnings attributable to Berkshire shareholders"
    rows = [fact(row, "$ 4,603", "4603", year=2025, ptype="quarterly", label="First Quarter 2025", fid="a"),
            fact(row, "$ 4,603", "4603", year=2025, ptype="quarterly", label="First Quarter 2025",
                 group="Net earnings includes:", fid="b")]
    checks, bound = bind_table(claim("$ 4,603", row, "First Quarter 2025", row), rows,
                               "What were net earnings for First Quarter 2025?")
    assert not failed(checks), checks
    assert bound["value"] == "4603"
    # A conflicting currency or segment scope must not be deduplicated.
    for conflict in ({"currency": "EUR"}, {"scope": "segment"}, {"rowGroup": "Segment B"}):
        checks, bound = bind_table(claim("$ 4,603", row, "First Quarter 2025", row),
                                   [rows[0], dict(rows[1], **conflict)],
                                   "What were net earnings for First Quarter 2025?")
        assert bound is None and failed(checks, "operand_cell_located")


def test_equal_values_in_different_years_bind_only_the_claimed_period() -> None:
    rows = [fact("Revenue", "100", "100", year=2024), fact("Revenue", "100", "100", year=2025)]
    checks, bound = bind_table(claim("100", "Revenue", "2025", "revenue"), rows, "What was revenue in 2025?")
    assert not failed(checks), checks
    assert bound["period"]["fiscalYear"] == 2025


def test_narrative_binding_uses_the_clause_holding_the_value() -> None:
    text = ("Net sales increased 5% to $8.2 billion in 2022, while operating income declined to $412 million "
            "in 2021.")
    q = "What was operating income in 2022?"
    checks, _ = bind_text(claim("$412", "operating income", "2022", "operating income"), text, q)
    assert failed(checks, "operand_period_matches")  # the clause holding $412 says 2021
    checks, _ = bind_text(claim("$412", "net sales", "2021", "revenue"), text, "What was revenue in 2021?")
    assert failed(checks, "operand_row_label_quoted")
    checks, _ = bind_text(claim("$412", "operating income", "2021", "operating income"), text,
                          "What was operating income in 2021?")
    assert not failed(checks), checks


def test_derived_metric_inputs_are_not_required_to_share_the_question_metric() -> None:
    q = "What was 3M's free cash flow in 2018?"
    steps = [Step("fcf", "add", ["ocf", "capex"])]
    metrics = {"ocf": {"operating_cash_flow"}, "capex": {"capital_expenditure"}}
    years = {"ocf": {2018}, "capex": {2018}}
    assert not failed(calculation_checks(q, "fcf", "free cash flow", steps, metrics, years))
    # a free-cash-flow "calculation" missing the capex input, or using the wrong operation, is rejected
    assert failed(calculation_checks(q, "fcf", "free cash flow", steps, {"ocf": {"operating_cash_flow"},
                                                                          "capex": {"net_income"}}, years))
    bad = [Step("fcf", "percent_of", ["ocf", "capex"])]
    assert failed(calculation_checks(q, "fcf", "free cash flow", bad, metrics, years), "calculation_spec_valid")


def test_growth_needs_the_same_metric_in_two_periods() -> None:
    q = "By what percentage did revenue grow from 2021 to 2022?"
    steps = [Step("g", "percent_change", ["a", "b"])]
    ok = calculation_checks(q, "g", "revenue growth", steps, {"a": {"revenue"}, "b": {"revenue"}},
                            {"a": {2021}, "b": {2022}})
    assert not failed(ok)
    assert failed(calculation_checks(q, "g", None, steps, {"a": {"revenue"}, "b": {"revenue"}},
                                     {"a": {2022}, "b": {2022}}))
    assert failed(calculation_checks(q, "g", None, steps, {"a": {"revenue"}, "b": {"net_income"}},
                                     {"a": {2021}, "b": {2022}}))


def test_final_operand_must_match_the_question_metric() -> None:
    q = "What was the company's net income in 2022?"
    assert failed(calculation_checks(q, "r", "revenue", [], {"r": {"revenue"}}, {"r": {2022}}),
                  "final_metric_matches_question")
    assert not failed(calculation_checks(q, "n", "net income", [], {"n": {"net_income"}}, {"n": {2022}}))


# --------------------------------------------------------------------------- regressions found by the real-filing benchmark
def test_known_metric_conflict_is_not_rescued_by_word_overlap() -> None:  # D34
    facts = [fact("Operating income", "1,264", "1264", year=2022)]
    checks, _ = bind_table(claim("1,264", "Operating income", "2022", "net income"), facts, "What was net income in 2022?")
    assert failed(checks, "operand_metric_supported")


def test_table_context_or_row_group_cannot_supply_the_metric() -> None:  # K17, H34
    facts = [fact("Customer deposits", "110,239", "110239", year=2022)]
    checks, _ = bind_table(claim("110,239", "Customer deposits", "2022", "total assets"), facts,
                           "What were total assets in 2022?", context="Assets Liabilities and Shareholders' Equity")
    assert failed(checks, "operand_metric_supported")
    rd = [fact("Research, development and related expenses", "1,862", "1862", year=2022, group="Operating expenses")]
    checks, _ = bind_table(claim("1,862", "Research, development and related expenses", "2022", "operating income"),
                           rd, "What was operating income in 2022?", context="Consolidated Statement of Income")
    assert failed(checks, "operand_metric_supported")


def test_same_year_columns_need_the_full_date() -> None:  # K38/K40 pattern
    bs = [fact("Merchandise inventories", "5,651", "5651", year=2023, end="2023-07-29", ptype="point_in_time",
               label="July 29, 2023"),
          fact("Merchandise inventories", "5,140", "5140", year=2023, end="2023-01-28", ptype="point_in_time",
               label="January 28, 2023")]
    q = "What were inventories as of July 29, 2023?"
    assert not failed(bind_table(claim("5,651", "Merchandise inventories", "July 29, 2023", "inventories"), bs, q)[0])
    assert failed(bind_table(claim("5,140", "Merchandise inventories", "July 29, 2023", "inventories"), bs, q)[0],
                  "operand_period_matches")
    # a bare year cannot pick between two columns of the same year
    assert failed(bind_table(claim("5,651", "Merchandise inventories", "2023", "inventories"), bs, q)[0],
                  "operand_period_matches")


def test_weeks_headers_are_typed() -> None:  # L12
    from app.financial.facts import _period_from

    assert _period_from("13 Weeks Ended January 28, 2023", "", "column_header").period_type == "quarterly"
    assert _period_from("26 Weeks Ended July 29, 2023", "", "column_header").period_type == "ytd"
    assert _period_from("52 Weeks Ended January 28, 2023", "", "column_header").period_type == "annual"


def test_respectively_binds_values_to_periods_positionally() -> None:  # H52/H53
    text = ("Restricted cash was $379 million and $269 million as of January 28, 2023, and January 29, 2022, "
            "respectively.")
    q = "What was restricted cash as of January 28, 2023?"
    assert not failed(bind_text(claim("$379", "Restricted cash", "2023", "restricted cash"), text, q)[0])
    assert failed(bind_text(claim("$269", "Restricted cash", "2023", "restricted cash"), text, q)[0],
                  "operand_period_matches")


def test_outlook_and_relative_clauses_do_not_date_a_value() -> None:  # H56, H57, L28
    s = ("Provisions for credit losses increased versus the prior year, reflecting a reserve build of $617 million "
         "compared with a reserve release of $2.5 billion in the prior year, and are expected to increase in 2023.")
    assert failed(bind_text(claim("$617", "reserve build", "2023", "reserve build"), s, "What in 2023?")[0],
                  "operand_period_matches")
    agg = "We received total gross insurance settlements of $46 million in fiscal years 2023 and 2022."
    assert failed(bind_text(claim("$46", "insurance settlements", "2023", "insurance settlements"), agg,
                            "What in fiscal 2023?")[0], "operand_period_matches")
    cmp_ = ("In 2022, cash flows provided by operating activities decreased $1,863 million compared to the same "
            "period last year, with this decrease primarily due to lower net income.")
    assert not failed(bind_text(claim("$1,863", "cash flows provided by operating activities decreased", "2022",
                                      "decrease in operating cash flow"), cmp_, "By how much in 2022?")[0])

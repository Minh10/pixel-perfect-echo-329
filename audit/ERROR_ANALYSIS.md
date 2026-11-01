# Error analysis

The scope is everything that could be executed without an LLM. LLM-stage errors (wrong reasoning, hallucinated citations, mis-abstention) are **not observed**, because no live run was possible. They are not estimated here either.

Sources:
- `QA_EVALUATION_RESULTS.csv`: 37 real-filing questions, per-stage outputs.
- `artifacts/validation_audit_results.json`: 26 adversarial validator cases on real chunks.
- `services/api/tests/audit/test_audit_findings.py`: 9 strict-xfail reproductions.

## 1. Failure taxonomy (30 answerable real-filing questions)

A question can carry several categories.

| Failure category (pre-LLM) | Questions | IDs | Root cause |
|---|---|---|---|
| Validator rejects gold operand: **units** | 13 | F02 F06 F07 N02 N04 C01 C02 C03 X01 X03 A02 A03 A05 | Chunk has no `Units:` line: units printed in a header row (AMD p54/56), or the table title is lost (PepsiCo p79). The validator requires stated units (AUD-04/06) |
| Validator rejects gold operand: **period** | 12 | F03 F04 F05 F07 F08 N05 M02 M03 X01 A03 A04 A06 | Columns unlabelled and years only in the title (Boeing p24, PepsiCo p62/64) are treated as "ambiguous" (AUD-04) |
| Validator rejects gold operand: **question metric** | 6 | N03 N05 M01 M02 M03 A04 | Every operand of a derived metric must carry the question's metric name (AUD-05); A04: the question asks "operating profit", the filing reports "Loss from operations" |
| Validator cannot locate the value | 2 | C04 (`(0.6)%` unparseable, AUD-01), N03 (6,439 occurs in two statements on p49) | Number parsing / duplicate values |
| Retrieval: no gold page in dense top 8 | 14 | F01 F02 F05 F07 N06 C04 C05 M01 M03 X02 X03 A02 A03 A06 | See §2 |
| Retrieval: partial (multi-evidence) | 3 | N03 M02 X01 | Second document/page not reached in k = 8 |
| No failure detected before the LLM | 1 | N01 | — |

Unanswerable and ambiguous-abstain items (U01–U05, A01, A07): routing behaves as intended (U05 → no company match → whole-corpus search with a warning). Whether the LLM abstains is **not measured**.

## 2. Retrieval misses: what was retrieved instead

For the 14 questions with no gold page in the top 8 (dense, layout):

| Pattern | Questions | Observation |
|---|---|---|
| Same value on another retrieved page (MD&A, notes, another statement) | 10 | F01 (3M p39 capital spending discussion has 1,577), F02/A03 (AMD p58 cash-flow statement ends with 4,835/2,535), F05/N06 (PepsiCo p62/63), F07 (AMD p48/49/68), A02 (AMD p66 inventory note), X02 (3M p34, p39), M01 (p39), A06 (Best Buy p25) |
| Value nowhere in the top 8 | 4 | C04 (Boeing tax rate: unparseable value, AUD-01), C05 (3M investing row: vocabulary), M03 (needs two PepsiCo pages), X03 (Boeing cash on p57 not retrieved) |

**Interpretation:**
- Page-level gold (FinanceBench-style) **understates usable evidence**. Many 10-K figures are restated in MD&A and notes, and citing those would be correct.
- Strict citation-recall against a single gold page would penalise correct behaviour.
- **Recommendation:** add value-level relevance (the gold value with matching row label and period on any page) as a second metric. Don't replace the page-level metric.
- **Vocabulary gap:** "capital expenditure" vs "purchases of property, plant and equipment" (F01, M01, X02) explains several dense-retrieval misses. That's a research opportunity (financial synonym expansion), not a bug.

## 3. Validator error modes (adversarial audit, 26 real-chunk cases)

| Mode | Count | Example | Safety impact |
|---|---|---|---|
| **False accept: period** | 1 | V11: AMD balance sheet with unlabelled columns; the 2021 value $2,535 labelled "2022" passes every check | **Wrong figure presented as verified** |
| Masked false accept (period check passed; rejected by an unrelated check) | 2 | V10 (rejected only for missing units), V17 (cumulative "Plan to Date through 12/31/2022" accepted as FY2022 by the period check; rejected only by label overlap) | Latent: becomes a false accept once AUD-04 is fixed carelessly |
| False reject: paraphrased metric | 1 | V02 "Capital expenditure 2018" vs row "Purchases of property, plant and equipment" | Over-abstention |
| False reject: currency stated by the model but not in the chunk | 1 | V03 label "USD millions", chunk units "(Millions)" | Over-abstention |
| False reject: units missing in chunk | 2 | V09 (AMD), V16 (PepsiCo) | Over-abstention |
| False reject: years only in the table title | 2 | V12, V14 (Boeing) | Over-abstention |
| False reject: two years in one sentence | 2 | V24, V25 (3M employment) | Over-abstention |
| Correct rejections | 14/15 corrupted | wrong row, wrong column year, wrong scale, wrong currency, wrong metric in the same sentence | — |

**Required property** ("cannot associate a valid number with an unrelated period"): **violated** in case V11 and latently in V17.

## 4. Number-handling defects

| Defect | Effect | Reproduction |
|---|---|---|
| `parse_number("(0.6)%")`, `("(5.3)%")`, `("$(3,547)")` → `None`; `numbers_in` drops them | (a) The grounding check ignores such tokens, so an invented `(9.9)%` passes; (b) negative percentages can't be operands; (c) the Boeing tax-rate question (C04) can't be answered | `test_b1_*`, `test_b2_*` |
| Chunker leaves `(7.0; %)` when a `%)` cell follows the number | Malformed value text in evidence | `test_b6_*` |

## 5. What would change these numbers

The pre-LLM ceiling (1/30 questions with complete retrieval and validator acceptance) would rise substantially if AUD-02/04/05/06 were fixed. It must then be **re-measured**, not assumed: fixing the over-rejection without fixing period binding would convert the masked V10/V17 cases into real false accepts.

# Financial evidence schema and normalization (Milestone 3.5)

This document specifies the structured evidence layer added in Milestone 3.5 and the rules the QA validator
uses to bind a model's numeric claims to it. Code: `app/financial/` (schema, numbers, facts, vocabulary,
pipeline) and `app/qa/evidence_binding.py`.

## Layers and versions

| Layer | Version constant | Input | Output |
|---|---|---|---|
| Parsing | `ParserInfo.version` (unchanged) | PDF | `parse.json` (blocks, table cells, bboxes) — **never modified** |
| Normalization | `NORMALIZATION_VERSION = "facts-v1"` (`app/financial/schema.py`) | `parse.json` + PDF word geometry | `TableNormalization` / `FinancialFact` rows (SQLite `financial_facts`) |
| Chunking | `CHUNKER_VERSION = "layout-v3"` (`app/indexing/chunker.py`) | parse + normalizations | layout chunks whose table text carries explicit `column = value` tags and `factIds` |

Normalization is versioned separately from parsing: re-normalizing a document replaces its facts atomically
(`ChunkStore.replace_document_facts`) and fact ids are deterministic
(`sha256(document | table | row | slot | first column | normalization version)`), so re-running never duplicates.
Every fact keeps the verbatim `cellText`, `rowLabel`, `columnHeader` and the cell `bbox`, so a normalized value
always traces back to a PDF region.

## `FinancialFact`

| Field | Meaning | When unknown |
|---|---|---|
| `factId`, `normalizationVersion` | identity / version | — |
| `documentId`, `issuer`, `sourceSha256`, `parser`, `parserVersion` | provenance | `issuer` may be null |
| `tableId`, `page`, `rowIndex`, `colIndices`, `slotIndex`, `bbox` | location: parsed grid row, grid columns merged into the value (e.g. `$` + number + `%`), aligned value column | `bbox` null if the parser gave none |
| `rowLabel`, `rowGroup` | verbatim row label; nearest preceding label-only row (section heading) | `rowGroup` null |
| `columnHeader` | verbatim header text aligned with the value column | null — the column is **unlabelled** |
| `cellText` | verbatim value text, e.g. `(7.0)%`, `$(3,547)` | — |
| `value`, `valueStatus` | exact decimal string; `parsed` / `nil` (—) / `malformed` / `non_numeric` / `empty` | `value` null unless `parsed` |
| `isPercent` | value printed with `%` | — |
| `period` (`label`, `fiscalYear`, `endDate`, `periodType`, `source`) | period read from the aligned column header | all null and `periodType: "unknown"` |
| `scale`, `scaleSource` | `units/thousands/millions/billions/percent/per_share` + verbatim text it came from | `"unknown"` |
| `currency`, `currencySource` | ISO code when printed (`USD`, `EUR`, …); `"dollar"` when only `$`/“Dollars” is printed | null |
| `scope`, `scopeSource` | `consolidated` / `segment` when the table context says so | `"unknown"` |

`periodType` values: `annual`, `quarterly`, `ytd` (six/nine months, year-to-date), `cumulative`
(plan-to-date, “through 12/31/2022”, since inception), `point_in_time` (balance-sheet dates, “as of”), `unknown`.

**Unknown stays unknown.** Nothing is inferred from a document title, filename or the document's fiscal year.
A year that appears only in a table title (e.g. AMD's balance sheet title fragment “December 31, 2022 December
25,”) does not bind any column.

## Normalization algorithm (`app/financial/facts.py`)

1. **Cell merging.** Adjacent `$`, `%`, `)`, `%)`, `)%` cells are merged into the value they belong to
   (`"(7.0"` + `"%)"` → `"(7.0%)"` = −7.0 %).
2. **Value slots.** Numeric cells are clustered into value columns by horizontal-interval overlap (≥ 50 %) of
   their bboxes. Grid column indices are not used for alignment: PyMuPDF grids shift by one wherever a `$` cell
   exists, which was the root cause of misaligned PR #2 columns.
3. **Headers.** Rows before the first data row (including rows that are only years) are header rows. In addition
   the page words above the table are read closest-first, stopping at a paragraph line; a word binds to the slot
   whose x-range contains its centre (±10 pt). Lines without digits become table context, or — when they hold
   several period phrases (“Three Months Ended … Six Months Ended”) — are split and assigned to the nearest slots.
4. **Periods.** Parsed only from slot-aligned header text (`_period_from`): full dates → `endDate`, numeric dates,
   bare years; the period type comes from the header, then the table context. Dates are `point_in_time` for
   balance-sheet / “as of” contexts.
5. **Collisions.** If two values of one row fall into the same slot the binding is ambiguous: both get
   `periodType: "unknown"` and a warning; nothing is guessed.
6. **Scale / currency / scope.** From the table's own units text (“(Dollars in millions)”, “$ in millions”,
   “(Millions)”), else from the latest document-level statement on or before the page (“tabular dollars are in
   millions”), with its source recorded. Previous-page lead-in text (for a table at the top of a page) is kept as
   descriptive context only and is never used for units, currency, scope or periods.

## Number parsing (`app/financial/numbers.py`)

`parse_amount` accepts `(0.6)%`, `(0.6) %`, `(7.0%)`, `$(3,547)`, `($3,547)`, `(1,577)`, `-1,577`, `−1,577`,
`$1.6`, and rejects unbalanced or nested parentheses, double signs, double currency symbols or percent signs.
`scan_numeric_tokens` classifies each numeric-looking token of an answer as `value`, `year`, `date`, `reference`
(`Note 7`, `Item 7A`, `10-K`, `401(k)`, `page 56`) or `malformed`. Malformed tokens fail closed.

## Binding rules (`app/qa/evidence_binding.py`)

A model operand states `quote`, `row_label` (verbatim), `period`, `metric`, `currency`, `scale`. It must bind to
**exactly one** source fact (table evidence) or one clause (narrative evidence):

| Check | Rule |
|---|---|
| `operand_cell_located` | value + row label (optionally its row group) identify exactly one fact; 0 → not found, >1 → ambiguous; a calendar year is never an operand |
| `operand_metric_supported` | the metric's words are in the row label / group / table context, or the paraphrase is listed in `app/financial/vocabulary.py` (e.g. capital expenditure ↔ purchases of property, plant and equipment / additions to property and equipment) |
| `operand_period_matches` | the fact's period is known and its year equals the claimed year; cumulative / YTD / quarterly columns pass only when the question asks for that period type |
| `operand_period_in_question` | operand year is in the question, or is the prior year of a year-over-year question |
| `operand_units_match` | claimed scale equals the fact's scale; unknown scale fails closed |
| `operand_currency_matches`, `question_currency_supported` | asserted currency must be the printed one; `$` is compatible with USD only; currency conversion is rejected |
| `operand_scope_matches` | a claimed segment / consolidated scope must be stated by the source |
| `operands_scope_consistent`, `operands_currency_consistent` | operands feeding one result may not mix scopes or currencies |
| `calculation_spec_valid` | derived metrics (free cash flow, margins, ratios, growth) are checked against a registered specification of operation + input metrics; inputs are validated individually and are **not** required to carry the question's metric name |
| `final_metric_matches_question` | a non-derived final operand must measure the metric the question asks for |

Narrative evidence binds to the clause holding the value (sentences are split at *and / while / whereas / but /
;* when several clauses hold numbers); the year is taken from the value's comma segment, then its clause, then
the sentence — each only if it names exactly one year.

## Answer text

Every value in the answer must be an operand or a (rounded / rescaled) calculation result, or restate the
question. A number that merely appears in a cited excerpt is not accepted — it has not been bound to a row,
period and unit (this closed the path by which injected document text could supply a figure). Years must appear
in the question or cited evidence; malformed numerics fail closed; sentences that look like instructions, links
or contact details are rejected, and other sentences need content-word support in the cited evidence.

## Untrusted document content

Evidence is rendered inside `<evidence id="E1"> … </evidence>` fences; a literal `</evidence>` inside document
text is neutralised; the system prompt states that fenced content is data, never instructions. These are
mitigations, not guarantees about model behaviour: they have been tested only with a scripted model double.

## Known limitations

* Facts come from PyMuPDF geometry; tables without word geometry or with merged multi-row labels can produce
  `unknown` periods (fail closed → abstention).
* The metric vocabulary is small and explicit; unlisted paraphrases are rejected (false rejects, not accepts).
* Row-label matching is substring-based on normalized text; a claimed label that is a substring of several rows
  is reported as ambiguous.

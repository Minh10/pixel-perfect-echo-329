# FINAUDIT AI — Independent AI Validation and Research Audit

**Subject:** PR [Minh10/pixel-perfect-echo-329#2](https://github.com/Minh10/pixel-perfect-echo-329/pull/2) (`feature/fullstack-ai-integration` @ `ed9e7e2`), which contains Milestones 1 and 3 (PR #1) plus the full-stack integration.
**Audit branch:** `audit/ai-validation`. It adds reports, audit scripts, strict-xfail bug reproductions and a CI workflow. No production code was changed, and PR #2 was not merged.
**Auditor:** Claude (AI agent). This is an *independent* review in the sense that every claim was re-executed against fresh builds. It is not independent of the author: the same agent wrote Milestones 1 and 3, and the findings include defects in its own earlier work.

## Decision: **NOT READY for Milestone 4**

Milestone 4 (financial discrepancy auditing) needs a QA and validation layer that is evaluated and correct on real filings. Neither condition holds:

1. **End-to-end QA has never been run with an LLM.** No LLM credentials were supplied (blocker B-LLM). Answer accuracy, numerical accuracy, citation precision/recall, abstention quality, LLM latency and token cost are therefore **not measured**, and none are claimed.
2. **The evidence validator is unreliable on real 10-Ks**, in both directions:
   - It **accepts a value from the wrong period** (1 of 15 corrupted cases). Two more wrong-period cases were rejected only by an unrelated check.
   - It **rejects 8 of 11 correct associations**.
   - In the 30-question real-filing set it rejects the gold operands of **25 of 30** questions. The gold operands were given the truest labels available.
3. **A grounding bypass exists:** an invented number written as `(9.9)%` passes the answer-grounding check (AUD-01). The root cause is that parenthesised negative percentages are not parsed.
4. **No CI exists**, so none of these properties are enforced on change.

### What *is* verified

- **Retrieval:** results reproduce **exactly** from a fresh rebuild. That covers 120 per-query metric series, every CI and every p-value (`RETRIEVAL_REPRODUCIBILITY_REPORT.md`).
- **Chunking:** fully deterministic (18,079 / 18,079 chunks identical in id and content).
- **Tests:** backend 122 passed (plus 1 skip and 9 strict-xfail reproductions); frontend 7/7. Typecheck, lint (0 errors) and build pass.
- **Full stack:** live UI + API smoke test passes 9/9 in a real browser. Bboxes align on a real 10-K page (screenshot), and the 503 state is honest.
- **Security:** 13/13 runtime probes pass, no secrets in git history, and no known vulnerabilities in the 154 backend Python packages.

### Exit criteria for "READY"

| # | Criterion | Evidence required |
|---|---|---|
| 1 | AUD-01…AUD-06 fixed; the 9 strict-xfail tests in `services/api/tests/audit/` flip to passing (and their markers are removed) | CI green |
| 2 | Validator re-audited on real filings: **0 false accepts** and ≤ 20% false rejects on an expanded adversarial set (≥ 60 cases, ≥ 6 filings) | `validation_audit.py` output |
| 3 | Live QA evaluation on `qa_audit_set.jsonl` (37) **and** the FinanceBench benchmark (71), with a configured provider; per-question outputs reviewed by a human | `run_qa_eval.py` + reviewed CSV |
| 4 | CI (`.github/workflows/ci.yml`) running and green, including the API contract check | GitHub Actions run |
| 5 | Docling path verified on ≥ 3 real filings, or the PyMuPDF-only decision recorded explicitly | ingest log + retrieval rerun |

**Conditionally ready** would be justified once criteria 1, 2 and 4 are met and criterion 3 has been run, even with modest accuracy, because the numbers would then be real.

---

## 1. Environment and blockers (what could and could not be executed)

| Item | Status | Evidence |
|---|---|---|
| LLM provider credentials (`FINAUDIT_LLM_API_KEY`, `ANTHROPIC_API_KEY`, OpenAI-compatible key) | **BLOCKER: not supplied.** Ambient cloud credentials (`AWS_*`, `CLOUDSDK_*`) exist in the session but were not designated for this provider, and Bedrock is not a supported provider, so they were **not** used | `qa_audit.py` records `NOT RUN — no LLM provider configured` for each item |
| Docling model weights (huggingface.co) | **BLOCKER:** egress proxy returns 403. Real Docling extraction is **unverified**; all real-filing results use the PyMuPDF parser | `backend_pytest.txt` (skip reason) |
| MiniLM dense retrieval on real filings | **Verified.** 14 documents / 2,321 pages; exact reproduction | `RETRIEVAL_REPRODUCIBILITY_REPORT.md` |
| VLM chart interpretation | **Not tested** (needs an LLM). No chart-understanding claim is made | §8 |
| Qdrant server mode | Not exercised; embedded mode only | — |

## 2. PR #2 review: changes, regressions, consistency

PR #2 = PR #1 (unchanged) + `770a3ba` (workspace ↔ API) + `f3339e8` (AI Analysis + operand-association validator) + `ed9e7e2` (synthetic smoke set).

- **Regressions in tests:** none. Backend 122 passed, versus 113 on PR #1 plus the new validator tests. Frontend `tsc`, lint, test and build pass.
- **Behavioural change in the validator:**
  - PR #1 never rejected on metric or period association; label overlap was informational. By construction it would accept all 15 corrupted cases in `validation_audit.py`.
  - PR #2 rejects 14 of 15 corrupted cases, a large safety improvement, but also 8 of 11 correct ones, a large recall regression.
  - The PR's own tests use only the synthetic fixture, whose vocabulary ("turnover", "profit for the year") matches the hard-coded `_METRIC_PHRASES`. The over-rejection on US 10-K language was therefore invisible to them (AUD-07).
- **Architecture consistency (AGENTS.md):**
  - All frontend data access goes through `src/lib/api/service.ts`.
  - Demo mode keeps the `PendingModule`.
  - In live mode no demo data is mixed in (e2e check), and the 503 path is honest.
  - Compliant.
- **API contract:** `eval/audit/contract_check.py` compares all 22 TS interfaces and 6 enums with OpenAPI. One error: TS `JobStage` lacks the backend's `indexing` (AUD-10). It is runtime-harmless (displayed as text) but a type drift. The committed `openapi.json` is in sync with the code.
- **Other PR #2 changes:**
  - `numpy` is pinned to 2.4.6, but all testing used 2.5.4 (AUD-11).
  - Uploads are now read fully into memory (≤ 100 MB) to work around Windows file locks (AUD-13).

## 3. Retrieval reproduction (task 3)

All B1–B4 and ablation configurations were re-run from a fresh download, ingestion, benchmark build and index, using PR #2's code.
- **Metrics:** every per-query value is identical to the committed results (max |Δ| = 0.000000).
- **Statistics:** CIs and paired p-values are identical.
- **Latency:** not reproducible as a number (p50 differs by up to about 2× between runs).

The committed conclusions stand:
- dense retrieval accounts for the gains;
- layout chunking alone did not improve recall;
- hybrid did not beat dense;
- nothing survives Holm correction.

Details are in `RETRIEVAL_REPRODUCIBILITY_REPORT.md`.

## 4. End-to-end QA evaluation (tasks 4–6)

`eval/audit/qa_audit_set.jsonl` contains **37 independently verifiable questions on real SEC filings**:

| Category | Items |
|---|---|
| Factual | 8 |
| Numerical calculation | 6 |
| Complex tables | 5 |
| Multi-page | 3 |
| Cross-document | 3 |
| Unanswerable | 5 |
| Ambiguous currency / unit / period / metric / scope | 7 |

Each gold answer cites document, page, row label and value. **An executed check confirmed every gold label/value pair in the PDF's raw text layer: 37/37**, independent of the system's parser and chunker. Unanswerable items are verified by term absence or period logic.

**What was run:** every stage up to the LLM. Per-question results are in `QA_EVALUATION_RESULTS.csv`.

| Stage (30 answerable questions) | Result |
|---|---|
| Document routing (gold document among routed) | 30/30 (the only unrouted item is the out-of-corpus U05, correctly) |
| QA-default retrieval (dense · layout, k = 8): **all** gold pages in top 8 | 13/30 (43%); partial 3; none 14 |
| …of the 14 "none": the gold value is present on another retrieved page (MD&A, notes) | 10/14 |
| Hybrid retrieval, all gold pages in top 8 | 10/30 |
| Validator accepts the gold operands (best-case labels) | **5/30 (17%)** |
| Retrieval complete **and** validator accepts | **1/30** |

**Not measured:** answer accuracy, numerical accuracy, citation precision/recall, abstention quality, LLM latency and token cost. Every one of those cells in the CSV reads `NOT MEASURED (no LLM run)`.

**Indicative conclusion:** with the current validator, a live run would abstain on the large majority of answerable real-filing questions, whatever the LLM's quality. This is the main reason for the decision.

## 5. Evidence validation engine (task 7)

`eval/audit/validation_audit.py` runs 26 cases on **real chunks**. 11 are correct associations; 15 are corrupted in exactly one dimension: row, period, column, scale or currency.

| | Result | Cases |
|---|---|---|
| False accepts (wrong association accepted) | **1/15** | V11: AMD 2021 cash ($2,535) accepted as 2022 |
| Wrong-period cases rejected only by an *unrelated* check (period check passed) | 2 | V10 (units), V17 (label overlap; "Plan to Date through 12/31/2022" read as FY2022) |
| False rejects (correct association rejected) | **8/11** | paraphrase (V02), USD label with "(Millions)" units (V03), no units line (V09, V16), years only in title (V12, V14), two years in one sentence (V24, V25) |

**Required property:** "cannot associate a valid number with an unrelated metric or period".
- **Not met** for periods when column headers are absent (AUD-02) or cumulative (AUD-03).
- **Met** for metric rows and scale in the tested cases.
- The grounding check additionally misses parenthesised negative percentages (AUD-01).

## 6. Findings

Severity: **High** = can produce wrong or ungrounded output, or blocks release. **Medium** = significant functional or test gap. **Low** = hygiene.

| ID | Sev | Type | Finding | Evidence |
|---|---|---|---|---|
| AUD-01 | High | Correctness bug | `parse_number`/`numbers_in` drop `(0.6)%`, `(5.3)%`, `$(3,547)`. Consequences: the answer-grounding check **does not see** such numbers, so an invented `(9.9)%` passes; and negative percentages can't be operands | `test_b1_*`, `test_b2_*` |
| AUD-02 | High | Correctness bug | Period check passes a wrong-period value when the table has no column period labels and the header names one year | `test_b3_*`, V11 |
| AUD-03 | Medium | Correctness bug | A cumulative "Plan to Date through 12/31/2022" column is treated as fiscal 2022 | `test_b4_*`, V17 |
| AUD-04 | High | Correctness bug (over-rejection) | Validator rejects most correct real-filing associations (8/11; gold operands of 25/30 questions). Failed-check counts across gold operands: units 16, period 16, question-metric 7 | `validation_audit.txt`, CSV |
| AUD-05 | High | Correctness bug | `operand_metric_matches_question` requires *every* operand to carry the question's metric, so any question naming a derived metric (free cash flow, margin, ratio) fails on all its inputs | `test_b5_*`; N03, N05, M01–M03 |
| AUD-06 | Medium | Correctness bug (data) | Chunker misses units and periods printed in table header rows. AMD p56 shows "(In millions…)" and "December 25, 2021" on the page, but the chunk has neither (see `artifacts/e2e_evidence_link.png`). Also `(7.0; %)` mis-merge | `test_b6_*`, V09, V16 |
| AUD-07 | Medium | Test gap | Validator tests use only synthetic UK vocabulary; there are no real-filing validator tests | §2 |
| AUD-08 | High | Release | No CI pipeline (no `.github/`) | added `.github/workflows/ci.yml` |
| AUD-09 | Medium | Test gap | Frontend has only routing tests (7). No tests for `http-service` error mapping, Analysis states or citation deep links | `frontend_checks.txt` |
| AUD-10 | Low | Contract | TS `JobStage` lacks `indexing` | `contract_check.txt` |
| AUD-11 | Low | Reproducibility | `numpy==2.4.6` pinned, but tests ran on 2.5.4 | `pyproject.toml` |
| AUD-12 | Low | Documentation | `eval/README.md` states 10,081 layout chunks; the real count is 10,050 (a stale v1 figure) | reproducibility report |
| AUD-13 | Low | Robustness | Upload validation loads the whole file into memory | `processing/validation.py` |
| AUD-14 | Medium | Research / data quality | Figure detection: of 8 random real figure regions, 3 are text blocks; none classified; no VLM tested | §8 |
| AUD-S* | — | Security | See `SECURITY_AND_RELEASE_AUDIT.md` (no auth or rate limit on `/qa`; 28 pre-existing frontend advisories; non-numeric answer text unvalidated) | — |

## 7. Recommendations

### Correctness bugs (fix before Milestone 4)

1. **AUD-01:** parse `(x)%`, `(x) %`, `$(x)` and `($x)` as negatives. In the grounding check, fail closed on any numeric-looking token that cannot be parsed.
2. **AUD-02/03:** attach a period to every value at chunk time (column header, or period recovered from context only on an exact count match). The validator must require the operand's year to equal *that cell's* period. A header that merely contains a year is not enough. Reject columns whose header contains "to date", "cumulative", "through", "YTD" or "since" unless the question asks for that.
3. **AUD-05:** check the question metric against the *final* value (or the calculation description), not each input operand.
4. **AUD-04/06:**
   - Capture units from header rows and text above the table into chunk metadata.
   - Accept the issuer's reporting currency from document metadata when the chunk carries `$` or `Dollars`.
   - Replace the fixed `_METRIC_PHRASES` list with row-label anchoring: the operand must come from the row whose label the model *quotes*, enforced by a required `row_label` quote field checked verbatim.
5. **AUD-07/09:** add real-filing validator fixtures (the `validation_audit.py` cases, frozen as text) and frontend tests for error states and deep links.

### Release

- **AUD-08:** enable the CI workflow. The contract step will fail until AUD-10 is fixed, which is intentional.
- **AUD-11:** align pins with the tested environment.
- **Security:** add auth and rate limits before any non-local deployment (see the security report).

### Research opportunities (not bugs; claim gains only with measured evidence)

- Financial query expansion: synonyms such as capex ↔ "purchases of property, plant and equipment" (F01, M01 misses).
- Table-aware reranking.
- Docling layout and TableFormer on the same benchmark (blocked here).
- Page-level gold understates usable evidence (10/14 misses had the value elsewhere). Add value-level relevance as a second metric.
- A VLM chart evaluation with real charts and annotated values; the corpus has at least 3 real charts in an 8-region sample.

## 8. Visual retrieval (task 8): audited separately

| Item | Finding |
|---|---|
| Figure regions detected | 99 in the real corpus (1 synthetic) |
| Captions | 3 |
| Classifications | 0 (the PyMuPDF path has no classifier) |
| Random sample of 8 real regions, inspected visually | 3 data charts (AES waterfalls and infographic), 2 non-data images (map, logo), 3 text blocks misdetected as figures (`artifacts/visual_figure_sample_montage.png`: fig0–fig7, sampled with `random.seed(7)` from the 98 real-filing figure chunks) |
| Chart interpretation (VLM) | **Never executed.** No `chart_interpretations` row exists in any corpus |
| Chart questions in the benchmark | 3, all on the synthetic fixture |

**No chart-understanding accuracy is claimed.** Figure *retrieval* on the synthetic chart works (Recall@10 = 1.0, n = 3, too small to generalise). The table cross-check logic for visual estimates is covered by unit tests with a scripted VLM test double.

## 9. Integration and CI (task 10)

| Check | Result |
|---|---|
| Live stack: Vite dev server (live mode) + FastAPI on the fresh real corpus, driven by Playwright | `audit/e2e_smoke.cjs`, **9/9 checks pass** |
| Documents | Live documents shown, no demo data mixed in |
| Workspace | Renders AMD p.56 from the API page image; the bbox overlay aligns with the printed table (screenshot) |
| `?ev=` deep link | Selects the evidence |
| Analysis without LLM | `POST /qa` → 503, with the honest "not configured" state and no value rendered |
| Unexpected API errors | None |
| CI | Added `.github/workflows/ci.yml`: backend pytest (incl. strict xfail reproductions), OpenAPI drift, API contract, frontend tsc/lint/test/build, informational dependency audits |

## 10. Artifact index (`audit/artifacts/`)

| File | Contents |
|---|---|
| `backend_pytest.txt`, `frontend_checks.txt` | Test results |
| `contract_check.txt` / `.json` | API contract comparison |
| `validation_audit.txt` / `_results.json` | Adversarial validator audit (26 real-chunk cases) |
| `qa_audit_results.json` | Full per-question stage outputs (also `../QA_EVALUATION_RESULTS.csv`) |
| `retrieval_report_committed.md`, `retrieval_report_reproduction.md` | Before and after reproduction |
| `security_probe.txt`, `frontend_bun_audit.txt`, `backend_pypi_vulnerability_lookup.txt` | Security evidence |
| `e2e_*.png` | Full-stack screenshots |

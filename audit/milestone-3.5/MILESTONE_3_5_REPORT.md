# Milestone 3.5: Financial Evidence Grounding & Validation Hardening

Branch `fix/evidence-grounding`, based on the audit branch `audit/ai-validation` (`ab8ed0b`), which is itself on
top of PR #2 (`feature/fullstack-ai-integration` @ `ed9e7e2`). No LLM was executed: no provider credentials
were supplied, and ambient cloud credentials were deliberately not used. **Every number below comes from
deterministic code (parser, normalizer, validator, retrieval). No end-to-end QA accuracy is claimed.**

## 1. Decision

**NOT READY for live LLM evaluation against the gate set for this milestone.**

| Gate (held-out) | Result on the last clean held-out set (held-out-4, final code, evaluated once) | Met? |
|---|---|---|
| 0 observed false accepts | 0/15 (95 % CI 0–21.8 %) | Met, but on a small sample |
| ≤ 20 % false rejects | **8/11 = 73 %** (95 % CI 39–94 %) | **No** |
| Reject fabricated negative percentages | `(9.9)%`-style inventions are rejected (AUD-B2 test, D27–D31 parse cases) | Met |
| Correct metric / period / currency / unit / scope binding | 0 false accepts across all 104 should-reject cases with the final code (post hoc, see §4) | Met post hoc only |

The validator is now **fail-closed**: its remaining errors are mostly unnecessary rejections, not wrong
acceptances. A live run today would mainly measure abstentions on segment tables and on tables whose headers
the geometry does not align. Before a live evaluation, three steps remain:

1. Fix the held-out-4 false-reject classes: segment rows whose table never prints the word "segment", segment
   values missing from chunks, and spanning headers.
2. Freeze a new held-out set of ≥ 60 cases and evaluate it once.
3. Supply credentials through the environment.

If that run shows 0 false accepts and ≤ 20 % false rejects, the decision becomes READY.

The application is **not production-secure**; see §8.

## 2. Before / after: every audit finding

| ID | Finding (from `audit/AI_VALIDATION_REPORT.md`) | Status | Evidence |
|---|---|---|---|
| AUD-01 | `(0.6)%`, `(5.3)%`, `$(3,547)` dropped; an invented `(9.9)%` passed grounding | **Fixed.** Strict parser (`app/financial/numbers.py`). The answer scanner fails closed on malformed numbers. Answer values must be operands or calculation results (a number merely present in a cited chunk no longer counts) | `test_b1_*`, `test_b2_*` pass (markers removed); `tests/unit/test_financial_numbers.py` |
| AUD-02 | Wrong-period value accepted when columns are unlabelled and the title names a year | **Fixed.** Periods come only from slot-aligned headers; unknown period → reject | `test_b3_*` passes; V10/V11 rejected |
| AUD-03 | Cumulative "Plan to Date" column treated as FY2022 | **Fixed.** Period types: cumulative / YTD / quarterly / point-in-time; a typed column is accepted only when the question asks for that type | `test_b4_*` passes; V17, H41, H46, H48, K34 rejected |
| AUD-04 | Over-rejection of correct real-filing associations (8/11; gold operands of 25/30 questions) | **Largely fixed.** Real-filing dev FR 15/18 → 4/18; gold operands accepted 8/41 → 38/41 (§5). Held-out-4 still has a 73 % FR (§1) | §4, §5 |
| AUD-05 | Every operand had to carry the question's metric, so derived metrics always failed | **Fixed.** Inputs are validated individually; derived metrics are checked by calculation specs (`DERIVED` in `vocabulary.py`); `final_metric_matches_question` applies only to a non-derived final value | `test_b5_*` passes; D37 accepted; `test_derived_metric_*` |
| AUD-06 | Chunker missed header-row units and periods; `(7.0; %)` mis-merge | **Fixed** for the audited tables (AMD p56: Dec 31 2022 / Dec 25 2021, millions). Chunker `layout-v3` serialises `column = value` with explicit period tags | `test_b6_*` passes; `FINANCIAL_EVIDENCE_SCHEMA.md` |
| AUD-07 | No real-filing validator tests | **Fixed.** 192 benchmark cases from 12 real filings plus 1 synthetic, replayed offline in CI from frozen evidence | `tests/unit/test_grounding_benchmark.py` |
| AUD-08 | No CI | Workflow from the audit kept. It must be observed green on the PR (§9) | `.github/workflows/ci.yml` |
| AUD-09 | Frontend has only routing tests | **Not addressed** (out of scope). The UI change is small and type-checked | — |
| AUD-10 | TS `JobStage` lacks `indexing` | **Fixed.** Contract check: 1 error → 0 | `contract_check.txt` |
| AUD-11 | `numpy==2.4.6` pinned; tests ran on 2.5.4 | **Not changed.** CI installs from `pyproject.toml`, so CI runs the pinned set | — |
| AUD-12 | README layout-chunk count stale | **Fixed** in `eval/README.md` (v2: 10,050; v3: 10,606) | — |
| AUD-13 | Upload validation reads the whole file into memory | **Not changed** (documented, §8) | — |
| AUD-14 | Figure detection quality | **Not addressed** (Milestone 4 territory) | — |
| AUD-S2 | Prompt injection; non-numeric answer text unvalidated | **Mitigated** (§7) | `tests/unit/test_prompt_injection.py` |

Audit reproductions: baseline `122 passed, 1 skipped, 9 xfailed` → now **all 9 pass with markers removed**.
Full backend suite: **384 passed** (the 1 Docling-model test is deselected, as in CI; `pytest_final.txt`).

## 3. What was built

- **Structured evidence:** `FinancialFact` (normalization `facts-v1`, versioned separately from parsing) for
  every value cell. Each fact carries:
  - row and row group;
  - verbatim cell text;
  - the aligned column header;
  - period (fiscal year, end date, type);
  - scale, currency and scope, each with the verbatim text it was read from;
  - bbox and provenance.

  Unknown stays unknown. 33,951 facts over the 14-document corpus. Stored in `financial_facts`, served by
  `GET /api/v1/documents/{id}/facts`.
- **Binding validator** (`app/qa/evidence_binding.py`): the model must state `row_label`, `period`, `metric`,
  `currency` and `scale` for every operand, and the claim must bind to exactly one fact or one clause. The rules
  are in `services/api/docs/FINANCIAL_EVIDENCE_SCHEMA.md`.
- **Pipeline:**
  - plan schema v2 (operand fields + `final.metric`);
  - evidence fenced as untrusted `<evidence>` data;
  - mixed-scope and mixed-currency checks across operands;
  - rescaling variants for answer numbers.
- **Chunker `layout-v3`:** tables are serialised from facts with explicit period tags and `factIds`.

## 4. Real-filing grounding benchmark

`services/api/eval/grounding/`: 192 cases, 12 real filings (3M ×3, AMD, Boeing, PepsiCo, Best Buy ×2, Amcor,
CVS, AmEx, AES, Ulta) plus the synthetic fixture.

**Labelling.** Every case was written from raw PDF page text. `verify_cases.py` then re-checks each one against
PyMuPDF page text, independently of the system under test: 192/192 verified.

**No human review.** Cases were reviewed by a second-pass mechanical check, not by an independent human
annotator. The semantic label (which column a value belongs to) is the author's reading, recorded per case in
`note`.

**Protocol.** Each held-out set was frozen in a commit before its first evaluation; hashes are in
`HELDOUT_FROZEN.sha256`. When a run exposed a bug and the fix was tuned on that set, a fresh set was frozen
before the fix and the used set was reclassified as non-independent:

| Round | Code state | Commit freezing the newly evaluated set | Run |
|---|---|---|---|
| 1 | binding v1 | held-out-1 `d17fd23` | `round1_prefix/` |
| 2 | header/period/metric fixes | held-out-2 `e7fb080` | `round2/` |
| 3 | row-level metric rule | held-out-3 `477a9ee` | `round3/` |
| 4 | weeks / sub-annual / comparison fixes | — (no new set: post hoc) | `round4_postfix/` |
| 5 | **final** (`1ae42ad`) | held-out-4 `1ae42ad` | `round5_final/` |

**Clean measurements** (each set's single evaluation before any fix it informed). FA = false accepts among
should-reject cases; FR = false rejects among should-accept cases. 95 % Clopper–Pearson intervals:

| Set (cases, filings) | M3.5 validator at the time | | PR #2 validator, same cases | |
|---|---|---|---|---|
| | FA | FR | FA | FR |
| held-out-1 (58, 8) | 4/32 (3.5–29 %) | 15/26 (37–77 %) | 1/32 | 25/26 |
| held-out-2 (40, 8) | 1/20 (0.1–25 %) | 0/20 (0–17 %) | 0/20 | 20/20 |
| held-out-3 (30, 2) | 1/17 (0.2–29 %) | 2/13 (2–45 %) | 1/17 | 10/13 |
| held-out-4 (26, 4) | **0/15 (0–22 %)** | **8/11 (39–94 %)** | 0/15 | 11/11 |

**Final code on all sets** (post hoc, not independent, because sets 1–3 informed the fixes):

| Validator | FA | FR |
|---|---|---|
| M3.5 | **0/104 (0–3.5 %)** | 17/88 = 19 % (12–29 %) |
| PR #2 | 6/104 | 68/88 |

Zero observed false accepts is **not** evidence of a zero false-accept probability. On held-out-4 alone the data
are consistent with a rate of up to 22 %.

**How the PR #2 baseline was run.** Its validator was loaded verbatim from `ab8ed0b` (with its own number
parser) and run on the layout-v2 index it was designed for. Its operand label is `"<metric> <period>"`.

**Remaining false rejects (final code):**
- Segment rows whose table never states "segment": the strict scope rule.
- 3M segment values missing from all chunks (NO_EVIDENCE).
- Ulta's spanning "13 Weeks Ended" header: the period length is not aligned, and the table reports sub-annual
  periods, so the binding fails closed.
- PepsiCo FLNA rows: the metric appears only in text before the table.
- A percent-of-sales column with no aligned header.
- An inflected narrative metric.

## 5. 37-question pre-LLM QA audit (re-run on layout-v3)

`audit/milestone-3.5/qa_audit_v3/`. The gold operand is given with its verbatim row label, the period of its
own column (or the question's single year) and the gold scale. It is then bound by the M3.5 validator against
the stored facts. This is an **upper bound for the validator stage**: the period comes from the fact itself, so
it tests binding consistency, not the model's ability to state the right period.

| Of 30 answerable questions | PR #2 baseline (layout-v2) | M3.5 (layout-v3) |
|---|---|---|
| Validator accepts every gold operand | 5/30 | **27/30** |
| Dense retrieval returns every gold page in the top 8 | 13/30 | 15/30 |
| Both (the pipeline *could* answer) | **1/30** | **13/30** |
| Gold operands accepted | 8/41 | 38/41 |

Remaining validator rejections:
- N03: the value appears in two cells of the same row label (ambiguous).
- C02: the question names no single year.
- C03: the gold label "Total" doesn't match the row.

The LLM stage is **NOT RUN**: no provider is configured. Answer accuracy, citation precision and recall, latency
and cost are not measured and are not estimated.

## 6. Retrieval on layout-v3

`run_retrieval_eval.py` was re-run on the reindexed corpus: layout-v3, 10,606 layout chunks (previously
10,050); the 8,029 flat chunks are unchanged. ONNX MiniLM embedder; same 63-item benchmark. Full report:
`retrieval_layout_v3/`. The committed M3 results in `eval/results/` are left untouched.

Recall@10:

| Config | v2 gold doc | v3 gold doc | v2 open | v3 open |
|---|---|---|---|---|
| B1 BM25 · flat | 0.413 | 0.413 | 0.349 | 0.349 |
| B2 dense · flat | 0.571 | 0.571 | 0.500 | 0.500 |
| B3 BM25 · layout | 0.405 | 0.421 | 0.294 | 0.294 |
| B4 hybrid · layout | 0.516 | 0.540 | 0.444 | 0.452 |
| dense · layout (QA default) | 0.563 | 0.571 | 0.444 | 0.452 |

Layout configurations move by +0.008 to +0.024: that is one or two of the 63 items. No comparison survives
Holm correction (smallest adjusted p = 0.117). **Layout-v3 is neutral for retrieval.** Its purpose is
correct value binding, not recall, and no retrieval improvement is claimed.

## 7. Untrusted document content (prompt injection)

**Mitigations:**
- Evidence is fenced as `<evidence id=…>` data, and a literal closing tag inside a document is neutralised.
- The system prompt says fenced content is never instructions.
- Answers containing links, "ignore previous instructions"-style text or contact details are rejected.
- Every other answer sentence needs content-word support from cited evidence.
- Answer numbers must be validated operands or calculation results.

**Tests** (`tests/unit/test_prompt_injection.py`, real PyMuPDF-parsed PDF with an embedded injection): with a
*scripted* model that obeys the injection — a planted URL, a fabricated figure, "ignore previous instructions",
or an unsupported claim — the answer is rejected. A correct answer from the same page still validates.

**Limits.** This tests the deterministic guards, not any real model's resistance. Content-word support is a
heuristic: a fluent unsupported claim reusing evidence vocabulary can pass.

## 8. Security and dependencies (unchanged by this milestone, listed separately)

- **Authentication / authorisation / rate limiting:** none (S-1, High for any non-local deployment). `/qa` will
  spend LLM tokens per request once configured. Mitigation is only the localhost binding.
- **Frontend dependencies:** `bun audit` reports **28 advisories (1 critical, 14 high, 12 moderate, 1 low)**,
  identical to the audit. `bun.lock` was not changed (`frontend_bun_audit.txt`).
- **Backend dependencies:** no new dependencies were added. The audit's PyPI lookup found 0 known
  vulnerabilities; it was not re-run (OSV unreachable).
- Runtime security probes: **13/13 pass** (`security_probe.txt`).
- S-5 (exception text in job errors), S-6 / AUD-13 (in-memory upload validation), S-7 (in-process PDF parsing)
  and S-8 (Qdrant without an API key) are unchanged.

The application must not be described as production-secure.

## 9. Reproduce

```bash
cd services/api
PYTHONPATH=. python eval/grounding/verify_cases.py --corpus <corpus> eval/grounding/cases_*.jsonl
PYTHONPATH=. python <reindex: index_document(..., chunk_sets=("layout",))> # layout-v3 + facts
PYTHONPATH=. python eval/grounding/run_benchmark.py --db <corpus-v3>/finaudit.sqlite3 \
    --legacy-db <corpus-v2>/finaudit.sqlite3 --out <dir>
PYTHONPATH=. python eval/audit/qa_audit.py --corpus <corpus-v3> --csv out.csv --json out.json
pytest -q -m "not docling_models"          # includes the offline benchmark replay
```

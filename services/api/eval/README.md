# FINAUDIT retrieval and QA benchmark

## Reproduce

Run these from `services/api`, in order:

```bash
python eval/fetch_financebench.py
```

```bash
python -m app.retrieval.fetch_models
```

```bash
PYTHONPATH=. python eval/ingest_corpus.py --workers 4
```

```bash
PYTHONPATH=. python eval/build_benchmark.py
```

```bash
PYTHONPATH=. python eval/run_retrieval_eval.py --reindex --embedders onnx wordllama
```

```bash
PYTHONPATH=. python eval/run_qa_eval.py
```

What each step does:
1. **`fetch_financebench.py`** downloads the FinanceBench questions and 13 SEC filings at commit
   `cc39aeb`, verified against `financebench.lock.json`.
2. **`fetch_models`** fetches the all-MiniLM-L6-v2 ONNX embedder, checksum-pinned.
3. **`ingest_corpus.py`** parses the filings through the production upload → job → worker path. It
   uses PyMuPDF by default; pass `--parser docling` where the Docling models are available.
4. **`build_benchmark.py`** writes `data/benchmark.jsonl` and `results/benchmark_report.md`.
5. **`run_retrieval_eval.py`** builds the index (both chunk sets, both embedders) and runs B1–B4 plus
   ablations. It writes `results/retrieval_results.json` and `results/retrieval_report.md`.
6. **`run_qa_eval.py`** runs end-to-end QA. It needs an LLM provider (`FINAUDIT_LLM_*`) and writes
   `results/qa_results.json`.

## Synthetic smoke set

`eval/smoke/milestone3_smoke.jsonl` is 30 manually reviewable questions about
`tests/fixtures/annual_report_excerpt.pdf` only. It is not FinanceBench and it has no scores until
a configured LLM provider answers each item. With `FINAUDIT_LLM_PROVIDER=none`, the API returns
503 `llm_unavailable` and no accuracy, citation, latency, or cost metric is computed.

FinanceBench data and PDFs are **not** redistributed here. The repository publishes no licence for
them, so they are downloaded into `eval/data/`, which is git-ignored.

## Benchmark composition (71 items)

| Category | n | Source | Gold evidence |
|---|---|---|---|
| factual | 31 | FinanceBench (human-annotated answers + evidence pages) | FinanceBench pages |
| numerical | 23 | FinanceBench (`question_reasoning` contains "Numerical", or a bare-number gold answer) | FinanceBench pages |
| multi_page (tag) | 9 | FinanceBench items whose gold evidence spans ≥ 2 pages | FinanceBench pages |
| cross_document | 6 | Constructed: comparisons whose components are two FinanceBench human gold answers (`constructed.jsonl`, `derived_from`) | Union of both items' pages |
| unanswerable | 8 | Constructed. 5 are verified by executed term-absence checks on the filings' text layer; 3 by period logic (the corpus contains no filing for that period) | none |
| chart | 3 | Constructed on the synthetic fixture; true bar values are defined in `tests/fixtures/generate_fixtures.py` | fixture page 3 |

- **Selection:** every FinanceBench open-source question on the 13 filings with ≥ 3 questions, plus
  3M FY2018. 3M then has three filings from different periods. No question was filtered on difficulty
  or system output.
- **Evidence verification:** each FinanceBench evidence page was checked against the PDF's text layer.
  All 66 of 66 entries were found on the stated page (≥ 80% token coverage; see
  `results/benchmark_report.md`).
- **Constructed items** were written and verified by the development agent (Claude) using the
  executed checks above. They have not been reviewed by a human analyst; review them before treating
  the results as final.

## Metrics

- **Retrieval** (page-level, as FinanceBench annotates pages):
  - Recall@5/@10 over gold (document, page) pairs, Hit@k, MRR and nDCG@10.
  - Gains are de-duplicated per gold page, so several chunks from one page count once.
  - 95% bootstrap CIs (2,000 resamples).
  - Paired sign-flip permutation tests (10,000 permutations) between configurations, on identical
    items, index and hardware.
  - Two settings: **filtered** (the gold document(s) are given, measuring ranking) and **open** (all 14
    documents, measuring cross-document retrieval).
- **QA:**
  - Numerical accuracy: |value| within 1% of gold. FinanceBench states outflows as positive amounts.
  - Token F1 for text answers. It is reported, but free-text correctness needs human or LLM-judge
    review; per-item outputs are written for that.
  - Page-level citation precision and recall.
  - Abstention precision/recall/F1 (unanswerable = positive) and false-abstain rate.
  - Latency p50/p95, tokens, and cost (only when prices are configured).

## Results (retrieval, chunker `layout-v2`, 63 items with gold evidence)

Full tables, CIs and per-tag results are in `results/retrieval_report.md`; per-query rankings are in
`results/raw/` (git-ignored). Setup:
- Corpus: 14 documents, 10,081 layout chunks and 8,029 flat chunks. Parsed with PyMuPDF (Docling
  models unreachable).
- Embedder: all-MiniLM-L6-v2 ONNX. WordLlama was run as an ablation.
- Hardware: one shared 4-vCPU container, embedded Qdrant.

Recall@10 [95% CI] / MRR:

| Config | Gold doc given: Recall@10 | MRR | Open corpus: Recall@10 | MRR |
|---|---|---|---|---|
| B1 BM25 · flat | 0.413 [0.302, 0.532] | 0.275 | 0.349 [0.238, 0.460] | 0.184 |
| B2 dense · flat | **0.571** [0.452, 0.690] | 0.323 | **0.500** [0.381, 0.619] | 0.267 |
| B3 BM25 · layout | 0.405 [0.294, 0.524] | 0.275 | 0.294 [0.183, 0.405] | 0.185 |
| B4 hybrid (RRF) · layout | 0.516 [0.397, 0.635] | 0.287 | 0.444 [0.325, 0.563] | 0.224 |
| dense · layout (ablation; QA default) | 0.563 [0.437, 0.683] | **0.337** | 0.444 [0.325, 0.571] | 0.266 |

What the evidence supports, and what it does not:
1. **Layout-aware chunking alone did not improve retrieval** (B3 vs B1: Δ Recall@10 −0.008 with the
   gold document given; −0.056 in the open corpus, p = 0.22). Every gold page is covered by at least
   one chunk in both chunk sets (80/80), so misses are ranking failures, not parsing gaps. The benefit
   of layout chunks in this milestone is *evidence quality*: units, period columns, row labels and
   exact block bboxes for citations and calculations. It is not recall.
2. **Dense retrieval accounts for the gains.** B2 vs B1 Recall@10 is +0.159 (uncorrected p = 0.029)
   with the gold document given and +0.151 (p = 0.057) in the open corpus. B4 vs B3 open-corpus
   Recall@10 is +0.151 (p = 0.0023).
3. **Hybrid RRF fusion did not beat dense alone** (B4 vs B2: −0.056 Recall@10, p = 0.51). The QA
   default is therefore *dense over layout chunks*. It has the best point estimates among layout
   configurations, particularly on numerical items (Recall@10 0.435 vs 0.261 for B4, n = 23). It falls
   back to BM25 if the embedder is unavailable.
4. **None of these differences survive Holm–Bonferroni correction** over the 30 reported comparisons
   (smallest adjusted p = 0.069). With 63 queries they are directional evidence, not established
   improvements.
5. **Weak spots:**
   - Numerical questions: Recall@10 0.15 (BM25) to 0.44 (dense · layout).
   - Multi-page evidence: 0.11 for every configuration.
   - The static WordLlama embedder is worse than MiniLM everywhere (e.g. B2 0.381 vs 0.571).
6. **Reranking** was not evaluated (no reranker weights reachable), so no reranking claim is made.
7. **Latency** is in-process with embedded Qdrant, so treat it as order-of-magnitude only: it varied
   up to ~1.7× between two runs of identical code (B4 p50 168 vs 288 ms). Operating cost of retrieval
   is local CPU only, with no API calls.

**Chunker change log.** `layout-v1` (results archived in `results/archive/layout-v1/`) let PyMuPDF's
row-0 header flag turn data rows into column labels. In one real Boeing table, values were serialised
under other values ("Defense, Space & Security: $25,867 = 23,162"). The defect was found by
inspecting `sample_retrievals.md`, not by tuning on the metrics. `layout-v2` accepts only header rows
without non-year numbers, and recovers periods from the text above a table only on an exact count
match. Retrieval metrics are essentially unchanged by the fix (B4 Recall@10 0.548 → 0.516, within CI);
the fix is a correctness fix.

## QA results

**Not run.** No LLM credentials were available in this environment, so answer correctness, numerical
accuracy, citation precision/recall, abstention quality, LLM latency and token cost are **not
measured**, and no placeholder figures are given. To run:

```bash
FINAUDIT_LLM_PROVIDER=anthropic FINAUDIT_LLM_MODEL=claude-opus-5-5 FINAUDIT_LLM_API_KEY=... \
FINAUDIT_LLM_PRICE_INPUT_PER_MTOK=4 FINAUDIT_LLM_PRICE_OUTPUT_PER_MTOK=20 \
PYTHONPATH=. python eval/run_qa_eval.py
```

Free-text answers then need human or LLM-judge review of `results/raw/qa_runs.jsonl`. Token F1 alone
is not a correctness measure.

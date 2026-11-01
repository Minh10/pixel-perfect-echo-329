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

## Results

See `results/retrieval_report.md` for the full tables. The QA evaluation has **not been run** in this
environment because no LLM credentials were available. It is not reported, and no placeholder numbers
exist.

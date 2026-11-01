# Retrieval reproducibility report

**Question:** do the committed Milestone 3 retrieval results (`services/api/eval/results/retrieval_results.json`, chunker `layout-v2`) reproduce when everything is rebuilt from scratch with PR #2's code?

**Answer: yes, exactly, for every quality metric. Latency does not reproduce as a number.**

## Procedure (identical conditions)

| Step | Command (from `services/api`, PR #2 head `ed9e7e2`) | Result |
|---|---|---|
| 1. Download inputs | `python eval/fetch_financebench.py` | 15 files, **0 checksum failures** against `financebench.lock.json` (FinanceBench commit `cc39aeb`) |
| 2. Fresh ingestion into a new data dir | `python eval/ingest_corpus.py --data-dir /home/user/audit-data/corpus --workers 4` | 14 documents, 2,321 pages; per-document sha256 sequence identical to the original corpus |
| 3. Benchmark build | `python eval/build_benchmark.py --corpus … --out /home/user/audit-data/benchmark.jsonl` | **byte-identical** to the original (`sha256 2d9d976c…`); `benchmark_report.md` unchanged (66/66 evidence pages verified) |
| 4. Index + evaluate | `python eval/run_retrieval_eval.py --corpus … --reindex --embedders onnx wordllama` | 20 configuration × setting results, 30 paired comparisons |

| Item | Value |
|---|---|
| Parser | PyMuPDF. Docling's weights are unreachable here, so the reproduction uses the same parser as the original |
| Embedders | all-MiniLM-L6-v2 ONNX (`onnx-all-MiniLM-L6-v2-4f148ba8ae9c`, checksum-pinned) and WordLlama 256-d |
| Vector store | Embedded Qdrant |
| Hardware | One shared 4-vCPU container; the original run used the same container type |

## Results

| Comparison | Outcome |
|---|---|
| Configuration/setting keys | 20 / 20 identical |
| Per-query metric series (Recall@5/10, Hit@5/10, MRR, nDCG@10 × 20) | **120 / 120 identical**, max \|Δ mean\| = 0.000000 |
| Bootstrap 95% CIs | all identical (seeded resampling) |
| Paired permutation p-values (30) and Holm-adjusted p-values | all identical |
| Layout chunks (id + content) | 10,050 / 10,050 identical |
| Flat chunks (id + content) | 8,029 / 8,029 identical |

The headline table therefore stands as committed. Recall@10, 63 items:

| Config | Gold doc given | Open corpus |
|---|---|---|
| B1 BM25 · flat | 0.413 | 0.349 |
| B2 dense · flat | 0.571 | 0.500 |
| B3 BM25 · layout | 0.405 | 0.294 |
| B4 hybrid · layout | 0.516 | 0.444 |
| dense · layout (QA default) | 0.563 | 0.444 |

The committed scientific conclusions are reproduced, not merely re-asserted:
- layout chunking alone gives no recall gain (B3 ≈ B1);
- dense retrieval accounts for the gains;
- hybrid does not beat dense;
- no difference survives Holm–Bonferroni (smallest adjusted p = 0.069).

## Latency (not reproducible as a number)

p50 latency (ms), original run vs reproduction, same code and container type:

| Configuration | Original | Reproduction |
|---|---|---|
| B1 · filtered | 40.7 | 39.0 |
| B2 onnx · filtered | 113.6 | 106.3 |
| B4 onnx · filtered | 288.1 | 155.2 |
| dense-layout onnx · filtered | 235.2 | 128.7 |
| dense-layout onnx · open | 70.1 | 38.9 |
| B4 wordllama · filtered | 276.8 | 154.5 |

Embedded Qdrant on a shared container gives up to ~2× variation between runs. Latency should be reported only as an order of magnitude (tens to low hundreds of ms per query on CPU), and measured on target hardware with Qdrant server mode before any SLA is set.

## Discrepancies found

1. **Documentation:** `services/api/eval/README.md` states "10,081 layout chunks"; both the original and the reproduced corpora contain **10,050**. 10,081 is a stale figure from the `layout-v1` chunker. No metric is affected (AUD-12).
2. **Parser coverage:** Docling was not exercised in either run, so these results characterise the PyMuPDF path only.

## Artifacts

- `artifacts/retrieval_report_committed.md`: the committed report.
- `artifacts/retrieval_report_reproduction.md`: the regenerated report. It differs only in latency columns.

# Retrieval evaluation

Items with gold evidence: 63 · embedders: {'onnx': 'onnx-all-MiniLM-L6-v2-4f148ba8ae9c'} · RRF k=60 · candidate depth 50 · Python 3.13.18

Page-level relevance (see `app/evaluation/metrics.py`). 95% CIs: percentile bootstrap over queries (2,000 resamples).

## Gold document(s) given (ranking quality)

| Config | Method | Chunks | Embedder | Recall@5 | Recall@10 | Hit@5 | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| B1 | bm25 | flat | — | 0.365 [0.254, 0.484] | 0.413 [0.302, 0.532] | 0.381 | 0.275 [0.183, 0.368] | 0.306 | 52.5 | 97.0 |
| B2 | dense | flat | onnx | 0.397 [0.278, 0.516] | 0.571 [0.452, 0.690] | 0.413 | 0.323 [0.229, 0.426] | 0.377 | 132.3 | 204.3 |
| B3 | bm25 | layout | — | 0.373 [0.262, 0.484] | 0.421 [0.310, 0.540] | 0.397 | 0.274 [0.180, 0.372] | 0.302 | 49.1 | 92.6 |
| B4 | hybrid | layout | onnx | 0.421 [0.310, 0.540] | 0.540 [0.421, 0.651] | 0.444 | 0.288 [0.204, 0.376] | 0.346 | 189.5 | 262.2 |
| A-dense-layout | dense | layout | onnx | 0.460 [0.341, 0.587] | 0.571 [0.444, 0.690] | 0.476 | 0.334 [0.235, 0.434] | 0.387 | 148.0 | 178.4 |
| A-hybrid-flat | hybrid | flat | onnx | 0.381 [0.270, 0.508] | 0.484 [0.365, 0.611] | 0.397 | 0.273 [0.186, 0.362] | 0.321 | 157.9 | 225.5 |

## Open corpus (cross-document)

| Config | Method | Chunks | Embedder | Recall@5 | Recall@10 | Hit@5 | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| B1 | bm25 | flat | — | 0.254 [0.159, 0.365] | 0.349 [0.238, 0.460] | 0.254 | 0.193 [0.112, 0.279] | 0.230 | 59.5 | 113.1 |
| B2 | dense | flat | onnx | 0.333 [0.222, 0.452] | 0.500 [0.381, 0.619] | 0.349 | 0.267 [0.177, 0.363] | 0.315 | 46.9 | 63.0 |
| B3 | bm25 | layout | — | 0.214 [0.119, 0.317] | 0.294 [0.183, 0.397] | 0.222 | 0.183 [0.102, 0.271] | 0.204 | 74.0 | 131.0 |
| B4 | hybrid | layout | onnx | 0.349 [0.238, 0.460] | 0.452 [0.333, 0.571] | 0.381 | 0.230 [0.147, 0.318] | 0.280 | 122.3 | 157.0 |
| A-dense-layout | dense | layout | onnx | 0.349 [0.238, 0.468] | 0.452 [0.333, 0.579] | 0.365 | 0.263 [0.173, 0.362] | 0.305 | 46.8 | 64.5 |
| A-hybrid-flat | hybrid | flat | onnx | 0.310 [0.198, 0.421] | 0.389 [0.278, 0.508] | 0.333 | 0.216 [0.133, 0.302] | 0.256 | 118.9 | 170.6 |

## Paired comparisons (difference = second − first; sign-flip permutation test, 10,000 permutations)

`p` is uncorrected; `p (Holm)` is Holm–Bonferroni-adjusted over all 30 comparisons in this table.

| Comparison | Setting | Metric | Δ mean | 95% CI | p | p (Holm) | n |
|---|---|---|---|---|---|---|---|
| B2 vs B1 | filtered | recall@5 | +0.032 | [-0.103, +0.167] | 0.7415 | 1.0000 | 63 |
| B2 vs B1 | filtered | recall@10 | +0.159 | [+0.024, +0.294] | 0.0289 | 0.7513 | 63 |
| B2 vs B1 | filtered | mrr | +0.048 | [-0.073, +0.164] | 0.4248 | 1.0000 | 63 |
| B3 vs B1 | filtered | recall@5 | +0.008 | [-0.056, +0.071] | 1.0000 | 1.0000 | 63 |
| B3 vs B1 | filtered | recall@10 | +0.008 | [-0.048, +0.063] | 1.0000 | 1.0000 | 63 |
| B3 vs B1 | filtered | mrr | -0.001 | [-0.053, +0.055] | 0.9824 | 1.0000 | 63 |
| B4 vs B1 | filtered | recall@5 | +0.056 | [-0.048, +0.159] | 0.3879 | 1.0000 | 63 |
| B4 vs B1 | filtered | recall@10 | +0.127 | [+0.032, +0.222] | 0.0214 | 0.5991 | 63 |
| B4 vs B1 | filtered | mrr | +0.013 | [-0.056, +0.084] | 0.7231 | 1.0000 | 63 |
| B4 vs B3 | filtered | recall@5 | +0.048 | [-0.048, +0.143] | 0.5142 | 1.0000 | 63 |
| B4 vs B3 | filtered | recall@10 | +0.119 | [+0.032, +0.214] | 0.0239 | 0.6452 | 63 |
| B4 vs B3 | filtered | mrr | +0.014 | [-0.052, +0.078] | 0.6759 | 1.0000 | 63 |
| B4 vs B2 | filtered | recall@5 | +0.024 | [-0.087, +0.135] | 0.7921 | 1.0000 | 63 |
| B4 vs B2 | filtered | recall@10 | -0.032 | [-0.167, +0.103] | 0.7437 | 1.0000 | 63 |
| B4 vs B2 | filtered | mrr | -0.035 | [-0.133, +0.059] | 0.4887 | 1.0000 | 63 |
| B2 vs B1 | open | recall@5 | +0.079 | [-0.071, +0.222] | 0.3444 | 1.0000 | 63 |
| B2 vs B1 | open | recall@10 | +0.151 | [+0.008, +0.294] | 0.0573 | 1.0000 | 63 |
| B2 vs B1 | open | mrr | +0.074 | [-0.024, +0.173] | 0.1534 | 1.0000 | 63 |
| B3 vs B1 | open | recall@5 | -0.040 | [-0.119, +0.032] | 0.4450 | 1.0000 | 63 |
| B3 vs B1 | open | recall@10 | -0.056 | [-0.135, +0.016] | 0.2166 | 1.0000 | 63 |
| B3 vs B1 | open | mrr | -0.009 | [-0.060, +0.039] | 0.6904 | 1.0000 | 63 |
| B4 vs B1 | open | recall@5 | +0.095 | [+0.008, +0.190] | 0.0837 | 1.0000 | 63 |
| B4 vs B1 | open | recall@10 | +0.103 | [+0.008, +0.206] | 0.0822 | 1.0000 | 63 |
| B4 vs B1 | open | mrr | +0.038 | [-0.030, +0.108] | 0.3001 | 1.0000 | 63 |
| B4 vs B3 | open | recall@5 | +0.135 | [+0.048, +0.230] | 0.0079 | 0.2291 | 63 |
| B4 vs B3 | open | recall@10 | +0.159 | [+0.063, +0.262] | 0.0039 | 0.1170 | 63 |
| B4 vs B3 | open | mrr | +0.047 | [-0.008, +0.107] | 0.1122 | 1.0000 | 63 |
| B4 vs B2 | open | recall@5 | +0.016 | [-0.111, +0.151] | 0.9030 | 1.0000 | 63 |
| B4 vs B2 | open | recall@10 | -0.048 | [-0.183, +0.087] | 0.5634 | 1.0000 | 63 |
| B4 vs B2 | open | mrr | -0.037 | [-0.127, +0.050] | 0.4412 | 1.0000 | 63 |

## Recall@10 by question tag (filtered setting)

| Config | Tag | n | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|---|
| B1 (bm25) | chart | 3 | 1.000 | 1.000 | 0.833 |
| B1 (bm25) | cross_document | 6 | 0.250 | 0.333 | 0.222 |
| B1 (bm25) | factual | 31 | 0.484 | 0.565 | 0.385 |
| B1 (bm25) | multi_page | 9 | 0.056 | 0.111 | 0.074 |
| B1 (bm25) | numerical | 23 | 0.152 | 0.152 | 0.067 |
| B2 (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| B2 (onnx) | cross_document | 6 | 0.167 | 0.500 | 0.292 |
| B2 (onnx) | factual | 31 | 0.516 | 0.694 | 0.420 |
| B2 (onnx) | multi_page | 9 | 0.000 | 0.111 | 0.022 |
| B2 (onnx) | numerical | 23 | 0.217 | 0.370 | 0.134 |
| B3 (bm25) | chart | 3 | 1.000 | 1.000 | 0.778 |
| B3 (bm25) | cross_document | 6 | 0.250 | 0.250 | 0.200 |
| B3 (bm25) | factual | 31 | 0.500 | 0.597 | 0.399 |
| B3 (bm25) | multi_page | 9 | 0.111 | 0.111 | 0.093 |
| B3 (bm25) | numerical | 23 | 0.152 | 0.152 | 0.058 |
| B4 (onnx) | chart | 3 | 1.000 | 1.000 | 0.778 |
| B4 (onnx) | cross_document | 6 | 0.083 | 0.167 | 0.083 |
| B4 (onnx) | factual | 31 | 0.565 | 0.742 | 0.411 |
| B4 (onnx) | multi_page | 9 | 0.111 | 0.222 | 0.063 |
| B4 (onnx) | numerical | 23 | 0.239 | 0.304 | 0.111 |
| A-dense-layout (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| A-dense-layout (onnx) | cross_document | 6 | 0.167 | 0.250 | 0.140 |
| A-dense-layout (onnx) | factual | 31 | 0.613 | 0.677 | 0.469 |
| A-dense-layout (onnx) | multi_page | 9 | 0.111 | 0.167 | 0.068 |
| A-dense-layout (onnx) | numerical | 23 | 0.261 | 0.457 | 0.137 |
| A-hybrid-flat (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| A-hybrid-flat (onnx) | cross_document | 6 | 0.167 | 0.250 | 0.167 |
| A-hybrid-flat (onnx) | factual | 31 | 0.516 | 0.677 | 0.387 |
| A-hybrid-flat (onnx) | multi_page | 9 | 0.000 | 0.000 | 0.000 |
| A-hybrid-flat (onnx) | numerical | 23 | 0.174 | 0.217 | 0.073 |

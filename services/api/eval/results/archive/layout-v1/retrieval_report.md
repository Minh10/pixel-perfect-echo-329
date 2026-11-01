# Retrieval evaluation

Items with gold evidence: 63 · embedders: {'onnx': 'onnx-all-MiniLM-L6-v2-4f148ba8ae9c', 'wordllama': 'wordllama-l2supercat-256'} · RRF k=60 · candidate depth 50 · Python 3.13.18

Page-level relevance (see `app/evaluation/metrics.py`). 95% CIs: percentile bootstrap over queries (2,000 resamples).

## Gold document(s) given (ranking quality)

| Config | Method | Chunks | Embedder | Recall@5 | Recall@10 | Hit@5 | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| B1 | bm25 | flat | — | 0.365 [0.254, 0.484] | 0.413 [0.302, 0.532] | 0.381 | 0.275 [0.181, 0.371] | 0.303 | 44.5 | 64.5 |
| B2 | dense | flat | onnx | 0.397 [0.278, 0.516] | 0.571 [0.452, 0.690] | 0.413 | 0.323 [0.229, 0.426] | 0.377 | 103.9 | 149.7 |
| B3 | bm25 | layout | — | 0.373 [0.262, 0.484] | 0.405 [0.294, 0.524] | 0.397 | 0.282 [0.186, 0.382] | 0.303 | 47.0 | 66.7 |
| B4 | hybrid | layout | onnx | 0.389 [0.270, 0.516] | 0.548 [0.429, 0.667] | 0.397 | 0.293 [0.204, 0.386] | 0.354 | 168.1 | 233.1 |
| A-dense-layout | dense | layout | onnx | 0.460 [0.341, 0.587] | 0.563 [0.437, 0.683] | 0.476 | 0.351 [0.255, 0.452] | 0.399 | 128.4 | 188.3 |
| A-hybrid-flat | hybrid | flat | onnx | 0.381 [0.270, 0.508] | 0.476 [0.357, 0.603] | 0.397 | 0.272 [0.186, 0.363] | 0.319 | 140.6 | 166.1 |
| B2 | dense | flat | wordllama | 0.302 [0.190, 0.413] | 0.381 [0.270, 0.508] | 0.302 | 0.188 [0.111, 0.270] | 0.234 | 83.9 | 112.3 |
| B4 | hybrid | layout | wordllama | 0.333 [0.222, 0.444] | 0.458 [0.341, 0.571] | 0.349 | 0.251 [0.165, 0.346] | 0.297 | 156.7 | 186.4 |
| A-dense-layout | dense | layout | wordllama | 0.315 [0.206, 0.429] | 0.384 [0.275, 0.492] | 0.333 | 0.214 [0.137, 0.301] | 0.248 | 105.3 | 135.6 |
| A-hybrid-flat | hybrid | flat | wordllama | 0.405 [0.294, 0.524] | 0.452 [0.333, 0.571] | 0.413 | 0.292 [0.199, 0.386] | 0.330 | 129.1 | 167.7 |

## Open corpus (cross-document)

| Config | Method | Chunks | Embedder | Recall@5 | Recall@10 | Hit@5 | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| B1 | bm25 | flat | — | 0.238 [0.143, 0.333] | 0.349 [0.238, 0.460] | 0.238 | 0.184 [0.107, 0.267] | 0.223 | 55.4 | 93.2 |
| B2 | dense | flat | onnx | 0.333 [0.222, 0.452] | 0.500 [0.381, 0.619] | 0.349 | 0.267 [0.177, 0.363] | 0.315 | 23.3 | 66.4 |
| B3 | bm25 | layout | — | 0.214 [0.119, 0.317] | 0.294 [0.183, 0.397] | 0.222 | 0.185 [0.103, 0.276] | 0.205 | 56.1 | 109.3 |
| B4 | hybrid | layout | onnx | 0.349 [0.238, 0.468] | 0.444 [0.325, 0.563] | 0.365 | 0.230 [0.149, 0.319] | 0.280 | 185.8 | 246.3 |
| A-dense-layout | dense | layout | onnx | 0.349 [0.238, 0.468] | 0.444 [0.325, 0.571] | 0.365 | 0.279 [0.187, 0.382] | 0.316 | 37.8 | 62.4 |
| A-hybrid-flat | hybrid | flat | onnx | 0.302 [0.190, 0.413] | 0.389 [0.278, 0.508] | 0.317 | 0.216 [0.133, 0.302] | 0.256 | 95.9 | 149.7 |
| B2 | dense | flat | wordllama | 0.190 [0.095, 0.286] | 0.222 [0.127, 0.333] | 0.190 | 0.114 [0.053, 0.185] | 0.140 | 5.4 | 7.0 |
| B4 | hybrid | layout | wordllama | 0.222 [0.127, 0.317] | 0.347 [0.233, 0.460] | 0.222 | 0.177 [0.100, 0.262] | 0.216 | 60.3 | 104.2 |
| A-dense-layout | dense | layout | wordllama | 0.204 [0.111, 0.304] | 0.257 [0.161, 0.362] | 0.222 | 0.155 [0.086, 0.236] | 0.174 | 7.7 | 9.6 |
| A-hybrid-flat | hybrid | flat | wordllama | 0.230 [0.135, 0.333] | 0.302 [0.190, 0.413] | 0.238 | 0.192 [0.109, 0.280] | 0.215 | 70.7 | 108.6 |

## Paired comparisons (difference = second − first; sign-flip permutation test, 10,000 permutations)

`p` is uncorrected; `p (Holm)` is Holm–Bonferroni-adjusted over all 30 comparisons in this table.

| Comparison | Setting | Metric | Δ mean | 95% CI | p | p (Holm) | n |
|---|---|---|---|---|---|---|---|
| B2 vs B1 | filtered | recall@5 | +0.032 | [-0.103, +0.167] | 0.7415 | 1.0000 | 63 |
| B2 vs B1 | filtered | recall@10 | +0.159 | [+0.024, +0.294] | 0.0289 | 0.7513 | 63 |
| B2 vs B1 | filtered | mrr | +0.048 | [-0.076, +0.164] | 0.4389 | 1.0000 | 63 |
| B3 vs B1 | filtered | recall@5 | +0.008 | [-0.056, +0.071] | 1.0000 | 1.0000 | 63 |
| B3 vs B1 | filtered | recall@10 | -0.008 | [-0.056, +0.040] | 1.0000 | 1.0000 | 63 |
| B3 vs B1 | filtered | mrr | +0.008 | [-0.046, +0.066] | 0.7898 | 1.0000 | 63 |
| B4 vs B1 | filtered | recall@5 | +0.024 | [-0.079, +0.135] | 0.7651 | 1.0000 | 63 |
| B4 vs B1 | filtered | recall@10 | +0.135 | [+0.040, +0.238] | 0.0186 | 0.5021 | 63 |
| B4 vs B1 | filtered | mrr | +0.018 | [-0.062, +0.103] | 0.6560 | 1.0000 | 63 |
| B4 vs B3 | filtered | recall@5 | +0.016 | [-0.071, +0.111] | 0.8602 | 1.0000 | 63 |
| B4 vs B3 | filtered | recall@10 | +0.143 | [+0.048, +0.246] | 0.0141 | 0.3948 | 63 |
| B4 vs B3 | filtered | mrr | +0.011 | [-0.065, +0.081] | 0.7775 | 1.0000 | 63 |
| B4 vs B2 | filtered | recall@5 | -0.008 | [-0.119, +0.111] | 1.0000 | 1.0000 | 63 |
| B4 vs B2 | filtered | recall@10 | -0.024 | [-0.151, +0.103] | 0.8174 | 1.0000 | 63 |
| B4 vs B2 | filtered | mrr | -0.030 | [-0.131, +0.068] | 0.5659 | 1.0000 | 63 |
| B2 vs B1 | open | recall@5 | +0.095 | [-0.048, +0.238] | 0.2352 | 1.0000 | 63 |
| B2 vs B1 | open | recall@10 | +0.151 | [+0.008, +0.294] | 0.0573 | 1.0000 | 63 |
| B2 vs B1 | open | mrr | +0.083 | [-0.020, +0.184] | 0.1161 | 1.0000 | 63 |
| B3 vs B1 | open | recall@5 | -0.024 | [-0.111, +0.063] | 0.7213 | 1.0000 | 63 |
| B3 vs B1 | open | recall@10 | -0.056 | [-0.135, +0.016] | 0.2166 | 1.0000 | 63 |
| B3 vs B1 | open | mrr | +0.001 | [-0.051, +0.055] | 0.9792 | 1.0000 | 63 |
| B4 vs B1 | open | recall@5 | +0.111 | [+0.008, +0.214] | 0.0506 | 1.0000 | 63 |
| B4 vs B1 | open | recall@10 | +0.095 | [+0.008, +0.190] | 0.0734 | 1.0000 | 63 |
| B4 vs B1 | open | mrr | +0.046 | [-0.023, +0.116] | 0.2082 | 1.0000 | 63 |
| B4 vs B3 | open | recall@5 | +0.135 | [+0.056, +0.222] | 0.0037 | 0.1073 | 63 |
| B4 vs B3 | open | recall@10 | +0.151 | [+0.063, +0.246] | 0.0023 | 0.0690 | 63 |
| B4 vs B3 | open | mrr | +0.045 | [-0.011, +0.106] | 0.1268 | 1.0000 | 63 |
| B4 vs B2 | open | recall@5 | +0.016 | [-0.103, +0.143] | 0.9032 | 1.0000 | 63 |
| B4 vs B2 | open | recall@10 | -0.056 | [-0.190, +0.087] | 0.5066 | 1.0000 | 63 |
| B4 vs B2 | open | mrr | -0.037 | [-0.123, +0.046] | 0.4238 | 1.0000 | 63 |

## Recall@10 by question tag (filtered setting)

| Config | Tag | n | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|---|
| B1 (bm25) | chart | 3 | 1.000 | 1.000 | 0.833 |
| B1 (bm25) | cross_document | 6 | 0.250 | 0.333 | 0.222 |
| B1 (bm25) | factual | 31 | 0.484 | 0.565 | 0.369 |
| B1 (bm25) | multi_page | 9 | 0.056 | 0.111 | 0.130 |
| B1 (bm25) | numerical | 23 | 0.152 | 0.152 | 0.088 |
| B2 (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| B2 (onnx) | cross_document | 6 | 0.167 | 0.500 | 0.292 |
| B2 (onnx) | factual | 31 | 0.516 | 0.694 | 0.420 |
| B2 (onnx) | multi_page | 9 | 0.000 | 0.111 | 0.022 |
| B2 (onnx) | numerical | 23 | 0.217 | 0.370 | 0.134 |
| B3 (bm25) | chart | 3 | 1.000 | 1.000 | 0.778 |
| B3 (bm25) | cross_document | 6 | 0.250 | 0.250 | 0.208 |
| B3 (bm25) | factual | 31 | 0.500 | 0.565 | 0.393 |
| B3 (bm25) | multi_page | 9 | 0.111 | 0.111 | 0.148 |
| B3 (bm25) | numerical | 23 | 0.152 | 0.152 | 0.088 |
| B4 (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| B4 (onnx) | cross_document | 6 | 0.000 | 0.250 | 0.056 |
| B4 (onnx) | factual | 31 | 0.532 | 0.742 | 0.415 |
| B4 (onnx) | multi_page | 9 | 0.056 | 0.111 | 0.022 |
| B4 (onnx) | numerical | 23 | 0.217 | 0.304 | 0.120 |
| A-dense-layout (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| A-dense-layout (onnx) | cross_document | 6 | 0.167 | 0.250 | 0.137 |
| A-dense-layout (onnx) | factual | 31 | 0.613 | 0.677 | 0.480 |
| A-dense-layout (onnx) | multi_page | 9 | 0.111 | 0.111 | 0.056 |
| A-dense-layout (onnx) | numerical | 23 | 0.261 | 0.435 | 0.170 |
| A-hybrid-flat (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| A-hybrid-flat (onnx) | cross_document | 6 | 0.167 | 0.250 | 0.167 |
| A-hybrid-flat (onnx) | factual | 31 | 0.516 | 0.677 | 0.386 |
| A-hybrid-flat (onnx) | multi_page | 9 | 0.000 | 0.056 | 0.011 |
| A-hybrid-flat (onnx) | numerical | 23 | 0.174 | 0.196 | 0.073 |
| B2 (wordllama) | chart | 3 | 1.000 | 1.000 | 1.000 |
| B2 (wordllama) | cross_document | 6 | 0.000 | 0.000 | 0.000 |
| B2 (wordllama) | factual | 31 | 0.387 | 0.548 | 0.229 |
| B2 (wordllama) | multi_page | 9 | 0.000 | 0.000 | 0.000 |
| B2 (wordllama) | numerical | 23 | 0.174 | 0.174 | 0.075 |
| B4 (wordllama) | chart | 3 | 1.000 | 1.000 | 0.833 |
| B4 (wordllama) | cross_document | 6 | 0.083 | 0.250 | 0.100 |
| B4 (wordllama) | factual | 31 | 0.484 | 0.597 | 0.372 |
| B4 (wordllama) | multi_page | 9 | 0.056 | 0.148 | 0.058 |
| B4 (wordllama) | numerical | 23 | 0.109 | 0.254 | 0.052 |
| A-dense-layout (wordllama) | chart | 3 | 1.000 | 1.000 | 1.000 |
| A-dense-layout (wordllama) | cross_document | 6 | 0.000 | 0.167 | 0.033 |
| A-dense-layout (wordllama) | factual | 31 | 0.419 | 0.484 | 0.243 |
| A-dense-layout (wordllama) | multi_page | 9 | 0.093 | 0.130 | 0.167 |
| A-dense-layout (wordllama) | numerical | 23 | 0.167 | 0.225 | 0.120 |
| A-hybrid-flat (wordllama) | chart | 3 | 1.000 | 1.000 | 0.833 |
| A-hybrid-flat (wordllama) | cross_document | 6 | 0.250 | 0.333 | 0.200 |
| A-hybrid-flat (wordllama) | factual | 31 | 0.581 | 0.645 | 0.431 |
| A-hybrid-flat (wordllama) | multi_page | 9 | 0.000 | 0.056 | 0.016 |
| A-hybrid-flat (wordllama) | numerical | 23 | 0.130 | 0.152 | 0.057 |

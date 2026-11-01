# Retrieval evaluation

Items with gold evidence: 63 · embedders: {'onnx': 'onnx-all-MiniLM-L6-v2-4f148ba8ae9c', 'wordllama': 'wordllama-l2supercat-256'} · RRF k=60 · candidate depth 50 · Python 3.13.18

Page-level relevance (see `app/evaluation/metrics.py`). 95% CIs: percentile bootstrap over queries (2,000 resamples).

## Gold document(s) given (ranking quality)

| Config | Method | Chunks | Embedder | Recall@5 | Recall@10 | Hit@5 | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| B1 | bm25 | flat | — | 0.365 [0.254, 0.484] | 0.413 [0.302, 0.532] | 0.381 | 0.275 [0.181, 0.371] | 0.303 | 40.7 | 78.6 |
| B2 | dense | flat | onnx | 0.397 [0.278, 0.516] | 0.571 [0.452, 0.690] | 0.413 | 0.323 [0.229, 0.426] | 0.377 | 113.6 | 154.6 |
| B3 | bm25 | layout | — | 0.373 [0.262, 0.484] | 0.405 [0.294, 0.524] | 0.397 | 0.275 [0.178, 0.372] | 0.298 | 45.4 | 85.5 |
| B4 | hybrid | layout | onnx | 0.389 [0.270, 0.516] | 0.516 [0.397, 0.635] | 0.397 | 0.287 [0.199, 0.382] | 0.342 | 288.1 | 353.7 |
| A-dense-layout | dense | layout | onnx | 0.460 [0.341, 0.587] | 0.563 [0.437, 0.683] | 0.476 | 0.337 [0.237, 0.436] | 0.388 | 235.2 | 315.4 |
| A-hybrid-flat | hybrid | flat | onnx | 0.381 [0.270, 0.508] | 0.476 [0.357, 0.603] | 0.397 | 0.272 [0.186, 0.363] | 0.319 | 149.3 | 184.4 |
| B2 | dense | flat | wordllama | 0.302 [0.190, 0.413] | 0.381 [0.270, 0.508] | 0.302 | 0.188 [0.111, 0.270] | 0.234 | 90.8 | 118.7 |
| B4 | hybrid | layout | wordllama | 0.333 [0.222, 0.444] | 0.474 [0.354, 0.587] | 0.349 | 0.254 [0.168, 0.347] | 0.302 | 276.8 | 319.3 |
| A-dense-layout | dense | layout | wordllama | 0.307 [0.201, 0.418] | 0.384 [0.275, 0.492] | 0.333 | 0.216 [0.139, 0.303] | 0.249 | 226.1 | 307.5 |
| A-hybrid-flat | hybrid | flat | wordllama | 0.405 [0.294, 0.524] | 0.452 [0.333, 0.571] | 0.413 | 0.292 [0.199, 0.386] | 0.330 | 150.1 | 193.3 |

## Open corpus (cross-document)

| Config | Method | Chunks | Embedder | Recall@5 | Recall@10 | Hit@5 | MRR | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| B1 | bm25 | flat | — | 0.238 [0.143, 0.333] | 0.349 [0.238, 0.460] | 0.238 | 0.184 [0.107, 0.267] | 0.223 | 65.2 | 105.0 |
| B2 | dense | flat | onnx | 0.333 [0.222, 0.452] | 0.500 [0.381, 0.619] | 0.349 | 0.267 [0.177, 0.363] | 0.315 | 39.2 | 58.3 |
| B3 | bm25 | layout | — | 0.214 [0.119, 0.317] | 0.294 [0.183, 0.405] | 0.222 | 0.185 [0.103, 0.275] | 0.205 | 63.5 | 103.9 |
| B4 | hybrid | layout | onnx | 0.333 [0.222, 0.452] | 0.444 [0.325, 0.563] | 0.349 | 0.224 [0.142, 0.313] | 0.275 | 110.4 | 155.2 |
| A-dense-layout | dense | layout | onnx | 0.349 [0.238, 0.468] | 0.444 [0.325, 0.571] | 0.365 | 0.266 [0.174, 0.366] | 0.306 | 70.1 | 95.8 |
| A-hybrid-flat | hybrid | flat | onnx | 0.302 [0.190, 0.413] | 0.389 [0.278, 0.508] | 0.317 | 0.216 [0.133, 0.302] | 0.256 | 102.8 | 153.5 |
| B2 | dense | flat | wordllama | 0.190 [0.095, 0.286] | 0.222 [0.127, 0.333] | 0.190 | 0.114 [0.053, 0.185] | 0.140 | 6.6 | 9.7 |
| B4 | hybrid | layout | wordllama | 0.228 [0.127, 0.333] | 0.339 [0.222, 0.450] | 0.238 | 0.176 [0.098, 0.261] | 0.214 | 85.0 | 128.8 |
| A-dense-layout | dense | layout | wordllama | 0.196 [0.106, 0.296] | 0.257 [0.161, 0.365] | 0.206 | 0.152 [0.081, 0.232] | 0.172 | 27.8 | 29.1 |
| A-hybrid-flat | hybrid | flat | wordllama | 0.230 [0.135, 0.333] | 0.302 [0.190, 0.413] | 0.238 | 0.192 [0.109, 0.280] | 0.215 | 79.0 | 116.6 |

## Paired comparisons (difference = second − first; sign-flip permutation test, 10,000 permutations)

`p` is uncorrected; `p (Holm)` is Holm–Bonferroni-adjusted over all 30 comparisons in this table.

| Comparison | Setting | Metric | Δ mean | 95% CI | p | p (Holm) | n |
|---|---|---|---|---|---|---|---|
| B2 vs B1 | filtered | recall@5 | +0.032 | [-0.103, +0.167] | 0.7415 | 1.0000 | 63 |
| B2 vs B1 | filtered | recall@10 | +0.159 | [+0.024, +0.294] | 0.0289 | 0.8091 | 63 |
| B2 vs B1 | filtered | mrr | +0.048 | [-0.076, +0.164] | 0.4389 | 1.0000 | 63 |
| B3 vs B1 | filtered | recall@5 | +0.008 | [-0.056, +0.071] | 1.0000 | 1.0000 | 63 |
| B3 vs B1 | filtered | recall@10 | -0.008 | [-0.056, +0.040] | 1.0000 | 1.0000 | 63 |
| B3 vs B1 | filtered | mrr | +0.000 | [-0.053, +0.051] | 0.9988 | 1.0000 | 63 |
| B4 vs B1 | filtered | recall@5 | +0.024 | [-0.079, +0.135] | 0.7651 | 1.0000 | 63 |
| B4 vs B1 | filtered | recall@10 | +0.103 | [+0.016, +0.198] | 0.0514 | 1.0000 | 63 |
| B4 vs B1 | filtered | mrr | +0.013 | [-0.068, +0.097] | 0.7623 | 1.0000 | 63 |
| B4 vs B3 | filtered | recall@5 | +0.016 | [-0.071, +0.111] | 0.8602 | 1.0000 | 63 |
| B4 vs B3 | filtered | recall@10 | +0.111 | [+0.024, +0.214] | 0.0406 | 1.0000 | 63 |
| B4 vs B3 | filtered | mrr | +0.013 | [-0.061, +0.081] | 0.7290 | 1.0000 | 63 |
| B4 vs B2 | filtered | recall@5 | -0.008 | [-0.119, +0.111] | 1.0000 | 1.0000 | 63 |
| B4 vs B2 | filtered | recall@10 | -0.056 | [-0.190, +0.079] | 0.5089 | 1.0000 | 63 |
| B4 vs B2 | filtered | mrr | -0.036 | [-0.138, +0.062] | 0.4985 | 1.0000 | 63 |
| B2 vs B1 | open | recall@5 | +0.095 | [-0.048, +0.238] | 0.2352 | 1.0000 | 63 |
| B2 vs B1 | open | recall@10 | +0.151 | [+0.008, +0.294] | 0.0573 | 1.0000 | 63 |
| B2 vs B1 | open | mrr | +0.083 | [-0.020, +0.184] | 0.1161 | 1.0000 | 63 |
| B3 vs B1 | open | recall@5 | -0.024 | [-0.111, +0.063] | 0.7213 | 1.0000 | 63 |
| B3 vs B1 | open | recall@10 | -0.056 | [-0.135, +0.008] | 0.2240 | 1.0000 | 63 |
| B3 vs B1 | open | mrr | +0.001 | [-0.052, +0.055] | 0.9784 | 1.0000 | 63 |
| B4 vs B1 | open | recall@5 | +0.095 | [-0.008, +0.198] | 0.0870 | 1.0000 | 63 |
| B4 vs B1 | open | recall@10 | +0.095 | [+0.008, +0.190] | 0.0734 | 1.0000 | 63 |
| B4 vs B1 | open | mrr | +0.040 | [-0.029, +0.110] | 0.2708 | 1.0000 | 63 |
| B4 vs B3 | open | recall@5 | +0.119 | [+0.048, +0.206] | 0.0064 | 0.1856 | 63 |
| B4 vs B3 | open | recall@10 | +0.151 | [+0.071, +0.246] | 0.0023 | 0.0690 | 63 |
| B4 vs B3 | open | mrr | +0.039 | [-0.014, +0.096] | 0.1675 | 1.0000 | 63 |
| B4 vs B2 | open | recall@5 | +0.000 | [-0.127, +0.135] | 1.0000 | 1.0000 | 63 |
| B4 vs B2 | open | recall@10 | -0.056 | [-0.190, +0.087] | 0.5066 | 1.0000 | 63 |
| B4 vs B2 | open | mrr | -0.043 | [-0.133, +0.042] | 0.3616 | 1.0000 | 63 |

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
| B3 (bm25) | factual | 31 | 0.500 | 0.565 | 0.377 |
| B3 (bm25) | multi_page | 9 | 0.111 | 0.111 | 0.148 |
| B3 (bm25) | numerical | 23 | 0.152 | 0.152 | 0.088 |
| B4 (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| B4 (onnx) | cross_document | 6 | 0.000 | 0.250 | 0.056 |
| B4 (onnx) | factual | 31 | 0.532 | 0.710 | 0.413 |
| B4 (onnx) | multi_page | 9 | 0.056 | 0.111 | 0.022 |
| B4 (onnx) | numerical | 23 | 0.217 | 0.261 | 0.107 |
| A-dense-layout (onnx) | chart | 3 | 1.000 | 1.000 | 0.833 |
| A-dense-layout (onnx) | cross_document | 6 | 0.167 | 0.250 | 0.135 |
| A-dense-layout (onnx) | factual | 31 | 0.613 | 0.677 | 0.477 |
| A-dense-layout (onnx) | multi_page | 9 | 0.111 | 0.111 | 0.056 |
| A-dense-layout (onnx) | numerical | 23 | 0.261 | 0.435 | 0.136 |
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
| B4 (wordllama) | factual | 31 | 0.484 | 0.597 | 0.371 |
| B4 (wordllama) | multi_page | 9 | 0.056 | 0.148 | 0.067 |
| B4 (wordllama) | numerical | 23 | 0.109 | 0.297 | 0.062 |
| A-dense-layout (wordllama) | chart | 3 | 1.000 | 1.000 | 1.000 |
| A-dense-layout (wordllama) | cross_document | 6 | 0.083 | 0.167 | 0.072 |
| A-dense-layout (wordllama) | factual | 31 | 0.387 | 0.484 | 0.240 |
| A-dense-layout (wordllama) | multi_page | 9 | 0.093 | 0.130 | 0.167 |
| A-dense-layout (wordllama) | numerical | 23 | 0.167 | 0.225 | 0.120 |
| A-hybrid-flat (wordllama) | chart | 3 | 1.000 | 1.000 | 0.833 |
| A-hybrid-flat (wordllama) | cross_document | 6 | 0.250 | 0.333 | 0.200 |
| A-hybrid-flat (wordllama) | factual | 31 | 0.581 | 0.645 | 0.431 |
| A-hybrid-flat (wordllama) | multi_page | 9 | 0.000 | 0.056 | 0.016 |
| A-hybrid-flat (wordllama) | numerical | 23 | 0.130 | 0.152 | 0.057 |

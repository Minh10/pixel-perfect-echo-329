# PubLayNet evaluation summary

**What was measured.** The layout detector Docling 2.145.0 uses by default, `docling-project/docling-layout-heron` at commit `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`, on 200 PubLayNet validation pages. Sampling is `random.Random(20261101).sample` after sorting image ids. Scores use the production threshold 0.3. COCO AP uses the same boxes with a 0.01 score floor. This is the raw detector, not Docling's PDF post-processing.

**Primary results (IoU 0.5).**

| Class | Precision | Recall | F1 | AP | AP50 | AP75 |
|---|---:|---:|---:|---:|---:|---:|
| Table | 0.968 | 0.989 | 0.978 | 0.996 | 0.997 | 0.997 |
| Figure (`picture`) | 0.286 | 0.989 | 0.443 | 0.733 | 0.868 | 0.743 |

Table: 91 true positives, 3 false positives, 1 miss, out of 92 ground-truth tables. Figure: 86 true positives, 215 false positives, 1 miss, out of 87 ground-truth figures.

**What the figure errors look like.** On the drawn pages `PMC5987798_00006` and `PMC3425854_00006`, PubLayNet marks one box around a multi-panel figure, and the detector marks several `picture` boxes on the panels. One-to-one matching keeps a single true positive and counts the other panels as false positives. That pattern is visible. It is not a classification of all 215 false positives.

**What this does not show.** It does not measure end-to-end financial PDF parsing, table structure, chart reading, or the QA checks. PubLayNet is biomedical journal pages, rendered as JPEGs. Docling still merges regions using the PDF text layer, which this harness does not run. No fine-tuning experiment was run, so these numbers are a baseline only.

Title and text were scored only as secondary, many-to-one mappings. List was not scored: PubLayNet boxes a whole list and the model boxes each item (5,616 `list_item` predictions were ignored, not counted as false positives).

Full tables, checksums, and the 24 comparison images are in `research/publaynet/results/`.

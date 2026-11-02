# PubLayNet layout detection evaluation: FINAUDIT AI

**Status: RUN** on this machine, 2 November 2026. The scored subset is 200 validation images, seed `20261101`. The numbers below are that subset. They are not a confidence interval for the full validation split, and they are not an end-to-end Docling score.

A 20-image smoke run used the same seed. On this Python 3.11 install those 20 images are a subset of the 200, and they are not the first 20 rows of the sorted 200. Smoke metrics are in `results/smoke/` and are not the reported result.

## 1. Parser provenance

The previous copy of this report said Docling had never processed a FINAUDIT document. That sentence mixed three different things.

**Retrieval benchmark (14 filings).** `services/api/eval/ingest_corpus.py` defaults to `--parser pymupdf`. `audit/RETRIEVAL_REPRODUCIBILITY_REPORT.md` records that the reproduction used PyMuPDF because Docling weights were unreachable in that environment. `audit/AI_VALIDATION_REPORT.md` says the same for the real-filing results. Those 14 documents are not in the local demo database.

**Synthetic demo documents on this machine.** `services/api/data/finaudit.sqlite3` (local, not committed) has six Ready documents. For every one, `documents.parser_json` is `{"name": "docling", "version": "2.145.0", ...}` and `warnings_json` is empty. Chunk rows use the same parser and version. An empty warning list means the PyMuPDF fallback did not run: `pipeline._parse` inserts that warning only when Docling raises `ParserUnavailable` under `auto`.

The acceptance upload `doc_db4e313061b54d8eb9b85dd9701af9ca` (`annual_report_excerpt.pdf`, sha256 `3774531dd5e27bb8d6457211aaac3eb3e257b5993e3762cf1195c49e6483f338`) matches `demo/short-course-final/DEMO_GUIDE.md`:

| Record | Value |
|---|---|
| Job | `job_4325bbbcea794c9abccdcc022831525e`, requested parser `auto` |
| Started / finished | `2026-11-01T15:17:37.259141+00:00` / `2026-11-01T15:19:20.521301+00:00` |
| Duration | 103.262 seconds (the guide's 103.3 seconds) |
| Persisted parser | Docling 2.145.0, OCR off, table structure on |
| `parse.json` evidence | 4 regions: two `disclosure`, one `table`, one `figure` |
| `financial_facts` | 18 |
| `docling.json` | A `DoclingDocument` (schema 1.10.0) with a table and a picture |

The Docling JSON does not store the layout checkpoint SHA. Docling 2.145.0's default spec is `docling-project/docling-layout-heron`, revision `main`. This evaluation used the cached `main` snapshot `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`. That is the model the installed library requests. It is not a field recovered from the November 1 parse record.

**Production setting.** `Settings.parser` defaults to `docling`. `pymupdf` is the explicit fallback and is also used for page inspection and image crops. `auto` tries Docling first.

## 2. Model and label map

Read from the cached snapshot and from `docling.datamodel.layout_model_specs.DOCLING_LAYOUT_HERON`.

| Item | Value |
|---|---|
| Repository | `docling-project/docling-layout-heron` |
| Spec revision | `main` (Docling does not pin a commit) |
| Resolved commit | `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` |
| `model.safetensors` SHA-256 | `00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c` |
| `config.json` SHA-256 | `fdea30805ce2f5666b147fca941dcdd27ad468e27d6ed21902207d3da056a97d` |
| Architecture | `RTDetrV2ForObjectDetection` |
| Score threshold | 0.3 |
| Device / threads | CPU / 4 |

`id2label` in that `config.json`, checked by `evaluate.py` before scoring:

`caption`, `footnote`, `formula`, `list_item`, `page_footer`, `page_header`, `picture`, `section_header`, `table`, `text`, `title`, `document_index`, `code`, `checkbox_selected`, `checkbox_unselected`, `form`, `key_value_region`.

Every label the mapping requires is present. The run did not refuse.

Installed versions for the scored process are in `results/run_config.json` and `results/environment.json`. Python 3.11.9, docling 2.145.0, transformers 5.22.1, torch 2.15.0, pycocotools 2.0.11, numpy 2.4.6. `requirements.txt` pins numpy 2.5.4; the run used the installed 2.4.6 and did not upgrade it.

## 3. Dataset

`dax-cdn.cdn.appdomain.cloud` did not resolve (`curl` exit 6). The training archive was not downloaded. Hugging Face is reachable from this machine. The validation split of `creative-graphic-design/PubLayNet` at `4bfc1ae32abdad8953c0b81e5cdf236f1745de50` has 11,245 rows, the same count as that dataset card's validation split. Rows keep COCO `image_id`, `file_name` (`PMC*.jpg`), boxes, and category ids 1–5. The class-label index stored beside each box is `category_id - 1` (`0` text through `4` figure). That equality was checked for every annotation.

`materialize_hf_validation.py` wrote `val.json` and the JPEGs for the sampled pages. `evaluate.py` then checked categories, box geometry, and JPEG size. Verification passed: `results/dataset_verification.json` has an empty problem list.

Seventeen table boxes had height 0. The harness stops on a non-positive box, so those 17 were excluded and listed in `results/provenance.json`. Table count after exclusion is 4,752 in the full split. No box failed the outside-image check. `val.json` SHA-256 is `aeff1d25eba29c30f0d64d50f9b4f055a77fa23c93ccedcc2632098f54844161`. Parquet SHA-256 values are in the same provenance file.

The subset is image records sorted by id, then `random.Random(20261101).sample`. It depends only on this `val.json`.

## 4. What was scored

The harness is unchanged in its matching and metrics. It runs the same processor, `AutoModelForObjectDetection`, `post_process_object_detection`, and 0.3 threshold as Docling's transformers engine. It does not run Docling cluster merging, cell assignment, OCR, or table-structure recognition.

| PubLayNet | Docling labels | Role |
|---|---|---|
| table | `table` | primary |
| figure | `picture` | primary |
| title | `title`, `section_header` | secondary, many-to-one |
| text | `text`, `caption`, `footnote`, `formula` | secondary, many-to-one |
| list | `list_item` | not scored |

Predictions whose labels are not in that map are neither true positives nor false positives. On these 200 pages the ignored counts were: `list_item` 5,616, `page_header` 4,781, `page_footer` 3,324, `key_value_region` 4,521, `form` 525, `checkbox_unselected` 346, `code` 326, `checkbox_selected` 50, `document_index` 20.

Precision, recall, and F1 use greedy one-to-one matching at IoU 0.5 on boxes with score ≥ 0.3. AP, AP50, and AP75 are `pycocotools` COCOeval on boxes kept at the 0.01 floor.

## 5. Results (200 images)

| Class | GT | Pred | TP | FP | FN | Precision | Recall | F1 | AP | AP50 | AP75 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Table | 92 | 94 | 91 | 3 | 1 | 0.968 | 0.989 | 0.978 | 0.996 | 0.997 | 0.997 |
| Figure | 87 | 301 | 86 | 215 | 1 | 0.286 | 0.989 | 0.443 | 0.733 | 0.868 | 0.743 |
| Title | 306 | 517 | 301 | 216 | 5 | 0.582 | 0.984 | 0.731 | 0.534 | 0.964 | 0.372 |
| Text | 1531 | 2520 | 1500 | 1020 | 31 | 0.595 | 0.980 | 0.741 | 0.887 | 0.967 | 0.928 |

Source: `results/publaynet_metrics.csv`. Per-image counts: `results/publaynet_per_image_results.csv`. The same table is copied to `publaynet_metrics.csv` at the directory root. The previous `NOT_RUN` schema rows are replaced.

Timing (`results/timing.json`), warmup excluded, JPEG decode excluded:

| Stage | Mean | p50 | p95 |
|---|---:|---:|---:|
| Model init (once) | 22.9 s | | |
| Preprocess | 19.5 ms | 7.0 ms | 43.0 ms |
| Inference | 1839 ms | 708 ms | 3420 ms |
| Post-process | 3.0 ms | 1.3 ms | 4.4 ms |

The process took 417 seconds from start to exit, including init, two warmup images, COCO evaluation, and the 24 drawings.

Drawings are `results/visualizations/` (green ground truth, blue true positive, red false positive, orange miss). Two pages with figure false positives:

- `018_PMC5987798_00006.jpg`: one ground-truth figure around the upper multi-panel graphic, and separate `picture` boxes on the brain panels below (15 false positives, 2 true positives, no table errors).
- `006_PMC3425854_00006.jpg`: one ground-truth figure around the whole Kaplan–Meier group, plus `picture` boxes on individual plots (3 false positives, 1 true positive).

Those pages show a granularity difference: one PubLayNet figure box versus several detector boxes. They do not account, by themselves, for every one of the 215 figure false positives.

Title AP50 is 0.964 and AP75 is 0.372, so many title matches clear IoU 0.5 and miss IoU 0.75. Text AP75 stays high (0.928). Title and text are the secondary mappings, so part of that gap is the label definition in section 4.

## 6. What the scores establish

On this seeded slice of PubLayNet validation images, the raw heron detector finds almost all tables and figures at IoU 0.5. Table precision at the production threshold is high. Figure precision at that threshold is low, while figure AP is higher than the F1, which means some extra `picture` boxes are ranked below the matched ones but still above 0.3.

The scores do not establish:

- quality of Docling's merged clusters, reading order, or table-structure model;
- behaviour on financial filings, 10-K tables, or the synthetic demo PDFs;
- chart-to-text or the MATCH / POTENTIAL_DISCREPANCY checks;
- that the November 1 demo parse used this exact checkpoint SHA (the parse record stores Docling 2.145.0, not the commit).

PubLayNet JPEGs are not Docling's PDF render. Docling scales the layout image from the PDF; these files are the dataset's own JPEGs.

No fine-tuning run was done. Nothing here shows that fine-tuning would raise figure precision. A later experiment would need a held-out comparison against this subset, this seed, and these thresholds. The panel-versus-whole-figure difference is also a definition mismatch, not only a weight problem.

## 7. Commands

From the repository root, with the API virtualenv (docling 2.145.0, torch 2.15.0, pycocotools 2.0.11, pyarrow):

```text
python research/publaynet/fetch_hf_validation.py C:/Users/Lenovo/data/publaynet-hf
python research/publaynet/materialize_hf_validation.py --parquet-dir C:/Users/Lenovo/data/publaynet-hf/data --out C:/Users/Lenovo/data/publaynet --n 20 --n 200 --seed 20261101
python research/publaynet/evaluate.py --val-json C:/Users/Lenovo/data/publaynet/val.json --image-dir C:/Users/Lenovo/data/publaynet/val --model-dir C:/Users/Lenovo/.cache/huggingface/hub/models--docling-project--docling-layout-heron/snapshots/8f39ad3c0b4c58e9c2d2c84a38465abf757272d8 --out research/publaynet/results/smoke --n 20 --seed 20261101
python research/publaynet/evaluate.py --val-json C:/Users/Lenovo/data/publaynet/val.json --image-dir C:/Users/Lenovo/data/publaynet/val --model-dir C:/Users/Lenovo/.cache/huggingface/hub/models--docling-project--docling-layout-heron/snapshots/8f39ad3c0b4c58e9c2d2c84a38465abf757272d8 --out research/publaynet/results --n 200 --seed 20261101
```

`fetch_inputs.sh` still points at the IBM DAX val archive. That host did not resolve here, so it was not used. Offline harness tests: `pytest research/publaynet/tests/test_harness.py` — 6 passed. Those tests do not use heron or PubLayNet.

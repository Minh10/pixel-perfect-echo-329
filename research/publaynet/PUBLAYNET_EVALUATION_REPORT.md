# PubLayNet layout detection evaluation: FINAUDIT AI

**Status: NOT RUN. No evaluation result exists.** The two required inputs could not be obtained in the
environment where this work was done. The environment's network policy denied every host that serves them
(HTTP 403 on CONNECT; recorded by the egress proxy):

| Input | Host(s) tried | Result |
|---|---|---|
| Docling layout model weights + `config.json` (label map) | `huggingface.co`, `hf-mirror.com`, `modelscope.cn` | 403 policy denial |
| PubLayNet validation images + COCO annotations | `dax-cdn.cdn.appdomain.cloud` (official IBM DAX), HF dataset mirrors (`huggingface.co`, `datasets-server.huggingface.co`), `zenodo.org` | 403 policy denial |
| Either, via the allowed package indexes | `pypi.org` | Not published there. `layoutparser` is on PyPI, but it is a different detector whose weights come from Dropbox, so it would not evaluate FINAUDIT's model |

Consequences:
- `publaynet_metrics.csv` and `publaynet_per_image_results.csv` contain only the column schema and a `NOT_RUN`
  status.
- There are no visualizations of real predictions.
- **No precision, recall, F1, AP, timing or failure analysis is reported, and none is estimated.**

Everything that does not depend on the blocked inputs is done and is reproducible:
1. The exact model and configuration, read from the installed code.
2. The class mapping.
3. A complete evaluation harness that mirrors the production inference code.
4. Offline tests of the harness logic.

**To unblock:** allow `huggingface.co` and `dax-cdn.cdn.appdomain.cloud` in the environment's network settings,
or run it on a machine with that access. Then:

```bash
bash research/publaynet/fetch_inputs.sh /data/publaynet            # val split + labels + model; records SHA-256 and model commit
python research/publaynet/evaluate.py --val-json /data/publaynet/publaynet/val.json \
    --image-dir /data/publaynet/publaynet/val --model-dir /data/publaynet/docling-layout-heron \
    --out research/publaynet/results --n 200 --seed 20261101
```

## 1. What FINAUDIT AI actually runs (verified from installed code)

| Item | Value | Source |
|---|---|---|
| docling / docling-core / docling-ibm-models | 2.145.0 / 2.105.0 / 4.0.4 | `importlib.metadata` (`results/environment.json`) |
| transformers / torch / torchvision | 5.22.1 / 2.15.0 / 0.29.2 | same |
| FINAUDIT layout configuration | Docling **defaults**. `docling_parser.py` sets `PdfPipelineOptions` (OCR, table structure, picture classification, threads, device) but no `layout_options` | `services/api/app/processing/docling_parser.py` |
| Default layout options class | `LayoutObjectDetectionOptions` (`LayoutOptions` is a deprecated alias that maps onto it) | `docling/models/stages/layout/layout_model.py` |
| Layout model | `docling-project/docling-layout-heron` | `docling.datamodel.layout_model_specs.DOCLING_LAYOUT_HERON` |
| Model revision | `"main"`, **not pinned by Docling**. The weights a run gets depend on the download date; `fetch_inputs.sh` resolves and records the commit SHA | same |
| Engine | Transformers `AutoModelForObjectDetection` + the model's own `AutoImageProcessor` (an ONNX variant, `docling-layout-heron-onnx`, exists but is not the default) | `inference_engines/object_detection/transformers_engine.py` |
| Score threshold | **0.3** (`TransformersObjectDetectionEngineOptions.score_threshold`) | same |
| dtype / compile | auto / off | same |
| Coordinate handling | `post_process_object_detection(target_sizes=[[h, w]])` returns pixel boxes in the input image frame. Docling then rescales them to PDF points with `page_width / image.width` | `layout_object_detection_model.py` lines 153–177 |
| Label vocabulary | **Not verified.** Docling reads `id2label` from the model's `config.json` at load time and upper-cases it into `DocItemLabel` (it raises if a name is not a `DocItemLabel`). The file lives on huggingface.co | `layout_object_detection_model.py` `_build_label_map` |

So the set of labels the detector can emit is bounded by `DocItemLabel`, but which subset heron uses, and in
what id order, must be read from its `config.json`. `evaluate.py` records `id2label` in `run_config.json` and
refuses to run if any mapped label is missing (`mapping.resolve`).

**Which parser produced the existing FINAUDIT corpus.** Docling was never initialised in any FINAUDIT run done
so far, for the same HuggingFace reason. All 14 documents in the audit corpus were parsed by the PyMuPDF
fallback (`parser: pymupdf`), which uses rule-based text and table extraction, not a learned layout detector.
"The pretrained layout detector used by FINAUDIT" therefore means the configured Docling default above. It has
never processed a FINAUDIT document.

## 2. What is evaluated, and why not raw Docling output

PubLayNet provides **page images**: JPEGs rendered from PubMed Central PDFs, with COCO `[x, y, w, h]` pixel
boxes. Docling's full `DocumentConverter` is not a clean object-detection target here, for three reasons:

1. Its layout post-processing merges, splits and re-labels clusters using the PDF's text cells. On an image
   input there are no PDF cells; they would have to come from OCR, which changes the result and is a separate
   download, the OCR models.
2. Its output boxes are in PDF points after post-processing, and carry Docling-level semantics such as
   reading-order groups.
3. Post-processed clusters keep a confidence, but filtering and merging change the score distribution, which
   makes AP over those boxes ill-defined.

The harness therefore evaluates **the underlying detector**: the same heron weights, the same image processor,
the same `post_process_object_detection` call and the same 0.3 threshold that Docling's engine uses
(`publaynet_eval/detector.py` reproduces `transformers_engine.predict_batch` line for line). These are the raw
per-region predictions that Docling's layout stage starts from. The distinction matters when interpreting
results: detector quality is measured, not end-to-end Docling parsing quality on born-digital PDFs.

## 3. Dataset protocol (implemented, not executed)

- **Split:** PubLayNet `val.json` only. The val archive is fetched separately, so the ~96 GB full archive and
  the training images are never downloaded.
- **Verification** (`publaynet_eval/dataset.py`):
  - the categories must equal the published set {1 text, 2 title, 3 list, 4 table, 5 figure};
  - every annotation must reference an existing image, have a positive size and lie inside the image;
  - every selected JPEG must exist and have exactly the COCO `width × height`.

  The run stops on any failure and writes `dataset_verification.json`.
- **Subset:** image records are sorted by `id`, then `random.Random(20261101).sample(n=200)`. The selection
  depends only on `val.json`. `subset_manifest.json` records ids, file names, sizes, per-image SHA-256 and the
  SHA-256 of `val.json`.

## 4. Class mapping (`publaynet_eval/mapping.py`)

| PubLayNet | Docling label(s) | Evaluated | Reason |
|---|---|---|---|
| table | `table` | **primary** | same concept |
| figure | `picture` | **primary** | same concept, different name |
| title | `title`, `section_header` | secondary | PubLayNet "title" covers article titles *and* section headings |
| text | `text`, `caption`, `footnote`, `formula` | secondary | PubLayNet folds captions and footnotes into text |
| list | `list_item` | **not evaluated** | granularity mismatch: one PubLayNet box per list vs one Docling box per item |
| — | `page_header`, `page_footer`, `code`, `checkbox_*`, `form`, `key_value_region`, `document_index` | ignored | not annotated in PubLayNet; neither TP nor FP; counts are logged |

The secondary-class mappings are many-to-one, so their numbers are expected to be pessimistic for reasons of
label definition rather than detection quality.

## 5. Metrics (`publaynet_eval/metrics.py`)

- **Per-class precision, recall and F1 at IoU 0.5.** Matching is per image and per class: predictions are taken
  in descending score order and greedily matched one-to-one to the highest-IoU unmatched ground-truth box with
  IoU ≥ 0.5, using the boxes kept at the production threshold (0.3).
- **COCO AP / AP50 / AP75.** Computed with the official `pycocotools` COCOeval (2.0.11), and only because the
  detector exposes real per-box scores. Inference runs once at a 0.01 score floor:
  - AP uses all of those scored boxes;
  - P/R/F1 re-filter to ≥ 0.3, which is identical to production because the threshold in
    `post_process_object_detection` is a pure score filter.

  AP is never computed from post-processed Docling boxes.
- **Timing** (`timing.json`), each measured with `perf_counter`:
  - model initialisation, reported once;
  - preprocessing: RGB conversion plus the HF image processor;
  - inference: the model forward pass under `inference_mode`;
  - post-processing.

  JPEG decoding is excluded, and two warm-up images are excluded from the statistics.
- **Visualizations** (`results/visualizations/`, first 24 subset images, Table and Figure). Green = ground
  truth, blue = true-positive prediction, red = false-positive prediction, orange dashed = missed ground truth
  (false negative). Each box is labelled with its class and score.

## 6. Verification of the harness (offline; not results)

`tests/test_harness.py`, 6/6 passing (`pytest research/publaynet/tests`):

- IoU, greedy one-to-one matching (a duplicate prediction becomes an FP) and the P/R/F1 edge cases.
- The mapping fails loudly on a vocabulary that lacks a mapped label.
- Dataset verification catches a wrong category set and a JPEG whose size disagrees with COCO; the subset
  selection is deterministic.
- An end-to-end run on a **synthetic** 3-image COCO set with a **scripted** detector double gives exact
  TP/FP/FN counts, ignores unmapped labels, writes the CSVs and visualizations, and produces AP from scores
  below the P/R threshold.
- `LayoutDetector` runs on a **tiny, randomly initialised RT-DETRv2** built locally. Its outputs are meaningless
  by design; the test checks the loading and inference path and that boxes come back in the input image's pixel
  frame for a non-square 612×792 page.

These tests verify code paths only. They say nothing about heron or PubLayNet.

## 7. Failure analysis: what can and cannot be stated

There are no observed failures, because nothing ran. The following are **expected failure sources**, derived
from the label definitions and the code, that the evaluation is designed to separate. They are not measured
findings:

- **Label mismatch.** List is excluded entirely. Title and text are many-to-one. PubLayNet does not annotate
  page headers and footers, so the harness drops those predictions instead of counting them as FP.
  Caption-inside-figure conventions may differ between the datasets; the visualizations are where this would
  show.
- **OCR availability.** The detector needs no OCR: it sees only pixels. Docling's *full* pipeline on an image
  needs OCR to obtain text cells for post-processing. FINAUDIT has OCR off by default (`docling_do_ocr`) and
  parses born-digital PDFs, where cells come from the PDF text layer, so OCR does not affect FINAUDIT's
  production path. It would affect any attempt to score full Docling output on PubLayNet images.
- **Image-based vs PDF-based parsing.** On a PDF, Docling renders the page itself, at a scale of 1.0 = 72 dpi
  for the layout model, and maps the boxes back to points. PubLayNet JPEGs have their own rendering resolution
  and JPEG artefacts. Detector accuracy on PubLayNet images is therefore an imperfect proxy for accuracy on
  FINAUDIT's rendered PDF pages.

## 8. Is fine-tuning worth pursuing?

**No evidence-based conclusion is possible: there is no baseline measurement.** Recommending or rejecting
fine-tuning now would be speculation. What the decision should rest on:

1. Run this baseline: 200 PubLayNet val images, Table and Figure F1 at IoU 0.5, plus AP.
2. More importantly for FINAUDIT, run the same harness on in-domain pages. PubLayNet is biomedical journal
   articles; FINAUDIT processes financial filings (10-K/10-Q tables, charts). A PubLayNet score answers "is the
   detector broken on generic documents", not "is it good on filings". The audit's own figure-detection
   finding (AUD-14) was made on PyMuPDF's rule-based regions, not on heron, so it is not evidence about heron
   either.
3. Fine-tuning is worth pursuing only if (a) in-domain Table or Figure recall or precision at IoU 0.5 is low
   enough to cause downstream misses that the QA validator then has to abstain on, and (b) a held-out
   comparison against this exact baseline (same subset, same seed, same thresholds) shows a gain. No such
   comparison exists, and none is claimed.

## 9. Files

| Path | Content |
|---|---|
| `evaluate.py` | end-to-end runner (verification → subset → inference → metrics → CSVs → visualizations) |
| `publaynet_eval/{dataset,mapping,metrics,detector,visualize}.py` | harness modules |
| `fetch_inputs.sh` | fetches the val split, labels and model only; records SHA-256 and the resolved model commit |
| `requirements.txt` | the exact versions installed where the harness was written |
| `tests/test_harness.py` | offline tests (synthetic data, scripted and random-weight doubles) |
| `results/environment.json` | installed versions, Docling default layout configuration, network denials |
| `publaynet_metrics.csv`, `publaynet_per_image_results.csv` | schema only, status `NOT_RUN` (overwritten by a real run) |

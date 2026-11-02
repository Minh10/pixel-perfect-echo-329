# FINAUDIT AI acceptance

**Product:** one application on GitHub `main`.  
**Public URL:** none. The online release is not complete.  
**Date of this record:** 2 November 2026.

## Official status

`main` contains the premium workspace, the FastAPI service and PDF worker, the three financial-analysis outcomes that were exercised in the browser, and the completed PubLayNet evaluation. Older pull requests are already in this history. They should not be merged again.

| Line | Commit that entered this history | What it contributes |
|---|---|---|
| Verified demo outcomes | `45f414a` | OpenAI `gpt-4.1-mini` chart readings, match / potential discrepancy, two-report trend |
| Workspace | `c487e40` | Premium UI, CI formatting, OpenAPI file, laptop trend chart |
| Layout evaluation | files from `f113699` | PubLayNet harness, 200-page metrics, drawings, provenance correction |

## Verified features

**Parsing.** The local database for the acceptance upload `doc_db4e313061b54d8eb9b85dd9701af9ca` records Docling 2.145.0, an empty warning list, 4 evidence regions, and 18 financial facts. The parse job lasted 103.262 seconds. Production default parser is Docling. PyMuPDF runs only when requested, or when Docling cannot start under `auto`, and that fallback writes a warning. The 14-document retrieval benchmark was ingested with PyMuPDF. That corpus is not the demo database.

**Chart-to-text.** A real `gpt-4.1-mini-2025-04-14` reading of the unlabelled segment chart is stored as visual estimates (North 50, South about 35, East about 12, West about 3) with status insufficient evidence. The labelled synthetic chart reading copied printed numbers 240, 158, 90, and 21. The screen states which of those two kinds of number it is showing. Screenshots: `docs/workspace-redesign/audit-summary-1440.png`, `docs/workspace-redesign/audit-discrepancy-1440.png`.

**Discrepancy.** On that labelled chart, North, South, and West match the 2025 table (difference 0). East is a potential discrepancy: chart 90 versus reported 150, absolute difference 60 (40.0%). The UI calls this a potential discrepancy, not a finding of fraud.

**Trends.** Revenue from the 2024 and 2025 synthetic annual reports is 2,900 (2023), 3,200 (2024, shown once), and 3,550 (2025), GBP millions. The 2025 bar is inside the plot at 1280px and at 1440px. Screenshots: `docs/workspace-redesign/trends-1280.png`, `docs/workspace-redesign/trends-1440.png`.

**Layout detector.** Heron commit `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`, 200 PubLayNet validation pages, seed `20261101`, score threshold 0.3, IoU 0.5:

| Class | Precision | Recall | F1 | AP |
|---|---:|---:|---:|---:|
| Table | 0.968 | 0.989 | 0.978 | 0.996 |
| Figure | 0.286 | 0.989 | 0.443 | 0.733 |

These figures are from `research/publaynet/results/publaynet_metrics.csv`. `research/publaynet/tests/test_harness.py` uses synthetic images and a scripted detector. Those tests check the code. They are not PubLayNet scores. The evaluation does not measure end-to-end financial PDF parsing, and no fine-tuning result is claimed.

## Release boundary

The document API is reachable on loopback without a token so the verified local demo keeps working. `FINAUDIT_API_TOKEN` rejects unauthenticated calls to every `/api/v1` route except health when the token is set. No public URL was opened, and no browser test was run against a public host. Until both exist, do not describe FINAUDIT AI as an online service.

Local checks before this commit: backend `pytest -m "not docling_models"` 391 passed, 1 deselected; contract check 0 errors; frontend lint 0 errors, `tsc --noEmit` clean, 14 tests passed, production build succeeded. GitHub Actions on `main` repeats those jobs.

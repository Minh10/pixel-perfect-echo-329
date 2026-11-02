# FINAUDIT AI

FINAUDIT AI reads financial PDFs, keeps every figure tied to a page region, and compares chart readings with the tables parsed from the same documents. It is one application: a workspace UI, a FastAPI service, and a PDF worker. This repository's `main` branch is that application.

The product does not decide that a filing is fraudulent. A chart value that disagrees with one aligned table cell is a **potential discrepancy**. A chart number with no aligned table cell is **insufficient evidence**.

## What is verified

| Capability | Status |
|---|---|
| Premium workspace (Overview, Documents, Document Intelligence, Consistency Audit, Trends) | In `main`. Browser evidence from 2 November 2026 is in `docs/workspace-redesign/`. |
| Docling 2.145.0 parse of the synthetic annual-report excerpt, with PyMuPDF as the fallback | Stored locally for the 1 November 2026 acceptance upload: 103.3 seconds, 4 evidence regions, 18 financial facts. |
| Chart-to-text with OpenAI `gpt-4.1-mini` | Real model output. Unlabelled charts stay visual estimates. Printed labels are named as printed labels. |
| Match and potential discrepancy on the labelled synthetic chart | North, South, and West match. East is a potential discrepancy: chart 90 versus table 150. |
| Multi-document revenue trend | 2,900 (2023), 3,200 (2024, once), 3,550 (2025), GBP millions, from the two synthetic annual reports. |
| PubLayNet layout-detector baseline | Real 200-page measurement in `research/publaynet/`. Table F1 0.978, figure F1 0.443 at IoU 0.5. The harness unit tests use synthetic images and are not measurements. |
| Public website | Not deployed. There is no verified public URL. |

Details and limits are in `docs/FINAL_ACCEPTANCE.md`.

## Run it locally

The API and the worker stay on this machine. Do not publish port 8000.

Terminal 1, from `services/api` (Python 3.11 or 3.12, virtualenv already used in development):

```text
python scripts/start_api.py
```

That process loads `services/api/.env` and listens on `127.0.0.1:8000` only. Put `FINAUDIT_LLM_API_KEY` in that file. Do not commit it.

Terminal 2, from `services/api`, with the same environment:

```text
python -m app.worker
```

Terminal 3, from the repository root. ` .env.local` is gitignored:

```text
# VITE_FINAUDIT_API_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open `http://127.0.0.1:8080`. The footer should say the document service is live.

`services/api/docker-compose.yml` runs the API, the worker, and Qdrant on a shared volume, with ports bound to `127.0.0.1`. Set `FINAUDIT_API_TOKEN` in `services/api/.env` before any deployment that is not loopback. See `DEPLOYMENT.md`.

## Layout evaluation

```text
python research/publaynet/evaluate.py --val-json <val.json> --image-dir <val-images> --model-dir <docling-layout-heron snapshot> --out research/publaynet/results --n 200 --seed 20261101
```

The committed CSVs and drawings are the run that already finished. Commands and checksums are in `research/publaynet/PUBLAYNET_EVALUATION_REPORT.md`. A short presentation summary is `research/publaynet/EVALUATION_SUMMARY.md`.

## Tests

```text
cd services/api
python -m pytest -q -m "not docling_models"
python eval/audit/contract_check.py --strict
```

From the repository root: `npx tsc --noEmit`, `npm run lint`, `npm test`, `npm run build`.

GitHub Actions on `main` runs the same backend and frontend jobs.

## Lovable

This code was first created in Lovable and is still linked to [the existing Lovable project](https://lovable.dev/projects/282cd50e-8aed-48da-9ff2-43355f4aa3d5). GitHub `main` is the source of truth.

Before the next Lovable prompt, sync Lovable **from GitHub** so it loads this `main`. A prompt against the old prototype would commit over this application. Do not open a second Lovable project for FINAUDIT AI.

## Repository map

| Path | Role |
|---|---|
| `src/` | Workspace UI |
| `services/api/` | FastAPI, worker, parsers, retrieval, chart checks |
| `research/publaynet/` | Offline layout-detector evaluation |
| `docs/FINAL_ACCEPTANCE.md` | Acceptance record |
| `DEPLOYMENT.md` | How to host it without exposing the document API |

# Five-minute demonstration

Branch: `demo/short-course-final`.

Use documents that are already **Ready**. A fresh Docling parse of the 3-page fixture took 103 seconds on this machine, so do not start an upload during the five minutes. The upload path was checked separately on 1 November 2026 and is described at the end.

Screenshots from that check are in `docs/short-course-demo/`. If the live app fails, open those files instead of improvising results.

## Start, before the room

Three terminals. Keep the API on loopback.

```powershell
# Terminal 1 — API
cd services\api
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2 — worker
cd services\api
.\.venv\Scripts\python.exe -m app.worker
```

```powershell
# Terminal 3 — frontend
# Repo-root .env.local (gitignored):
# VITE_FINAUDIT_API_URL=http://localhost:8000
npm install
npm run dev
```

Open http://localhost:8080. The sidebar footer must say **Live · Document service**. Health: http://127.0.0.1:8000/api/v1/health.

Test PDF, already in the repo: `services/api/tests/fixtures/annual_report_excerpt.pdf`. It is a synthetic 3-page report for Fictional Example Holdings plc and contains no real company data.

If Documents is empty, upload that PDF twice with two different titles and wait until both are Ready before the demo. One report is not enough for Trends.

## Script

**0:00 — Documents.** Show the library. On this machine the checked rows are Synthetic AR, Fictional Example Holdings - Annual Report 2025 (synthetic fixture), and Acceptance upload 2026-11-01. All three are Ready, 3 pages, Annual Report. Say they were parsed by Docling, not typed in by hand. Screenshot: `docs/short-course-demo/acceptance-documents-ready.png`.

**0:40 — Chart crop, not a generated summary.** Open Consistency Audit. Select Synthetic AR or the acceptance upload.

- The page shows the extracted page-3 crop, caption **Figure 1: Revenue by segment, 2025 (synthetic)**, and labels North, South, East, West.
- Say the crop and caption come from the PDF parser. No model wrote them.
- Click **Read chart with the configured model**.
- Expected: **Visual interpretation is unavailable. No chart summary was generated.**
- Visual check stays **INSUFFICIENT_EVIDENCE**. Say automated chart-to-table auditing is not claimed, because no vision model is configured.
- Click **Open source page** only if time remains. It opens page 3 with the figure highlighted.

Screenshots: `acceptance-audit-crop.png`, `acceptance-interpretation-unavailable.png`.

**2:00 — Retrieval and the source table.** On the same audit page, search `operating profit`.

- Expected method label: `bm25+dense`.
- Rank 1 is the page-2 income-statement table. Rank 2 is the sentence that operating profit rose to GBP 703 million.
- The figure hit says figure values are not extracted from the image. Do not read the bar heights as numbers.
- Click rank 1. Document Intelligence opens page 2 with the table highlighted.
- Point at the cells: 2025 revenue **4,812**, 2025 operating profit **703**, GBP millions. These are parsed table cells.

Screenshots: `acceptance-evidence-search.png`, `acceptance-source-table.png`, `acceptance-upload-table.png`.

**3:20 — Two-report comparison.** Open Trends. Tick two Ready reports. Leave the metric on **Revenue**.

- The heading says **Comparison, not a comprehensive trend**.
- Expected points, GBP millions: 2024 **4281** and 2025 **4812** in each selected report, page 2.
- The Change column, 12.4%, is left out because it is a percent.
- Say the two local reports are copies of the same synthetic PDF, so the bars match. This is not a multi-issuer trend and not model output.
- Click **Synthetic AR · 2025 · 4812**. Page 2 opens with the income-statement table highlighted.

Screenshot: `acceptance-trends-comparison.png`.

**4:20 — Question answering stays off.** Open AI Analysis. Select one report. Ask `What was operating profit in 2025?`

- Expected: **Question answering is not configured on this server.** No answer text is produced.
- Say the supported number is the table cell 703, already shown, not an answer from a language model.

Screenshot: `analysis-qa-unavailable.png`.

## What was executed on 1 November 2026

- `POST /api/v1/documents` accepted `annual_report_excerpt.pdf` as **Acceptance upload 2026-11-01** (`doc_db4e313061b54d8eb9b85dd9701af9ca`).
- The worker parsed it with Docling 2.145.0 in 103.3 seconds: 3 pages, 4 evidence regions, 18 parsed financial facts. The Documents page showed Ready, and Document Intelligence highlighted the income statement.
- Search on that new report returned the page-2 table first and opened it from the UI.
- Chart reading returned HTTP 503. No summary was stored.
- Trends plotted the parsed revenue facts for the two earlier copies and opened the source table.
- Backend tests: 384 passed, 1 deselected. Frontend: typecheck passed, 11 tests passed, production build completed.

## If the live demo fails

Use the screenshots above and say which step failed. Do not substitute a written summary or a discrepancy verdict.

- Footer says demo instead of Live: set `VITE_FINAUDIT_API_URL=http://localhost:8000` and restart `npm run dev`.
- A new upload stays on Processing: confirm terminal 2 is the worker. Parsing this fixture takes about two minutes after Docling has loaded.
- The new upload's worker log recorded 0 vectors because the local vector index was already open in the API process. Search can still return the table through the hybrid endpoint. To rebuild vectors, stop the API and the worker, run the one-process reindex in `FINAL_LIMITATIONS.md`, then start the API and the worker again.
- Trends says two reports are required: select a second Ready report. Do not show one report as a trend.

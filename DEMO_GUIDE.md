# Five-minute demonstration

Branch: `final-demo` (rollback checkpoint: `demo/short-course-final` at `3bfc04b`).

Use documents that are already **Ready**. Do not upload during the five minutes unless the library is empty. All figures below were verified on 2 November 2026 with provider **openai**, model **gpt-4.1-mini**, and parsed table facts from Docling.

Screenshots are in `docs/short-course-demo/`. If the live app fails, open those files instead of improvising results.

## Start, before the room

Three terminals. Keep the API on loopback. The vision key must be in `services/api/.env` as `FINAUDIT_LLM_API_KEY` (gitignored). Plain `uvicorn` does not load that key into the process; use the helper below.

```powershell
# Terminal 1 — API (loads gitignored .env, binds 127.0.0.1 only)
cd services\api
.\.venv\Scripts\python.exe scripts\start_api.py
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

Open http://localhost:8080. The sidebar footer must say **Live · Document service**.

Checks: http://127.0.0.1:8000/api/v1/health returns 200. http://127.0.0.1:8000/api/v1/index/status shows `llm.provider` **openai**, `llm.model` **gpt-4.1-mini**, `llm.available` **true**.

**Fixture PDFs in the repo** (synthetic, not real companies):

| File | Role |
| --- | --- |
| `services/api/tests/fixtures/synthetic_chart_check.pdf` | Printed chart numbers vs table (MATCH + POTENTIAL_DISCREPANCY) |
| `services/api/tests/fixtures/synthetic_ar_2024.pdf` | Distinct annual report, 2023–2024 revenue |
| `services/api/tests/fixtures/synthetic_ar_2025.pdf` | Distinct annual report, 2024–2025 revenue |
| `services/api/tests/fixtures/annual_report_excerpt.pdf` | Unlabelled bar chart; estimates only |

If the chart-check or annual-report rows are missing, upload the matching fixture once as **Annual Report** and wait until **Ready** before presenting.

## Script

**0:00 — Documents.** Show the library. Point at **Ready** rows, especially **Fictional Example Holdings plc — segment chart check 2025 (synthetic test fixture)** and the two **Annual Report 2024 / 2025 (synthetic test fixture)** titles. Say values come from parsed PDF tables, not hand entry.

**0:40 — Outcome 1: chart-to-text (real VLM).** Open **Consistency Audit**. Select **Acceptance upload 2026-11-01** (or any Ready report with the page-3 segment bar chart).

- The crop and caption are from Docling.
- A stored reading should already appear: summary from **gpt-4.1-mini**, points marked **estimated from the graphic** (North 50, South ~35, East ~12, West ~3 on the checked run).
- If empty, click **Read chart with the configured model** once and wait. Do not click repeatedly on quota errors.
- Visual check on this unlabelled chart stays **INSUFFICIENT_EVIDENCE** (no segment table with those labels).

Screenshot: `audit-existing-chart-summary.png`.

**1:40 — Outcome 2: MATCH and POTENTIAL_DISCREPANCY.** Select **Fictional Example Holdings plc — segment chart check 2025 (synthetic test fixture)**.

- Chart-to-text lists printed values **240, 158, 90, 21** and model id **openai · gpt-4.1-mini-2025-04-14**.
- Visual check: **MATCH** for North, South, West; **POTENTIAL_DISCREPANCY** for East (chart **90** vs table **150**, absolute difference **60**).
- Click **Open source page** on the East line. Document Intelligence opens page 1 with the segment table; East cell **150**.

Screenshots: `audit-match-and-discrepancy.png`, `audit-discrepancy-source.png`.

**3:00 — Outcome 3: multi-document trend.** Open **Trends**. Select only:

- Fictional Example Holdings plc — Annual Report **2024** (synthetic test fixture)
- Fictional Example Holdings plc — Annual Report **2025** (synthetic test fixture)

Metric **Revenue**. Heading: **Source-grounded series from parsed reports**. Expect 2023 **2900**, 2024 **3200** (once), 2025 **3550**, GBP millions. Click the **2024 · 3200** citation; the 2024 report table opens.

Screenshot: `distinct-reports-revenue.png` (operating profit: `distinct-reports-operating-profit.png`).

**4:20 — Boundaries.** Say QA is still off unless configured. Do not claim the unlabelled chart’s percent estimates as audited table facts. Redacted provider log: `openai-vision-success.txt`.

## If the live demo fails

Use the screenshots and `REQUIREMENTS_COMPLIANCE.md`. Do not invent summaries or discrepancy verdicts.

- Footer says demo: set `VITE_FINAUDIT_API_URL=http://localhost:8000` and restart Vite.
- **Visual interpretation is unavailable**: restart API with `scripts\start_api.py`, confirm `llm.available` in index status, confirm OpenAI billing.
- Interpret returns 429: stop; do not hammer the API.
- Trends needs two distinct Ready reports with the same metric and units.

## Verified run (2 November 2026)

- One schema vision probe on the existing chart crop: HTTP 200, model `gpt-4.1-mini-2025-04-14`.
- Stored readings on Acceptance upload and on `doc_95e7442728764d9088643ac9c9f9b9d9` (chart-check fixture).
- Backend `pytest -q`: 389 passed. Frontend: `tsc --noEmit` clean, Vitest 14 passed, `npm run build` succeeded.

# Requirements compliance

Project 10 expected three outcomes: automated chart-to-text summaries, visual discrepancy checks, and multi-document financial trend analysis.

Checked on 2 November 2026 on branch `final-demo` (verified demo delivery; rollback checkpoint `demo/short-course-final` at `3bfc04b`). The gitignored server `.env` selects provider `openai`, model `gpt-4.1-mini`, and base URL `https://api.openai.com/v1`. The key stays in `FINAUDIT_LLM_API_KEY`. The running API process has that variable set (length 164) and `GET /api/v1/index/status` reports the provider available. The stable demo checkpoint remains `demo/short-course-final` at `3bfc04b` and was not merged. The app at http://localhost:8080 was in live mode against http://127.0.0.1:8000.

An earlier call on 1 November returned HTTP 429 `credit_balance_exhausted`. After credits were added, one vision request against the existing chart crop returned HTTP 200. That request was not repeated as a quota retry.

| Outcome | Status | Where the result comes from | What was executed |
| --- | --- | --- | --- |
| Automated chart-to-text summaries | IMPLEMENTED | `gpt-4.1-mini-2025-04-14` through the existing OpenAI-compatible adapter. Every number below was parsed from the model response. | The unlabelled Figure 1 crop first returned `is_chart: true` and value `cannot be read` for North, South, East, and West. The application's later interpret of Acceptance upload 2026-11-01 stored a different real reading of that same figure: summary "North is the largest segment, followed by South, East, and West." Points are visual estimates, `printedOnChart` false: North 50, South approximately 35, East approximately 12, West approximately 3. The labelled synthetic chart returned the printed labels North 240, South 158, East 90, and West 21, with summary "The chart shows segment revenue in GBP millions for four regions: North has 240, South has 158, East has 90, and West has 21." Screenshots: `docs/short-course-demo/audit-existing-chart-summary.png`, `audit-match-and-discrepancy.png`. Record: `openai-vision-success.txt`. |
| Visual discrepancy checks | IMPLEMENTED for the labelled synthetic fixture | Chart points from the model, compared by code with parsed FinancialFacts for the same label, year, scale, and currency. | `synthetic_chart_check.pdf` is marked SYNTHETIC TEST FIXTURE. Its table, parsed before the model call, is North 240, South 158, East 150, West 21, GBP millions, segment scope, fiscal year 2025. The model read the printed chart values 240, 158, 90, and 21. The check computed MATCH for North, South, and West (absolute difference 0) and POTENTIAL_DISCREPANCY for East (chart 90, table 150, absolute difference 60). The East source button opened `/intelligence?doc=doc_95e7442728764d9088643ac9c9f9b9d9&page=1&ev=ev-p1-b003`, where the table shows East 150. The unlabelled chart's estimates do not match a segment fact, so that page stays INSUFFICIENT_EVIDENCE. Screenshots: `audit-match-and-discrepancy.png`, `audit-discrepancy-source.png`. |
| Multi-document financial trend analysis | IMPLEMENTED | Parsed FinancialFacts from two different synthetic annual reports. Not a model and not demo-mode data. | Revenue is 2900 (2023), 3200 (2024, shown once), and 3550 (2025), GBP millions. Operating profit is 360, 410, and 470. The 2024 citation still opens the 2024 income-statement table. The new chart-check upload was left unselected. Screenshot: `distinct-reports-revenue.png`. |

| Supporting check | Status | Evidence |
| --- | --- | --- |
| OpenAI vision on the existing chart crop | IMPLEMENTED | HTTP 200, served model `gpt-4.1-mini-2025-04-14`, strict JSON parsed. On that crop the model said the bar values cannot be read. |
| Source navigation | IMPLEMENTED | The discrepancy source opens the synthetic table. The trend citation opens the 2024 revenue row's report. |
| Tests on 2 November 2026 | Passed | Backend `pytest -q`: 389 passed, 1 local-Qdrant warning. Frontend `tsc --noEmit`: no errors. Vitest: 14 passed. |

The unlabelled fixture chart has no printed numbers, and the model did not return the same reading twice: one call said the values cannot be read, and the stored application reading gives rough visual estimates. Those estimates are labelled as estimates and are not treated as a table match. The MATCH and POTENTIAL_DISCREPANCY results use only the printed-number synthetic fixture.

Demo mode is unchanged. With `VITE_FINAUDIT_API_URL` unset, Trends still shows the labelled fictional series and Consistency Audit stays a pending module.

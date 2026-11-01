# Requirements compliance

Project 10 expected three outcomes: automated chart-to-text summaries, visual discrepancy checks, and multi-document financial trend analysis.

Checked on 1 November 2026 in the running app at http://localhost:8080, against Docling extracts of `services/api/tests/fixtures/annual_report_excerpt.pdf`. No language or vision model is configured. Nothing below was typed in as if a model had produced it.

| Outcome | Status | Where the result comes from | What was executed |
| --- | --- | --- | --- |
| Automated chart-to-text summaries | PARTIAL | Deterministic Docling crop and the printed PDF caption. Not a VLM. | Consistency Audit showed Figure 1 on page 3 for Synthetic AR and for the new acceptance upload. **Read chart with the configured model** returned HTTP 503. The page said visual interpretation is unavailable and that no summary was generated. Screenshots: `docs/short-course-demo/acceptance-audit-crop.png`, `acceptance-interpretation-unavailable.png`. |
| Visual discrepancy checks between charts, tables, and text | PARTIAL | Deterministic refusal. The comparison code can score a stored chart reading against one aligned parsed fact. No reading exists, so no check was scored. | The audit page stayed **INSUFFICIENT_EVIDENCE** and said automated chart-to-table auditing is not available. Unit tests cover MATCH, POTENTIAL_DISCREPANCY, and ambiguous facts. No live MATCH or discrepancy was produced. |
| Multi-document financial trend analysis | PARTIAL | Deterministic parsed table facts from two processed copies of the same synthetic PDF. Not a model and not demo-mode chart data. | Trends, with both earlier reports and metric Revenue, plotted 2024 = 4281 and 2025 = 4812 GBP millions for each report and labelled the result a comparison, not a comprehensive trend. The 12.4% Change row was excluded. Clicking Synthetic AR 2025 opened page 2 with the income-statement table highlighted. Screenshot: `acceptance-trends-comparison.png`. |

| Supporting workflow | Status | Evidence |
| --- | --- | --- |
| PDF upload, Docling extraction, retrieval, and evidence inspection | IMPLEMENTED | `POST /api/v1/documents` accepted the fixture as Acceptance upload 2026-11-01. The worker finished with Docling 2.145.0, 3 pages, 4 evidence regions, and 18 parsed facts. Documents showed Ready. Opening the report highlighted the page-2 table (revenue 4,812, operating profit 703). Search for `operating profit` on that report returned the table first, labelled `bm25+dense`, and the click opened the same table. Screenshots: `acceptance-documents-ready.png`, `acceptance-upload-table.png`. |
| Layout-aware BM25 and dense retrieval on the earlier copies | IMPLEMENTED | Those copies were reindexed in one process before the API was started. Search returned `bm25+dense`, with the page-2 table first. |
| Dense vectors for a PDF uploaded while the API is running | PARTIAL | The acceptance upload's index log recorded 0 vectors, status unavailable, because embedded Qdrant was already open in the API process. The hybrid query still returned the correct table and narrative. |
| PDF viewer and highlights | IMPLEMENTED | Citations from search and from Trends opened `/intelligence` with the document, page, and evidence id. The table or figure outline was selected. |
| FinancialFact normalization | IMPLEMENTED | The new upload and each earlier copy expose 18 parsed facts with value, period, scale, currency, scope, page, and bbox. |
| QA safety behaviour | IMPLEMENTED | Asking `What was operating profit in 2025?` returned HTTP 503. The page said question answering is not configured and showed no generated answer. Screenshot: `analysis-qa-unavailable.png`. |
| PubLayNet evaluation | NOT IMPLEMENTED | PubLayNet was not downloaded or scored. |
| A real vision-model chart summary | NOT IMPLEMENTED | `FINAUDIT_LLM_PROVIDER` defaults to `none`. The interpret call returned 503. |
| A verified chart-versus-table discrepancy | NOT IMPLEMENTED | No chart reading was stored, so the UI did not compare an estimate with the table. |

Demo mode is unchanged. With `VITE_FINAUDIT_API_URL` unset, Trends still shows the labelled fictional series and Consistency Audit stays a pending module. The checks above were made in live mode.

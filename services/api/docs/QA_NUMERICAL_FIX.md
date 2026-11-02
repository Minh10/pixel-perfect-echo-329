# Numerical QA fix and safe Windows rollout

## Verified source changes

- `app/qa/evidence_binding.py`: resolve equal-value candidates by the explicit claimed period. Collapse repeated totals only with stored fact/table provenance and identical document, table, row, value, period, units, currency and scope. A repeated headline below its own `… includes:` reconciliation group is equivalent; segment groups are not.
- `app/qa/pipeline.py`: classify calendar years separately from amounts in an already-verbatim operand quote; reject year-only quotes, malformed numbers and multiple amounts. Keep source row/period/unit/scope binding authoritative. Prompt explicitly asks for amount-only operands and exact citation substrings, not reconstructed dot leaders, and no numerical operands for purely narrative answers.
- Citation existence/verbatim, source hash/page/region provenance, calculation allowlist, repair-once and abstention remain intact.

## Test results

302 Python tests passed: affected QA/calculator/binding, prompt injection, financial numbers, grounding benchmark, real Berkshire replay and authenticated local HTTP integration. HTTP tests use an isolated test token and temporary storage, not deployment credentials or documents.

Public real evidence: https://www.berkshirehathaway.com/news/may0325.pdf. Stored extracted evidence replay validates:

| Reported amount | Period | Value / unit | Citation |
| --- | --- | --- | --- |
| Net earnings attributable to Berkshire shareholders | First Quarter 2025 | 4,603 million dollars | Page 1 |
| Operating earnings | First Quarter 2024 | 11,222 million dollars | Page 1 |
| BNSF | First Quarter 2025 | 1,214 million dollars | Page 2 |

These are deterministic validation replays of actual PDF evidence, **not live model acceptance tests**. Wrong periods, wrong units, fabricated quotes and amounts still fail. 106 frontend tests also passed; lint has zero errors/six existing warnings; host build OK. No paid model calls or new uploads in this task.

## Preserve the currently running Windows service

The source in this project is updated. Lovable publication cannot update an already-running Windows Python process, and no remote Windows control is available here. The running API and tunnel were not restarted or modified.

On the Windows checkout, use Cursor to apply only the two QA source-file changes above from the latest synchronized main, plus regression tests. Do **not** overwrite the entire API folder: the running Windows checkout has owner-added call ceilings/emergency-stop controls not present in this source configuration. Preserve those local controls, `.env`, data, model settings, worker and the existing cloudflared process.

Run in the existing Python environment from `services/api`:

```powershell
python -m pytest tests/unit/test_berkshire_qa.py tests/unit/test_evidence_binding.py tests/unit/test_qa.py tests/unit/test_prompt_injection.py tests/unit/test_grounding_benchmark.py tests/unit/test_financial_numbers.py tests/integration/test_rag_api.py -q
```

If API auto-reload is already enabled, confirm it loaded only the QA changes. Otherwise, loading changed Python modules requires an owner-scheduled API-process reload after in-flight requests finish; **leave cloudflared, worker, data and configuration running/unchanged**. A zero-restart deployment cannot be promised.

After the API loads the changes, open the existing `berkshire-q1-2025` report in Ask AI and test the three questions above. Confirm exact value, period, units and source page; also confirm an unsupported 2030 forecast abstains. Count repair calls against the existing Windows ceiling. Do not claim live success before that check.
# FINAUDIT AI temporary Windows demonstration

Official existing website: https://finauditai-cdac.lovable.app. Keep this Lovable project and GitHub main; do not fork. Temporary live demo was activated and published on 2026-11-02 from the existing synchronized main b9eb94a; the official URL was exercised successfully. No frontend or Windows backend source was changed during activation.

## What is implemented

- Public Overview, Documents and labelled sample remain available without entry. With live mode off, admin/admin opens only the sample.
- With the server switch on and private configuration complete, admin/admin obtains a signed **one-hour** `__Host-finaudit_demo` cookie: Secure, HttpOnly, SameSite=Strict, Path=/, no Domain. This is a temporary demo session, **not a Cloud user or owner identity**. Anyone knowing the credentials can enter; it does not secure against strangers.
- Every live JSON, job, page image, chart crop, citation, Docling export and PDF download verifies the signature, expiry and durable revocation before forwarding. Exit demo revokes the session, clears its cookie and returns to the sample. The off switch denies these demo cookies immediately after the updated deployment reaches production.
- All existing frontend-used FastAPI routes are already allowlisted. Arbitrary admin routes, encoded/traversal paths, cross-origin mutations, unexpected redirects and invalid parameters are rejected. FastAPI receives only the server-injected bearer token, not the demo cookie. Errors and response headers do not expose upstream authentication details.
- The browser discovers live mode from server-verified status after hydration; no VITE activation flag is required. SSR always renders sample mode; no fictional results are substituted for live results.
- Native PDF/image resources and Range requests remain same-origin. Temporary uploads retain multipart boundaries but are bounded and inspected before forwarding; downloads are streamed.

## Server-only settings in Lovable

Open **Project Settings → Secrets** in this existing project. Never paste token values in chat or commit them.

| Name                              | Required action                                                                                                                                                                      |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `FINAUDIT_DEMO_SESSION_SECRET`    | Already generated and stored privately. Do not copy or reveal it.                                                                                                                    |
| `FINAUDIT_BACKEND_URL`            | Add the current HTTPS origin only, e.g. `https://strip-conduct-pct-newton.trycloudflare.com`, without `/api/v1`. The configured HTTPS origin passed authenticated connectivity checks on 2026-11-02; do not restart the existing tunnel during this demonstration. |
| `FINAUDIT_API_TOKEN`              | Privately copy the existing Windows `services/api/.env` bearer token into this secret. It must match the API exactly. Already provisioned and verified without revealing its value.                                  |
| `FINAUDIT_TEMPORARY_DEMO_ENABLED` | Created with exact value `true` on 2026-11-02 following owner approval and reported upstream control verification. Set `false` and republish immediately after the course. This is the single activation switch.           |

`FINAUDIT_AUTHORIZED_USER_ID` is **not required** for temporary demo mode; no account must be created. Retained legacy owner policy is unchanged when the demo switch is off. `VITE_FINAUDIT_SERVICE_MODE` is no longer used to activate live requests. Never put bearer tokens, signing secrets or OpenAI credentials in VITE variables.

OpenAI remains exclusively on Windows FastAPI and its worker (`FINAUDIT_LLM_API_KEY`, configured by that backend); do not add it to Lovable.

## Conservative controls and remaining cost gate

Durable, atomic Lovable Cloud counters apply across server instances, fail closed if unavailable, and cannot be reset by logging out or changing IP. Limits are deliberately global for this one demonstration, not per-user production quotas:

- 10 live entry attempts/minute globally.
- 120 proxied requests/minute globally and 60/minute per signed session.
- 2 work-creating POSTs/minute and 20/day globally, including QA, retrieval, interpretation, indexing and reprocessing. Failed/invalid requests consume the reserved budget too.
- 10 PDF uploads per UTC day globally; resets at 00:00 UTC using a new daily bucket, without resetting or deleting historical counts. One unencrypted PDF per upload, maximum 10 MiB and 30 pages. JSON maximum 16 KiB, questions/queries maximum 2,000 characters, at most four report IDs and retrieval depth five. A quota rejection explicitly states the limit and UTC reset time, not that the backend is unavailable.
- Image DPI 36–150; fixed HTTPS upstream origin and strict path/method/query guards.

These are custom application limits, not a built-in platform limiter. Global ceilings are stronger than an IP quota for this shared demo and do not trust client-supplied IP headers. Counters use UTC minutes/days. There is no automatic counter cleanup yet; session/counter records contain no user identities, tokens or document contents.

**POST limits are not a dollar spending guarantee.** Before this activation, Cursor reported testing a 40-model-call cutoff (41st blocked before contacting OpenAI), emergency stop, one worker/job, three attempts, no model client retries, 120-second model timeout and 2048 output tokens per call; QA repair counts against the ceiling. These are owner-reported upstream checks, not independent Lovable tests or a verified monetary ceiling. No local Windows backend changes were made here. Publicly known admin/admin is not protection against strangers.

## Windows start and tunnel rotation

No checked-in `.ps1`, `.bat` or `.cmd` launcher exists in this repository, so an owner-specific Windows script cannot be named or verified. Cursor should supply its actual launcher path and commands. For the existing Python helper, from PowerShell at the repository root with the backend virtual environment activated:

```powershell
Set-Location services/api
python scripts/start_api.py
```

In a second activated PowerShell window in `services/api`, run `python -m app.worker`. Start the owner's existing Qdrant service and ensure API/worker use the same data directory and Qdrant URL. The API helper loads `services/api/.env` and listens at `127.0.0.1:8000`. Keep API/Qdrant host ports loopback-only.

In another window:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Copy the newly printed HTTPS origin into `FINAUDIT_BACKEND_URL` in Lovable Secrets each time the quick tunnel restarts. Never include the bearer token in the URL. The previously reported hostname may already be expired. Do not expose Qdrant through the tunnel.

## Explicit activation and published acceptance

1. Cursor supplies the current tunnel origin, actual Windows launcher instructions, matching API contract and verified worker/model cost controls; owner privately sets the shared token.
2. Verify the real service locally, with a small real PDF and model calls bounded. Do not turn on the switch before these controls are verified.
3. Owner explicitly approves temporary public demo deployment, sets the server switch to `true`, then uses **Publish** on this existing Lovable project. Secret changes affect preview immediately; production requires publication.
4. At **https://finauditai-cdac.lovable.app**, enter admin/admin. Confirm no-cookie and forged-cookie API calls are 401; off switch denies demo access; cross-origin mutations are 403; unrelated paths are 404.
5. Upload a real PDF through the existing drop area. Confirm actual job success, Docling pages, table facts, chart interpretations/comparisons, fact-based trends, grounded QA/citations and original PDF download. Check images and crops load through `/api/document-service`, never by direct token-bearing URLs.

**Published acceptance was performed on 2026-11-02.** See the actual results below; unit tests alone are not the basis for these live results.

## Disable immediately after the demo

## Upload quota fix acceptance — 2026-11-02

- Published application revision `3a4ce45` raises only the global upload allowance from 3 to 10 per UTC day; the atomic guard, existing historical counts and all other session/request/work/PDF/backend controls remain unchanged.
- Read-only pre-test check: `uploads:2026-11-02` used 3, leaving 7 under the new allowance. No counters were reset or deleted.
- Official URL browser check: anonymous documents 401; admin/admin issued Secure/HttpOnly/SameSite=Strict cookie; server status enabled/entered true; live upload control and nine existing documents displayed.
- Exactly one small fictional PDF uploaded through the official UI: HTTP 202 (not 429), worker Ready, one Docling page and page image HTTP 200. No QA/VLM requests were initiated; worker-internal model usage was not measured.
- Read-only post-test counters: uploads 4/10 (6 remaining); work 12/20 (8 remaining). Other visitors may consume the shared budget subsequently.
- All 75 Vitest tests pass, including the concrete 10-upload allowance, seven remaining after three used, rejection of the next upload and UTC bucket rollover. Lint: zero errors, six existing warnings. Host-managed production build: OK. Separate typecheck and fresh GitHub CI: NOT RUN; not claimed as passed.
- At exhaustion the existing upload error display receives “Daily PDF upload limit (10) reached; resets at 00:00 UTC.” Other files may still be rejected for encryption, exceeding 10 MiB or 30 pages, work/rate caps or upstream controls. The existing Windows tunnel was not changed.

## Disable immediately after the demo (steps)

1. Run the owner-verified Windows command `scripts/emergency-stop.ps1` immediately after the demonstration to block model calls. This command was reported tested by Cursor, not executed from Lovable. Do not restart the current tunnel during the demonstration. Stopping cloudflared afterward is optional additional disconnection; queued jobs require the worker stop mechanism.
2. Set `FINAUDIT_TEMPORARY_DEMO_ENABLED=false` in Lovable Secrets and republish. All demo sessions then fail closed; public sample remains available.
3. Exit demo to revoke the current cookie. Optionally rotate the shared FastAPI token on both Windows and Lovable privately before another demo.

## Final activation and published acceptance — 2026-11-02

- PASS: inspected current synchronized main `b9eb94a`; all three required secrets existed. Created only `FINAUDIT_TEMPORARY_DEMO_ENABLED=true`; existing credentials were not changed or disclosed.
- PASS: authenticated tunnel document list 200 / seven documents, unauthenticated 401. Guard table read 200 and actual service-role budget RPC 200 / reservation true (dedicated probe bucket).
- Upstream controls are **Cursor/owner-reported verification**, not independent Lovable model-cap tests: 40 model calls total, 41st rejected before OpenAI; emergency stop tested and reset; one worker/job; three attempts; no model client retries; 120-second model timeout; 2048 tokens per call; QA repair counted. No Windows server/tunnel changes were made here.
- PASS: existing project publish was scheduled and subsequently confirmed serving the activated session endpoint and real proxy at https://finauditai-cdac.lovable.app. No branch or new project was created.
- PASS: UI admin/admin entry 200; host-only signed demo cookie has Secure, HttpOnly, SameSite=Strict. Wrong password API 401 and unauthenticated proxy 401. UI exit returned to public sample; replay of revoked cookie returned 401.
- PASS: live same-origin list initially contained seven documents. One 2257-byte synthetic_ar_2025.pdf was uploaded through the published intake, automatically opened, progressed from processing to ready, and returned one Docling page with extracted table data. The synthetic upload remains in the shared library (eight documents after upload).
- PASS: original source download 200 / valid PDF; page image 200; subsequent rendered-page check confirmed both thumbnail and full-page images loaded through same-origin proxy. Initial screenshot was taken before images finished; later screenshot confirmed rendering.
- PASS: one real published QA request returned answered with one citation; usage reported OpenAI gpt-4.1-mini-2025-04-14, **llmCalls=1**, 1208 input tokens and 127 output tokens. Citation endpoint returned 200. This is the known newly consumed model-call count; a global counter/remaining total and any worker embedding costs were not independently observable.
- PASS: stored chart interpretation/crop loaded without re-running its model; four comparisons rendered (three matches, one potential discrepancy: East 90 versus 150). This is a synthetic example, not a financial fraud finding.
- PASS: Trends selected the stored synthetic annual reports for 2024/2025 and rendered aligned Revenue values for 2023/2024/2025: 2900/3200/3550 GBP millions, with source-page links. Selecting unrelated default reports correctly showed no aligned values before explicit report selection.
- PASS: captured browser requests showed no configured bearer/signing-secret exposure, no direct tunnel or OpenAI calls; no browser runtime errors in the upload/QA test. This is scoped test evidence, not a full security guarantee.
- PASS: frontend lint zero errors / six existing warnings; all 69 tests passed. Basic security checks found no issues but did not include deep code analysis.
- PASS: host-managed build reported build OK at 2026-11-02T06:10:49Z. NOT RUN: separate fresh typecheck, fresh remote GitHub CI status lookup, Windows restart/persistence, fresh VLM interpretation, independent emergency-stop/41st-call tests. Production successfully served and exercised current code, but that does not substitute for a new CI/typecheck report.
- No missing activation secret or hosted-backend blocker remains at this point-in-time test. Availability still depends on the unchanged short-lived tunnel, Windows services, configured budgets and course window. No monetary total is claimed.

**Publicly known admin/admin is not secure authentication. Any visitor can enter the shared library and spend the bounded demo budget. Use synthetic documents only, never confidential financial reports. Disable immediately after the course using Windows emergency stop, then Project Settings → Secrets → FINAUDIT_TEMPORARY_DEMO_ENABLED → false and Publish → Publish changes.**

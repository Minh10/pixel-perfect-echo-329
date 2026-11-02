# FINAUDIT AI temporary Windows demonstration

Official existing website: https://finauditai-cdac.lovable.app. Keep this Lovable project and GitHub main; do not fork. Nothing in this change activates or publishes live processing.

## What is implemented

- Public Overview, Documents and labelled sample remain available without entry. With live mode off, admin/admin opens only the sample.
- With the server switch on and private configuration complete, admin/admin obtains a signed **one-hour** `__Host-finaudit_demo` cookie: Secure, HttpOnly, SameSite=Strict, Path=/, no Domain. This is a temporary demo session, **not a Cloud user or owner identity**. Anyone knowing the credentials can enter; it does not secure against strangers.
- Every live JSON, job, page image, chart crop, citation, Docling export and PDF download verifies the signature, expiry and durable revocation before forwarding. Exit demo revokes the session, clears its cookie and returns to the sample. The off switch denies these demo cookies immediately after the updated deployment reaches production.
- All existing frontend-used FastAPI routes are already allowlisted. Arbitrary admin routes, encoded/traversal paths, cross-origin mutations, unexpected redirects and invalid parameters are rejected. FastAPI receives only the server-injected bearer token, not the demo cookie. Errors and response headers do not expose upstream authentication details.
- The browser discovers live mode from server-verified status after hydration; no VITE activation flag is required. SSR always renders sample mode; no fictional results are substituted for live results.
- Native PDF/image resources and Range requests remain same-origin. Temporary uploads retain multipart boundaries but are bounded and inspected before forwarding; downloads are streamed.

## Server-only settings in Lovable

Open **Project Settings → Secrets** in this existing project. Never paste token values in chat or commit them.

| Name | Required action |
| --- | --- |
| `FINAUDIT_DEMO_SESSION_SECRET` | Already generated and stored privately. Do not copy or reveal it. |
| `FINAUDIT_BACKEND_URL` | Add the current HTTPS origin only, e.g. `https://strip-conduct-pct-newton.trycloudflare.com`, without `/api/v1`. This reported hostname has not been authenticated or verified here. |
| `FINAUDIT_API_TOKEN` | Privately copy the existing Windows `services/api/.env` bearer token into this secret. It must match the API exactly. Lovable does not have it yet. |
| `FINAUDIT_TEMPORARY_DEMO_ENABLED` | Leave absent or `false` now. Set exactly `true` only after the owner verifies limits and explicitly approves activation/publication. This is the single activation switch. |

`FINAUDIT_AUTHORIZED_USER_ID` is **not required** for temporary demo mode; no account must be created. Retained legacy owner policy is unchanged when the demo switch is off. `VITE_FINAUDIT_SERVICE_MODE` is no longer used to activate live requests. Never put bearer tokens, signing secrets or OpenAI credentials in VITE variables.

OpenAI remains exclusively on Windows FastAPI and its worker (`FINAUDIT_LLM_API_KEY`, configured by that backend); do not add it to Lovable.

## Conservative controls and remaining cost gate

Durable, atomic Lovable Cloud counters apply across server instances, fail closed if unavailable, and cannot be reset by logging out or changing IP. Limits are deliberately global for this one demonstration, not per-user production quotas:

- 10 live entry attempts/minute globally.
- 120 proxied requests/minute globally and 60/minute per signed session.
- 2 work-creating POSTs/minute and 20/day globally, including QA, retrieval, interpretation, indexing and reprocessing. Failed/invalid requests consume the reserved budget too.
- 3 PDF uploads/day globally; one unencrypted PDF per upload, maximum 10 MiB and 30 pages. JSON maximum 16 KiB, questions/queries maximum 2,000 characters, at most four report IDs and retrieval depth five.
- Image DPI 36–150; fixed HTTPS upstream origin and strict path/method/query guards.

These are custom application limits, not a built-in platform limiter. Global ceilings are stronger than an IP quota for this shared demo and do not trust client-supplied IP headers. Counters use UTC minutes/days. There is no automatic counter cleanup yet; session/counter records contain no user identities, tokens or document contents.

**POST limits are not a dollar spending guarantee.** One Docling/index job or QA can trigger multiple embeddings/model calls. Cursor must verify explicit per-job model-call/token caps, worker concurrency and a provider spending cap on Windows before activation. Existing backend has no verified dollar ceiling. Do not claim an unbounded paid service is safe simply because admin/admin is required. No local Windows backend changes were made here.

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

**This published acceptance has not been performed.** Unit tests use controlled fixtures, not the owner's PC. The reported old production proxy 404 is not fixed online until the new code is published and the exact production route is checked.

## Disable immediately after the demo

1. **Stop cloudflared on Windows (Ctrl+C)**: this immediately disconnects the upstream, including in-flight/new network requests where possible. Stop API/worker too if desired; already queued work must be stopped separately to halt its costs.
2. Set `FINAUDIT_TEMPORARY_DEMO_ENABLED=false` in Lovable Secrets and republish. All demo sessions then fail closed; public sample remains available.
3. Exit demo to revoke the current cookie. Optionally rotate the shared FastAPI token on both Windows and Lovable privately before another demo.

## Exact current blockers

- Signing secret and durable guards are provisioned; live switch remains OFF.
- Upstream token and URL are not set in Lovable; Windows runtime/tunnel connectivity and model cost caps remain unverified.
- No real PDF has been processed through the published website by this implementation.
- No new app, account, local backend modification, live activation or publication was performed.
# Deployment

The official FINAUDIT AI frontend is published at https://finauditai-cdac.lovable.app in the existing Lovable project. Lovable Cloud is connected. The real document service is not connected or verified through the published website; the default experience remains an explicitly labelled sample preview. Do not expose FastAPI until `FINAUDIT_API_TOKEN` is set.

## Connection configuration still needed

| Setting                       | Where                                            | Required value / status                                                                                                                                                       |
| ----------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FINAUDIT_BACKEND_URL`        | Lovable project server-side Secrets              | Actual separately hosted HTTPS FastAPI origin, without `/api/v1`, query, credentials, or trailing path. **Not supplied; no backend hostname is known.**                       |
| `FINAUDIT_API_TOKEN`          | Lovable server-side Secrets **and** FastAPI host | The same shared bearer token on both sides. **Not configured.** Never use a `VITE_` name.                                                                                     |
| `FINAUDIT_AUTHORIZED_USER_ID` | Lovable server-side Secrets                      | Exact UUID of the manually created owner Cloud account. **Not configured; no account exists yet.**                                                                            |
| `VITE_FINAUDIT_SERVICE_MODE`  | Frontend deployment configuration                | Leave unset for the sample preview. Set to `proxy` only after private account access and the service are ready. This non-secret mode flag never contains credentials.         |
| `FINAUDIT_LLM_API_KEY`        | FastAPI API and worker host only                 | Actual OpenAI key, read using `FINAUDIT_LLM_API_KEY_ENV=FINAUDIT_LLM_API_KEY`. **Not supplied or verified.** Lovable does not need this key because FastAPI owns model calls. |

The frontend now ignores `VITE_FINAUDIT_API_URL`; a browser must never bypass the secure proxy. Requests use `/api/document-service/api/v1/...` on the app's own origin. The server validates Cloud authentication, checks the exact authorized user, allows only existing document-tool paths, and injects the FastAPI bearer token. PDF requests are streamed; background processing, progress and results remain owned by the FastAPI worker and Docling. Service errors are not fabricated as results. New proxy code uses supported TanStack server routes, not a new separate Edge Function.

### Public demo and private access activation

The website opens directly into the existing public Overview and sample workspace. Optional **Demo entry** at `/login` accepts the publicly guessable `admin` / `admin` combination and opens the existing sample report; **Exit demo** clears only a tab-local sample-entry flag and returns to Overview. Visitors can continue without entry. There is no signup, account creation or account-management UI; `/reset-password` still redirects to Overview. The header does not query or renew an owner session. Proxy mode remains off.

**This is NOT secure authentication.** Demo entry writes no auth cookies, creates no Cloud identity, calls no real login function and never grants access to private documents, the privileged proxy or paid OpenAI operations. Its browser-only presentation state is never read by server authorization. It is available only in sample mode; it is not a substitute for live access control. Do not treat `admin/admin` as a private credential or save it as a server secret.

Single-user demo mode describes the visible sample experience only. It does not identify anonymous visitors as the owner, provision an account, mint a privileged session or bypass any server check. Private paid PDF/OpenAI operations remain unavailable.

**Access blocker:** non-interactive owner-only access, such as a private network or identity-aware hosting edge, has not been implemented or verified. Before enabling private processing, enforce that access on every JSON request, PDF image, chart crop, source download and paid operation. Do not trust unsigned identity headers, a public mode flag or a globally privileged browser session. Existing Cloud authentication and exact-owner checks remain intact; they are not replaced by demo mode or by merely proposing edge access.

**Provider blocker:** email/password authentication has been enabled. Public signup has **not** been confirmed disabled: the available configuration tool replaces several settings together and a safe read of the current HIBP setting is unavailable. Set **More → Users → Auth settings → Disable sign-up** before activation. This changes the provider, not just the interface. Confirm the hosted settings report signup disabled and an anonymous signup attempt is rejected. The application's owner UUID check denies every other account regardless, but is not a substitute for this provider setting.

The retained server authentication code uses `__Host-finaudit_access` and `__Host-finaudit_refresh` cookies with **Secure, HttpOnly, SameSite=Lax, Path=/** and no Domain. The proxy still revalidates the access cookie with Cloud Auth and the exact owner UUID for every private resource. This code is retained as a fail-closed safeguard, not an active login experience or a verified non-interactive access solution.

Do not enable proxy mode until non-interactive owner-only access is implemented and verified on the published HTTPS site and the actual FastAPI backend is reachable. A direct request without authentication returns 401 even before backend configuration. Backend-unavailable responses remain honest errors; no sample values are mixed into private results.

After configuring secrets, publish the existing application again to make them available in production. Then upload a real financial PDF through the published intake, confirm the job completes, pages and citations load, and source images/PDFs read back securely. This acceptance test has **not** been performed; online PDF processing is **not claimed**.

## What has to stay private

The document API accepts PDF uploads and returns parsed tables, page images, and chart readings. It has no user accounts. CORS is not access control.

- `scripts/start_api.py` listens on `127.0.0.1:8000`.
- `docker-compose.yml` publishes API port 8000 and Qdrant port 6333 on `127.0.0.1` only. Inside the container, uvicorn listens on `0.0.0.0` so the port mapping can reach it. Do not change the host side of that mapping to `0.0.0.0`.
- When `FINAUDIT_API_TOKEN` is set, every `/api/v1` route except `GET /api/v1/health` requires `Authorization: Bearer <token>`. Health stays open so a private probe can run.
- Do not put the token in `VITE_` variables. A Vite variable is shipped in the browser bundle. The browser should talk only to a same-origin proxy that adds the header on the server.

The OpenAI key is `FINAUDIT_LLM_API_KEY` on the API and the worker. The provider used for the verified chart readings is `openai`, model `gpt-4.1-mini`, base URL `https://api.openai.com/v1`. The key is read from the environment named by `FINAUDIT_LLM_API_KEY_ENV`. It is never a request field and must not be committed.

## Processes

| Process           | Command                                                                            | Storage                                                                                               |
| ----------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| API               | `uvicorn app.main:app` via `scripts/start_api.py`, or the `api` service in Compose | `FINAUDIT_DATA_DIR` (SQLite, PDFs, renders)                                                           |
| Worker            | `python -m app.worker`                                                             | The same data directory. It claims parse and index jobs.                                              |
| Qdrant            | Compose service, or `FINAUDIT_QDRANT_URL`                                          | Required when the API and the worker are separate processes. Embedded Qdrant allows one process only. |
| UI + secure proxy | Existing Lovable TanStack Start application                                        | Server-side secrets; no replacement document store                                                    |

Compose already runs the API, one worker, and Qdrant on one named volume (`finaudit-data`) plus `qdrant-data`. That is the persistent layout. Back up both volumes. SQLite is in the data volume.

Set these in `services/api/.env` (gitignored) or the process environment, not in the image:

```text
FINAUDIT_PARSER=docling
FINAUDIT_DATA_DIR=/data
FINAUDIT_QDRANT_URL=http://qdrant:6333
FINAUDIT_API_TOKEN=<long random secret>
FINAUDIT_LLM_PROVIDER=openai
FINAUDIT_LLM_MODEL=gpt-4.1-mini
FINAUDIT_LLM_BASE_URL=https://api.openai.com/v1
FINAUDIT_LLM_API_KEY=<server-side key>
FINAUDIT_CORS_ORIGINS=["https://<your-ui-origin>"]
```

Build the image from `services/api` with the Dockerfile. It installs CPU torch, the API, and can preload Docling weights and the MiniLM embedder. The worker uses the same image and a different command.

## Lovable

The UI is linked to the existing Lovable project `282cd50e-8aed-48da-9ff2-43355f4aa3d5`. Lovable commits to GitHub `main` and reads `main` back.

1. Push this `main` first.
2. In that Lovable project, sync from GitHub before writing another prompt.
3. Do not create a second Lovable project.

Lovable hosts the frontend and its server-side proxy. FastAPI, Docling, the worker, persistent data volumes and Qdrant remain separately hosted. No second project or replacement AI processing workflow is needed.

## Not done

- No real FastAPI hostname, shared bearer token or authorized account has been configured.
- No real-PDF end-to-end test has been run through the published app.
- Non-interactive owner-only access is not implemented or verified. The retained proxy still requires a real authenticated owner; anonymous demo visitors cannot use it.
- FastAPI has no per-tenant isolation; the single-user proxy must never grant additional accounts access.

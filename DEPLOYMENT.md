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

### Private access implementation and activation

`/login` implements email/password sign-in only. Sign-in is checked server-side against exactly `FINAUDIT_AUTHORIZED_USER_ID`, and no profile table or public signup UI is needed. `/reset-password` supports emailed recovery. The public sample remains accessible and proxy mode remains off.

**Account blocker:** no Cloud auth users exist. Create your single owner account through **More → Users → Add user → Create new user**, then store its UUID as `FINAUDIT_AUTHORIZED_USER_ID` in server-side Secrets. Do not invent a UUID or authorize the first arbitrary registrant.

**Provider blocker:** email/password authentication has been enabled. Public signup has **not** been confirmed disabled: the available configuration tool replaces several settings together and a safe read of the current HIBP setting is unavailable. Set **More → Users → Auth settings → Disable sign-up** before activation. This changes the provider, not just the interface. Confirm the hosted settings report signup disabled and an anonymous signup attempt is rejected. The application's owner UUID check denies every other account regardless, but is not a substitute for this provider setting.

Sign-in issues `__Host-finaudit_access` and `__Host-finaudit_refresh` cookies with **Secure, HttpOnly, SameSite=Lax, Path=/** and no Domain. Access expires with the provider token; the refresh cookie lasts at most seven days. The header renews an expired access token through a same-origin server request while the app is open. Native PDF page images, chart crops and original-PDF downloads automatically send the same cookie; no token goes in a resource URL or sign-in response. The proxy revalidates each request with Cloud Auth and the owner UUID. Logout revokes the provider session and clears both cookies; cached queries are cancelled and cleared. HTTPS is required (browsers permit secure cookies on localhost for development).

Do not enable proxy mode until owner login, renewal, logout and resource access are tested on the published HTTPS site and the actual FastAPI backend is reachable. A direct request without authentication returns 401 even before backend configuration. Backend-unavailable responses remain honest errors; no sample values are mixed into private results.

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
- Owner-account creation, owner UUID configuration and provider signup restriction are pending; authenticated end-to-end checks cannot run until the owner exists.
- FastAPI has no per-tenant isolation; the single-user proxy must never grant additional accounts access.

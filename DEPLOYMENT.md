# Deployment

FINAUDIT AI is not deployed on a public URL. This guide is the supported way to host it. Do not put the FastAPI process on the public internet until `FINAUDIT_API_TOKEN` is set and an end-to-end check against that URL has passed. That check has not been done.

## What has to stay private

The document API accepts PDF uploads and returns parsed tables, page images, and chart readings. It has no user accounts. CORS is not access control.

- `scripts/start_api.py` listens on `127.0.0.1:8000`.
- `docker-compose.yml` publishes API port 8000 and Qdrant port 6333 on `127.0.0.1` only. Inside the container, uvicorn listens on `0.0.0.0` so the port mapping can reach it. Do not change the host side of that mapping to `0.0.0.0`.
- When `FINAUDIT_API_TOKEN` is set, every `/api/v1` route except `GET /api/v1/health` requires `Authorization: Bearer <token>`. Health stays open so a private probe can run.
- Do not put the token in `VITE_` variables. A Vite variable is shipped in the browser bundle. The browser should talk only to a same-origin proxy that adds the header on the server.

The OpenAI key is `FINAUDIT_LLM_API_KEY` on the API and the worker. The provider used for the verified chart readings is `openai`, model `gpt-4.1-mini`, base URL `https://api.openai.com/v1`. The key is read from the environment named by `FINAUDIT_LLM_API_KEY_ENV`. It is never a request field and must not be committed.

## Processes

| Process | Command | Storage |
|---|---|---|
| API | `uvicorn app.main:app` via `scripts/start_api.py`, or the `api` service in Compose | `FINAUDIT_DATA_DIR` (SQLite, PDFs, renders) |
| Worker | `python -m app.worker` | The same data directory. It claims parse and index jobs. |
| Qdrant | Compose service, or `FINAUDIT_QDRANT_URL` | Required when the API and the worker are separate processes. Embedded Qdrant allows one process only. |
| UI | `npm run build`, then serve the static `dist/` from a host that can reach the API | No document store of its own |

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

Lovable hosting, if used later, publishes the frontend only. Point it at an API that already requires `FINAUDIT_API_TOKEN`, through a proxy that holds the token. Until that proxy and a public URL are tested, the product is local.

## Not done

- No public hostname has been assigned.
- No end-to-end test has been run against a public URL.
- There are no user accounts and no per-tenant isolation.
- A reverse proxy that injects the bearer token is described here and is not included as a running service.

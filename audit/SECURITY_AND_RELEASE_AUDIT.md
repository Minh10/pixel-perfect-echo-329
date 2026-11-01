# Security and release audit (PR #2 @ `ed9e7e2`)

**Release posture:** acceptable for **local, single-user development only** (the documented posture: Compose binds to 127.0.0.1). It is **not** acceptable for any shared or network-exposed deployment until S-1 is resolved. The AI-correctness findings in `AI_VALIDATION_REPORT.md` separately block Milestone 4.

## Executed checks

| Check | Method | Result | Evidence |
|---|---|---|---|
| Secrets in git history | Pattern scan of every commit reachable from PR #2 (31 commits): Anthropic, AWS, GitHub and Slack key formats, private keys, `api_key=…` literals; tracked `.env`/`.pem`/credential files | **None found** | transcript; reproducible with the regex in this report's appendix |
| Secrets in the frontend bundle config | Search for `VITE_*KEY/TOKEN/SECRET` | **None.** Only `VITE_FINAUDIT_API_URL` | — |
| Credential handling in code | Review of every `os.environ` read | LLM, embedder and Qdrant keys are read only from server-side env vars *named* in config. The Anthropic client is built with an explicit key and base URL (no ambient-credential fallback) | `app/qa/llm.py`, `retrieval/embeddings.py`, `indexing/vectors.py` |
| Runtime probes (13) | `eval/audit/security_probe.py` against an in-process API | **13/13 pass** | `artifacts/security_probe.txt` |
| Python dependencies | PyPI JSON vulnerability data for all 154 installed distributions | **0 known vulnerabilities** (0 lookup errors). Note: OSV (api.osv.dev) was unreachable, so PyPI's OSV-derived data was used | `artifacts/backend_pypi_vulnerability_lookup.txt` |
| Frontend dependencies | `bun audit` on the committed `bun.lock` | **28 advisories (1 critical, 14 high, 12 moderate, 1 low). All pre-existing:** `bun.lock` is unchanged by PR #2 | `artifacts/frontend_bun_audit.txt` |
| XSS sinks | Search for `dangerouslySetInnerHTML` outside the generated `components/ui` | None. Evidence text is rendered as React text | — |

What the 13 runtime probes cover:
- CRLF/quote upload filename stored percent-encoded, and served via RFC 5987 `filename*` (no header injection);
- path traversal via document and block IDs → 404;
- out-of-range pages → 404;
- DPI clamped;
- CORS refuses an unknown origin;
- a configured key value is never echoed by `/index/status`, `/health`, `/qa` errors or `/openapi.json`;
- question length, `k` and method enums are enforced (422).

## Findings

| ID | Severity | Finding | Recommendation |
|---|---|---|---|
| S-1 | **High** (for any non-local deployment) | **No authentication, authorisation or rate limiting.** That includes `DELETE /documents/{id}`, uploads and **`POST /qa`, which spends LLM tokens per call (up to 2 calls, ~24k chars of evidence each)**. Mitigation today: Compose publishes ports on 127.0.0.1 only; native uvicorn binds localhost by default | Add auth (at least an API key or OIDC at a gateway) and per-client rate and cost limits before exposure. Keep the localhost binding as the default |
| S-2 | Medium | **Prompt injection:** retrieved PDF text is placed verbatim in the LLM prompt. Numbers are validated, but **non-numeric claims in `answer` are not** (e.g. an injected sentence such as "this filing is fraudulent" would pass validation) | Delimit evidence as data and tell the model to ignore instructions inside it; post-validate answer text with an allow-list of claim types, or render only structured fields for high-stakes use; add an injection fixture test |
| S-3 | Medium | Frontend advisories in **runtime** paths: `seroval` 1.6.8 (TanStack SSR serialisation; moderate code/script-injection advisories, fixed ≥ 1.6.11); `zod` 3.25.76/4.6.5 (high, memory exhaustion on oversized constrained collections, fixed 4.6.6) | `bun audit fix` within ranges; re-run tests and build |
| S-4 | Low | Frontend advisories in **dev-only** tooling: `shell-quote` (critical, via devtools → `launch-editor`), Vite 8.1.5 dev-server issues, `brace-expansion`, `minimatch`, `js-yaml`, `nanoid`, `source-map-js` | Upgrade. Never expose the Vite dev server beyond localhost |
| S-5 | Low | Internal exception text (`TypeName: message`) is stored in job errors and returned by `/jobs/{id}`, which may reveal file paths | Return a generic message plus a correlation id; log details server-side |
| S-6 | Low | Upload validation reads the whole file into memory (≤ `FINAUDIT_MAX_UPLOAD_MB`, default 100 MB) per request | Keep the streaming size limit (present); consider opening by path with retry, or lowering the limit |
| S-7 | Low | MuPDF and Docling parse untrusted PDFs in-process (the worker runs as non-root `finaudit` in Docker, which is good) | Add CPU and memory limits to the worker container; consider sandboxing the parser |
| S-8 | Info | Qdrant runs without an API key (Compose, localhost-bound) | Set `FINAUDIT_QDRANT_API_KEY` when not localhost |

## Release-engineering findings

| ID | Severity | Finding | Action taken / recommendation |
|---|---|---|---|
| R-1 | **High** | No CI at all (no `.github/`) | **Added** `.github/workflows/ci.yml` (see below). Not yet observed running on GitHub |
| R-2 | Medium | Real Docling extraction never verified (HuggingFace unreachable from the dev environment) | Run `eval/ingest_corpus.py --parser docling` where model download is possible; compare with `run_retrieval_eval.py` |
| R-3 | Medium | LLM path never exercised live (no credentials supplied) | Run `eval/run_qa_eval.py` and `eval/audit/qa_audit.py` with a configured provider before release |
| R-4 | Low | `numpy==2.4.6` pinned in `pyproject.toml`; all tests ran on 2.5.4 | Run CI on the pinned set (the workflow installs from `pyproject.toml`) |
| R-5 | Low | API contract drift: TS `JobStage` lacks `indexing` | Add it to `src/lib/api/types.ts`; the CI contract step fails until then (intentional) |
| R-6 | Medium | Test coverage gaps: real-filing validator cases; frontend error, deep-link and Analysis states | Freeze `validation_audit.py` cases as tests; add Vitest/RTL tests for `http-service` and `analysis.tsx` |

### CI workflow added (`.github/workflows/ci.yml`)

1. **Backend** (Python 3.12, CPU torch, pinned model fetch):
   - `pytest -m "not docling_models"`, including the 9 strict-xfail reproductions in `tests/audit/`;
   - an **OpenAPI drift** check against `docs/openapi.json`;
   - the **API contract** check (`eval/audit/contract_check.py --strict`).
2. **Frontend:** `bun install --frozen-lockfile`, `tsc --noEmit`, `lint`, `test`, `build`.
3. **Dependency audit** (informational): `bun audit`, `pip-audit`.

No secrets are needed, and no LLM evaluation runs in CI.

**Expected first result:** the backend job fails at the contract step (R-5) until `JobStage` is fixed. Everything else passed locally.

## Appendix: secret-scan pattern

```
sk-ant-[A-Za-z0-9]|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE)|ghp_[A-Za-z0-9]{20}|xox[bp]-|(api[_-]?key|secret|password)\s*[:=]\s*['"][A-Za-z0-9/+_-]{16,}
```

Applied to `git log -p HEAD`.

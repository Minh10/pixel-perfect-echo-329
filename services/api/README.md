# FINAUDIT AI — Backend API (`services/api`)

FastAPI service for **financial PDF ingestion, layout-aware parsing, evidence provenance, layout-aware
retrieval and evidence-grounded QA**. It is independent of the Lovable/TanStack frontend in the repository
root and implements the contract behind `src/lib/api/service.ts` (`FinAuditService`).

- **Milestone 1:** upload → validation → background parsing (Docling, PyMuPDF) → pages, blocks, tables,
  figure regions and evidence candidates, each with page/bbox provenance.
- **Milestone 3:** layout-aware chunking and indexing (SQLite FTS5 + Qdrant), retrieval baselines
  B1–B4, LLM question answering with deterministic validated calculations, citations and abstention,
  and chart interpretation as visual estimates. Design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
  Benchmark and results: [`eval/README.md`](eval/README.md).
- **Out of scope:** financial discrepancy auditing (next phase). The API never returns invented values
  or confidence scores; `Evidence.extracted` stays `null`.

## Architecture

```
            multipart upload                       poll (SQLite, atomic claim)
 frontend ──────────────► FastAPI (app.main) ──► jobs table ◄────────── worker (app.worker) ×N
    ▲                          │  validate (PyMuPDF)                     │ inspect pages  (PyMuPDF)
    │  JSON / PNG              │  store source.pdf + sha256              │ parse          (Docling | PyMuPDF)
    └──────────────────────────┤                                         │ assemble       (ids, provenance, evidence)
                               └──── data/documents/{id}/ ◄──────────────┘ persist parse.json, docling.json
```

| Concern | Design |
|---|---|
| API | FastAPI, versioned under `/api/v1`, camelCase JSON, uniform error envelope `{"error":{"code","message"}}` |
| Schemas | Pydantic v2 in `app/schemas.py`, a superset of `src/lib/api/types.ts`; OpenAPI in `docs/openapi.json` |
| Metadata store | SQLite (WAL) in `app/storage/db.py`: `documents` and `jobs` tables behind a small repository class (Postgres-ready interface) |
| File store | `data/documents/{id}/source.pdf` (original bytes), `parse.json` (served output), `docling.json` (raw Docling export), `renders/` (PNG cache) |
| Background work | Separate worker process(es) that claim jobs with a single atomic `UPDATE … RETURNING`. A heartbeat thread runs during parsing. Stale jobs are re-queued, and fail after `JOB_MAX_ATTEMPTS`. Unexpected errors retry; configuration and parse errors fail immediately |
| Parsing | `docling` (default): layout model + TableFormer, optional picture classifier. `pymupdf`: deterministic text layer + `find_tables` + image/vector regions, no ML. `auto`: Docling, falling back to PyMuPDF with a warning stored on the document |
| Provenance | Every block and evidence item carries `documentId, sourceSha256, page, bbox (pt, top-left), bboxNormalized, pageWidth/Height, charspan, sourceRef (Docling self_ref), parser, parserVersion, method, jobId` |

## API (v1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness, configured parser, library versions |
| POST | `/api/v1/documents` | Multipart `file` (+ optional `title`, `issuer`, `period`, `type`; query `parser`). Returns **202** `{document, job}` |
| GET | `/api/v1/documents` | `FinDocument[]`, newest first |
| GET | `/api/v1/documents/{id}` | `FinDocument` (status `processing`/`ready`/`failed`, `error`, `warnings`, `parser`) |
| DELETE | `/api/v1/documents/{id}` | 204. Returns 409 while a job is running |
| POST | `/api/v1/documents/{id}/reprocess` | Queue a new job (optional `?parser=`); 409 if one is active |
| GET | `/api/v1/documents/{id}/job` | Latest job for the document |
| GET | `/api/v1/jobs/{jobId}` | Job `state`, `stage`, `progress` (0..1, per-page with Docling), `attempts`, `error` |
| GET | `/api/v1/documents/{id}/pages` | `DocumentPage[]`; `[]` with header `X-Document-Status` if not ready |
| GET | `/api/v1/documents/{id}/pages/{n}` | One page (409 if not ready) |
| GET | `/api/v1/documents/{id}/evidence` | `Evidence[]`, filters `?page=` and `?category=table\|figure\|disclosure` |
| GET | `/api/v1/documents/{id}/pages/{n}/image` | PNG render of the original page (`?dpi=`, max 300) |
| GET | `/api/v1/documents/{id}/blocks/{blockId}/image` | PNG crop of a block's bbox (figures, charts, tables) |
| GET | `/api/v1/documents/{id}/source` | Original PDF (`X-Content-SHA256`) |
| GET | `/api/v1/documents/{id}/export/docling` | Raw DoclingDocument JSON (404 if the document was not parsed by Docling) |

### Milestone 3: indexing, retrieval, QA, visual

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/documents/{id}/index` | Queue deterministic (re-)indexing (202 `Job`); 409 if one is active. Indexing also runs automatically after each parse (`FINAUDIT_AUTO_INDEX`) |
| GET | `/api/v1/documents/{id}/index` | Index runs per chunk set (version, embedder, counts, dense status) + latest index job |
| GET | `/api/v1/index/status` | Embedder / vector store / LLM availability and chunk counts (no secrets) |
| POST | `/api/v1/retrieve` | `{query, documentIds?, method: bm25\|dense\|hybrid, chunkSet: layout\|flat, k, rerank}` → ranked evidence with page/block/bbox citations |
| GET | `/api/v1/citations/{chunkId}` | Full cited chunk: text, section path, regions, table units/columns, image URLs, provenance |
| POST | `/api/v1/qa` | `{question, documentIds?, topK?}` → answer or abstention, exact value, operands, calculations, citations, usage. Returns 503 `llm_unavailable` without a provider |
| POST | `/api/v1/documents/{id}/figures/{blockId}/interpret` | VLM chart reading (all values `visual_estimate`) + table cross-check; cached |
| GET | `/api/v1/documents/{id}/figures/{blockId}/interpretation` | Cached chart reading |

Interactive docs are at `http://localhost:8000/docs` when the server is running.

Upload errors: `400 empty_file`, `413 file_too_large`, `415 not_a_pdf`,
`422 corrupt_pdf | encrypted_pdf | no_pages | too_many_pages | invalid_request`.
Job error codes: `parser_unavailable`, `parse_failed`, `internal_error`, `worker_lost`, `document_deleted`.

## Local development

### Option A: Docker (recommended)

```bash
cd services/api
cp .env.example .env
docker compose up --build
```

The image installs CPU-only torch and pre-downloads the Docling layout, TableFormer and
picture-classifier weights to `/opt/docling-models` (`FINAUDIT_DOCLING_ARTIFACTS_PATH`), so containers then run offline. The build
needs access to `download.pytorch.org`, `pypi.org` and `huggingface.co`.
Build args for restricted networks:

| Build arg | Default | Use |
|---|---|---|
| `PYTHON_IMAGE` | `python:3.12-slim` | Registry mirror, e.g. `mirror.gcr.io/library/python:3.12-slim` |
| `TORCH_INDEX_URL` | `https://download.pytorch.org/whl/cpu` | `https://pypi.org/simple` if the PyTorch index is blocked (larger image) |
| `DOCLING_PRELOAD_MODELS` | `true` | `false` to skip model download. Then use `FINAUDIT_PARSER=pymupdf` or `auto` |

Scale workers with `docker compose up --scale worker=2`. Run the tests in the container with
`docker compose run --rm api pytest`.

### Option B: Native Python (3.11–3.13)

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision   # optional: CPU-only torch
pip install -e ".[dev]"
docling-tools models download layout tableformer picture_classifier -o ./models     # optional, else lazy download
export FINAUDIT_DOCLING_ARTIFACTS_PATH=$PWD/models
```

```bash
uvicorn app.main:app --reload --port 8000
```

```bash
python -m app.worker
```

Run the API and the worker in separate terminals. Without Docling weights, set
`FINAUDIT_PARSER=pymupdf` (or `auto`) so jobs do not fail with `parser_unavailable`.

### Retrieval and QA prerequisites

```bash
python -m app.retrieval.fetch_models
```

This fetches the default embedder (all-MiniLM-L6-v2 ONNX, checksum-pinned) into `./models`.
Without it, dense and hybrid retrieval degrade to BM25 and report it.

For QA, set an LLM provider in `.env` (see `.env.example`): `FINAUDIT_LLM_PROVIDER`,
`FINAUDIT_LLM_MODEL` and the key env var. With API and worker as separate native processes, run a
Qdrant server and set `FINAUDIT_QDRANT_URL`. Embedded Qdrant mode allows only one process.

### Tests

```bash
pytest
```

```bash
pytest -m "not docling_models"
```

The first command runs everything. Tests that need real Docling model weights skip automatically
when the weights cannot be loaded; the second command excludes them explicitly. To regenerate the
synthetic fixture PDFs (deterministic output):

```bash
python tests/fixtures/generate_fixtures.py
```

Fixtures (`tests/fixtures/`) are **synthetic** documents for a fictional issuer. Each has a
`*.layout.json` with the exact coordinates the generator drew, so tests check page numbers and
bounding boxes as well as text:

| Fixture | Purpose |
|---|---|
| `annual_report_excerpt.pdf` | 3 pages: title, narrative with numbers, ruled income-statement table + caption, raster bar chart + caption |
| `scanned_statement.pdf` | Image-only page: no text layer, must be flagged rather than "read" |
| `encrypted.pdf`, `truncated.pdf`, `corrupt.pdf`, `not_a_pdf.txt` | Validation rejections |

## Configuration

All settings are environment variables prefixed `FINAUDIT_` (see `.env.example` and `app/config.py`).
The main ones are `FINAUDIT_PARSER`, `FINAUDIT_DATA_DIR`, `FINAUDIT_MAX_UPLOAD_MB`,
`FINAUDIT_MAX_PAGES`, `FINAUDIT_CORS_ORIGINS`, `FINAUDIT_DOCLING_DO_OCR`,
`FINAUDIT_DOCLING_PICTURE_CLASSIFICATION` and `FINAUDIT_DOCLING_ARTIFACTS_PATH`
(pre-downloaded weights; ignored if the directory is empty or missing).

## Known limitations

- SQLite plus a shared volume suits a single host. For multi-host deployment, move the repository to
  Postgres (same interface) and the file store to object storage.
- No authentication or authorisation, and no per-tenant isolation yet.
- OCR is off by default. Scanned pages are flagged (`hasTextLayer: false` plus a document warning)
  but yield no text until `FINAUDIT_DOCLING_DO_OCR=true`, which needs OCR model weights.
- Chart values exist only as VLM *visual estimates* (`/figures/{id}/interpret`), never as reported
  figures. Without a configured vision-capable LLM, charts are figure regions with crops and captions.
- PyMuPDF fallback: headings come from a font-size / bold+body-size heuristic, and tables are found
  from ruling lines (`find_tables`), so borderless tables are often missed. Every block's
  `provenance.method` states this. The Milestone 3 benchmark corpus was parsed with PyMuPDF because
  Docling's model weights were unreachable in the development environment.
- Evidence "disclosure" candidates are selected by a documented regex rule
  (`detection.rule`). They are not verified facts.
- Pages with non-zero `/Rotate` are rendered correctly, but bbox alignment on rotated pages has not
  been verified with fixtures.
- Re-processing replaces the previous parse; block IDs (`p{page}-b{nnn}`) are stable only for the
  same parser and options.

### Milestone 3 (retrieval / QA)

- **The QA pipeline has not been evaluated end to end.** No LLM credentials were available in the
  development environment. Its validation and calculation logic is covered by tests with a scripted
  test double, and `eval/run_qa_eval.py` is ready to run once a provider is configured.
- Retrieval quality is modest: Recall@10 of about 0.4–0.57 when the gold document is known (see
  `eval/results/retrieval_report.md`). Numerical and multi-page questions are the weakest. After
  multiple-comparison correction, differences between configurations are not significant on this
  63-query benchmark.
- Hybrid fusion and reranking have not shown measurable gains here. The reranker is pluggable but was
  not evaluated (no weights reachable). ColPali-style visual retrieval was investigated but not
  implemented (see `docs/ARCHITECTURE.md`).
- Embedded Qdrant (no `FINAUDIT_QDRANT_URL`) allows a single process only. Qdrant server mode is
  configured in Compose but was not exercised in the development environment.
- Document routing matches issuer names and years from document metadata. Abbreviations that aren't
  in the metadata (e.g. "AMEX") fall back to whole-corpus retrieval, with a warning.
- Table period recovery is conservative: periods printed above a table are used only when their count
  matches the value columns exactly. Otherwise values stay unlabelled (the title keeps the period text).

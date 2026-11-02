# FINAUDIT backend architecture (Milestones 1–3)

```
 PDF upload ─► validate (PyMuPDF) ─► jobs(kind=parse) ─► worker: inspect + parse (Docling | PyMuPDF)
                                                          │   parse.json (pages, blocks, bbox provenance)
                                                          ▼
                                        jobs(kind=index) ─► worker: chunk (layout + flat)
                                                          │   ├─ SQLite: chunks, chunks_fts (BM25), index_runs
                                                          │   └─ embed ─► Qdrant (vectors + chunk ids only)
                                                          ▼
 POST /retrieve ─► Retriever: BM25 | dense | RRF hybrid [+ optional reranker] ─► ranked chunks + citations
 POST /qa ──────► route docs ─► retrieve ─► LLM structured plan ─► validate + Decimal calculator ─► answer | abstain
 POST /figures/{block}/interpret ─► crop ─► VLM structured reading (visual_estimate) ─► table cross-check
```

## Data model

| Store | Contents | Notes |
|---|---|---|
| SQLite `documents`, `jobs` | metadata, job queue (`kind` = parse/index) | M1. Atomic claim and heartbeats; migration adds `jobs.kind` |
| `documents/{id}/parse.json` | `ParseResult`: pages, blocks, tables, figures, provenance | M1. Source of truth for chunking |
| SQLite `chunks` | chunk text, `search_text`, section path, pages, source blocks (page/blockId/bbox), table/figure metadata, parser + parse-job provenance, `index_version` | M3. Structured store; FK → documents (cascade) |
| SQLite `chunks_fts` (FTS5) | analyzed tokens for BM25 | The trigger deletes FTS rows with their chunk, including FK cascades |
| SQLite `index_runs` | per (document, chunk set): version, embedder id, counts, dense status, timing | Status endpoint |
| SQLite `chart_interpretations` | cached VLM chart readings + table checks | Cascade on document delete |
| Qdrant `finaudit_{chunkSet}_{embedderId}` | vectors, payload `{chunk_id, document_id, kind, page}` | One collection per embedder, so models are never mixed |

## Chunking (`app/indexing/chunker.py`, version `layout-v3`; tables serialised from FinancialFacts — see FINANCIAL_EVIDENCE_SCHEMA.md)

- **text:** consecutive body blocks under one section on one page, up to ~220 words. A block is never
  split unless it alone exceeds the budget; it is then split at sentence boundaries. Running
  headers/footers (short lines repeated on ≥ 30% of pages) and page numbers are dropped.
- **table:** a normalised table view. Currency-symbol cells (`$`) are merged into their numbers, empty
  spacer columns are dropped, and leading rows with no non-year numbers become column headers (the
  periods). A header row may contain no non-year numbers, whatever the parser flagged (the v1 bug).
  When a table has no header row, periods printed above it are used only if their count exactly
  matches the value columns. Units come from the caption, headers, first rows or preceding text (`(Millions)`,
  `in thousands`, ...). Rows serialise as `Label: 2018 = (1,577); 2017 = (1,373)`. Tables over ~320
  words split into row groups, preferably at section rows (`[Cash Flows from Investing Activities]`),
  and **every group repeats the title, units and column headers**. Row-group citations carry the bbox
  of exactly those rows.
- **figure:** caption, parser classification (when Docling's classifier is on) and neighbouring text,
  plus a crop URL. Figure values are *not* in the text; see Visual RAG below.
- **flat (baseline, `flat-v1`):** 200-word windows with stride 150 over the raw page text layer. They
  carry the same document header line (company · period · type · title) as layout chunks, so a B1-vs-B3
  difference measures structure and not metadata.
- **Docling vs PyMuPDF:** the chunker consumes the parser-neutral `ParseResult`, so Docling's roles
  (`section_header` levels, `caption`, `page_header`/`footer`, TableFormer cells with header flags) are
  used directly when Docling parsed the document. PyMuPDF parses get heuristic roles: a font-size or
  bold+body-size heading rule and ruling-line tables.

**Determinism and versioning.** Chunk id = `sha256(document_id | chunker_version | kind | page | block
ids | part)`. Indexing replaces all chunks and vectors of `(document, chunk set)` in one transaction
or filter-delete, then reinserts. Re-indexing therefore yields identical ids and never duplicates
evidence (tested). Changing the chunker bumps `CHUNKER_VERSION`; changing the embedder writes to a new
collection.

## Retrieval (`app/retrieval/search.py`)

| Name | Method | Chunks |
|---|---|---|
| B1 | BM25 (FTS5, k1=1.2, b=0.75; Porter stemming; `1,577`→`1577`, `12.4`→`12_4`) | flat |
| B2 | dense (cosine, Qdrant) | flat |
| B3 | BM25 | layout |
| B4 | hybrid: RRF(k=60) over BM25 + dense top-50 | layout |

Dense and hybrid degrade to BM25 with an explicit warning when the embedder or Qdrant is unavailable.
A reranker (`FINAUDIT_RERANKER=cross-encoder`, sentence-transformers `CrossEncoder`) is pluggable, off
by default, and reported separately. It was **not evaluated**: no reranker weights are reachable from
the development environment.

## QA (`app/qa/`)

1. **Route:** match issuer names (suffix-normalised, whole-word for short names) and years against
   document metadata. Explicit `documentIds` override this; with no match the whole corpus is searched,
   with a warning.
2. **Retrieve:** `qa_method`/`qa_chunk_set`/`qa_top_k` (default **dense**/layout/8). Dense had the
   best point estimates among layout configurations; hybrid RRF showed no measured benefit (see
   `eval/README.md`). Dense falls back to BM25 with a warning when the embedder is unavailable.
3. **Prompt:** evidence is labelled `[E#] TABLE|TEXT|FIGURE | company | period | page | section`. The
   rules: use only the evidence, abstain when it is insufficient, quote numbers verbatim, never do
   arithmetic, prefer tables over narrative and over visual estimates.
4. **Structured output** (`PLAN_SCHEMA`, strict JSON schema): status, answer, citations (with quotes),
   operands (`quote`, `scale`, `value_kind`), calculation steps (whitelisted ops) and `final.ref`.
5. **Validation in code:**
   - cited ids exist and quotes are verbatim;
   - each operand quote is verbatim in its evidence and contains exactly one number;
   - chart-derived operands must be `visual_estimate`;
   - the calculation plan is valid (ops whitelist, arity, earlier-only references, no division by zero,
     scale compatibility);
   - `final.ref` exists;
   - every number in the answer text is grounded in cited evidence, an operand, or a (rounded or
     rescaled) calculation result.

   On failure the model gets one repair round with the failed checks; after that the pipeline abstains
   (`validation_failed`).
6. **Response:** answer, exact `value` (from the calculator or operand, with `valueKind`
   reported/calculated/visual_estimate), operands, calculations, citations with page/block/bbox and
   workspace evidence ids, abstention reason, usage (tokens; cost only when prices are configured), and
   timings. **There is no confidence score.**

**Providers** (`app/qa/llm.py`):
- `anthropic`: official SDK; `output_config.format` JSON schema; configurable effort; refusal handling
  and server-side refusal fallback on supported models.
- `openai`: any OpenAI-compatible endpoint with `response_format: json_schema`.
- `none`: QA returns 503.

The key is read from the env var named by `FINAUDIT_LLM_API_KEY_ENV`. The client is built with an
explicit key and base URL, never ambient credentials.

## Visual RAG (`app/visual/charts.py`)

- **Retrieval:** figure chunks (caption plus context) are retrieved like any other chunk, and citations
  include the figure crop (`/blocks/{id}/image`, rendered from the original PDF).
- **Interpretation:** `POST /documents/{id}/figures/{block}/interpret` sends the crop to the configured
  vision-capable provider with a strict schema. Every value is typed `visual_estimate`
  (`printedOnChart` records whether it was a printed data label). The model is not asked for, and the
  API does not return, confidence scores.
- **Validation against tables:** for each point, rows in the document's table chunks whose label
  contains the point label are candidates. A value within 10% relative is `consistent` (the table value
  is authoritative); otherwise `conflict`; with no candidates, `no_table_evidence`.
- **In QA:** interpretations are appended to figure evidence as `VISUAL ESTIMATE (...)`. Validation
  forces such operands to be `visual_estimate`, and the answer gets a fixed caveat.

**ColPali investigation.** ColPali/ColQwen-style late-interaction page retrieval embeds page images as
multi-vectors. Qdrant supports this (multivector collections with MaxSim comparator), so the
integration point is a third chunk set, `page_image`: one point per page with multivectors from a
`VisualEmbedder` protocol, fused into hybrid retrieval by RRF and evaluated as another configuration.
It was not implemented, for three reasons:
1. The weights (`vidore/colpali-*`, `vidore/colqwen2-*`) are only on HuggingFace, which the development
   environment cannot reach.
2. CPU inference over 2,300+ pages is impractical without a GPU.
3. The milestone's rule is to add components only with measured benefit.

The benchmark already contains chart questions with page-level gold, so the comparison can be run when
an environment with model access exists.

## Security posture

- No user accounts. `FINAUDIT_API_TOKEN`, when set, requires a bearer token on every `/api/v1` route except `/health`. Compose binds the API and Qdrant to 127.0.0.1; do not publish those ports. See `DEPLOYMENT.md`.
- Secrets are environment-only and never accepted in requests or returned (`/index/status` reports
  configuration, not keys).
- The LLM output is data. It is parsed as JSON, validated, and never executed.

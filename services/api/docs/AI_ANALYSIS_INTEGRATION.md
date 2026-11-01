# Connecting the AI Analysis page (for Cursor)

Scope: wire `src/routes/analysis.tsx` to `POST /api/v1/qa` through the existing service layer, and let
citations open the Document Intelligence workspace at the cited page and region. **Do not redesign the
page.** Reuse the existing components: `PageHeader`, `EmptyState`, `ErrorState`, `DocStatus`, the `Button`/`Input`
ui primitives, and the workspace route. This guide assumes the steps in
`docs/FRONTEND_INTEGRATION.md` (`http-service.ts`, `API_URL`, `IS_DEMO`) are done.

Shapes: `app/qa/schemas.py` (Pydantic) / `docs/openapi.json`. All JSON is camelCase.

## 1. Rules the UI must keep

- **Live mode only.** When `IS_DEMO` is true, keep today's `PendingModule` exactly as it is.
  `AGENTS.md` forbids simulated answers, and there is no demo QA data.
- `status: "abstained"` is a first-class result. Render `abstention.reason` and `abstention.detail`
  verbatim. Never fall back to showing `retrieved` excerpts as if they were an answer.
- Show `value.valueKind` next to the headline number, using these labels:
  - `reported`: "Reported"
  - `calculated`: "Calculated from cited values"
  - `visual_estimate`: "Visual estimate from chart, approximate"
- **No confidence UI.** The API returns no confidence score. Don't derive one from `score` or `rank`;
  those are ranking scores, not probabilities.
- Show `note`, the caveat that answers are not audited facts, under every answer.
- HTTP 503 `llm_unavailable` means the server has no LLM configured. Show `ErrorState` with the message
  "Question answering is not configured on this server", plus a link to `/intelligence`. Retrieval
  still works.

## 2. Types: append to `src/lib/api/types.ts`

```ts
export interface CitedRegion {
  page: number; blockId: string | null; role: string | null;
  bbox: BBox; bboxNormalized: NormalizedBBox; workspaceEvidenceId: string | null;
}
export interface ChunkRef {
  chunkId: string; chunkSet: "layout" | "flat"; kind: "text" | "table" | "figure" | "window";
  documentId: string; documentTitle: string | null; company: string | null; period: string | null;
  pages: number[]; sectionPath: string[]; content: string; regions: CitedRegion[];
  table: { caption: string | null; title: string | null; units: string | null; columns: string[] } | null;
  figure: { caption: string | null; imageUrl: string | null } | null;
  pageImageUrl: string; sourceSha256: string; parser: string; parserVersion: string; indexVersion: string;
}
export interface QACitation { evidenceId: string; quote: string | null; evidenceKind: ChunkRef["kind"]; chunk: ChunkRef }
export interface QAOperand { id: string; value: string; quote: string; label: string; evidenceId: string;
  scale: string; valueKind: "reported" | "visual_estimate"; evidenceKind: ChunkRef["kind"] }
export interface QACalculation { id: string; op: string; description: string;
  inputs: { ref: string; value: string }[]; result: string; scale: string; valueKind: "reported" | "visual_estimate" }
export interface QAResponse {
  status: "answered" | "abstained";
  question: string; answer: string | null;
  value: { value: string; unit: string | null; valueKind: "reported" | "calculated" | "visual_estimate"; source: string } | null;
  operands: QAOperand[]; calculations: QACalculation[]; citations: QACitation[];
  abstention: { reason: "no_evidence" | "insufficient_evidence" | "validation_failed" | "model_refused"; detail: string } | null;
  documentsConsidered: { documentId: string; issuer?: string; period?: string; title?: string }[];
  retrieved: { rank: number; score: number; chunk: ChunkRef }[];
  usage: { provider: string | null; model: string | null; inputTokens: number | null; outputTokens: number | null;
           llmCalls: number; costUsd: number | null };
  timingsMs: Record<string, number>; warnings: string[]; note: string;
}
export interface QARequest { question: string; documentIds?: string[] | null; topK?: number }
```

## 3. Service layer: `src/lib/api/http-service.ts` and `service.ts`

```ts
// http-service.ts
ask: (body: QARequest) => req<QAResponse>("/qa", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
getCitation: (chunkId: string) => req<ChunkRef>(`/citations/${encodeURIComponent(chunkId)}`),
```

```ts
// service.ts: optional members on FinAuditService (demo implementation leaves them undefined)
ask?(body: QARequest): Promise<QAResponse>;
getCitation?(chunkId: string): Promise<ChunkRef>;
```

QA is a mutation, not a cached query. Use `useMutation({ mutationFn: (b: QARequest) => api.ask!(b) })`.

## 4. `src/routes/analysis.tsx`

1. `component: () => IS_DEMO || !api.ask ? <PendingModule …unchanged… /> : <AnalysisWorkspace />`
2. `AnalysisWorkspace`, laid out like the other pages (`page-layout space-y-6`, `PageHeader` with the
   existing eyebrow, title and description):
   - A question `Input` plus a submit `Button`. Disable it while `mutation.isPending`.
   - An optional document scope: a multi-select over `useQuery(documentsQuery())`, filtered to
     `status === "ready"`, which sends `documentIds`. With no selection the server routes by the
     company named in the question, and `documentsConsidered` shows what it chose.
   - **Answered result:**
     - `answer` text.
     - The headline `value.value` + `value.unit` with the `valueKind` label (section 1).
     - A collapsible "How this was calculated" list. Each `calculations[i]` renders as
       `description: op(inputs) = result`. Each `operands[i]` renders as `label = quote [E#]`, with a
       "table" or "narrative" tag from `evidenceKind`.
     - A citation list (section 5).
   - **Abstained result:** an `EmptyState` titled "No supported answer", with `abstention.detail` as
     the description.
   - A footer with `usage.model`, `timingsMs.total_ms`, `note` and any `warnings`. Show `costUsd` only
     when it is non-null.

## 5. Citations → Document Intelligence workspace

Each citation item shows:
- `chunk.documentTitle`, `p. {chunk.pages[0]}`, `chunk.sectionPath.join(" › ")` and the `quote`;
- for tables, `chunk.table.units`;
- for figures, a thumbnail `<img src={apiAsset(chunk.figure.imageUrl)}>`.

Clicking a citation navigates to the workspace:

```ts
navigate({ to: "/intelligence", search: { doc: c.chunk.documentId, page: c.chunk.regions[0].page } })
```

To also select the highlighted region, add an optional `ev` search param to `intelligence.tsx`'s zod
schema: `ev: z.string().optional()`. Call `select(search.ev)` on mount. Pass
`c.chunk.regions[0].workspaceEvidenceId` (format `ev-{blockId}`, which matches
`GET /documents/{id}/evidence` ids for tables, figures and numeric text blocks).

When `workspaceEvidenceId` is null, or matches no evidence item (e.g. a plain text block), draw the
region instead. Overlay `regions[i].bboxNormalized` on `page.imageUrl` as described in
`FRONTEND_INTEGRATION.md` step 6.

## 6. Optional: retrieval inspector

`POST /api/v1/retrieve` with `{query, documentIds, method: "bm25"|"dense"|"hybrid", k}` returns ranked
evidence with no LLM involved. It can back a "Search evidence" tab on the same page using the same
citation list component. Label each item with its `rank`, never as an answer.

## 7. Verify

1. Backend with `FINAUDIT_LLM_PROVIDER=none`: the page shows the 503 `ErrorState`; Intelligence still works.
2. Backend with a provider configured: ask about the synthetic fixture.

   Ask: "What was Fictional Example Holdings' operating profit in 2025?"
   - The answer cites a TABLE on p. 2.
   - Clicking the citation opens the workspace on page 2 with the income-statement table selected.

   Ask: "What was Northwind's revenue in 2030?"
   - The page shows the abstention state.
3. Run `npm run test` and `npm run build`. Unset `VITE_FINAUDIT_API_URL` and confirm the page is the
   original `PendingModule`.

## 8. Milestone 3.5 changes (evidence binding)

All changes are **additive**; existing fields keep their meaning.

| Where | Change | UI guidance |
|---|---|---|
| `QAOperand` | new optional `rowLabel`, `period`, `metric`, `currency`, `factId`, `periodType`, `binding` (`fact` / `table_text` / `statement` / `figure`) | `analysis.tsx` shows "Source row … · period … (type)". `label` is now `"<metric> (<period>)"`. Never show a period the backend did not return |
| `Job` | `stage` may be `indexing`; new `kind` (`parse` / `index`) | Display as text; no new state handling needed |
| `GET /api/v1/documents/{id}/facts?page=&tableId=` | returns `FinancialFact[]` (see `docs/FINANCIAL_EVIDENCE_SCHEMA.md`) | Optional. If shown, render `period.periodType: "unknown"`, `scale: "unknown"`, `currency: null` as **"not stated"**, never as a guess. Use `bbox` + `page` for highlighting exactly like evidence regions |
| Abstention details | new check names (`operand_cell_located`, `operand_period_matches`, `operand_period_in_question`, `operand_metric_supported`, `operand_units_match`, `operand_currency_matches`, `question_currency_supported`, `operand_scope_matches`, `operands_scope_consistent`, `operands_currency_consistent`, `calculation_spec_valid`, `final_metric_matches_question`, `answer_no_injected_content`, `answer_claims_supported`) | `abstention.detail` stays free text; do not parse it |

The QA endpoint still returns 503 until a provider is configured server-side. No answer, value or verification
status may be simulated in the UI; demo-sourced values stay labelled DEMO.

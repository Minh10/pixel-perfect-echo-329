# Frontend integration guide (for Cursor)

Goal: point the existing frontend at the FastAPI backend **through the existing service abstraction**
(`src/lib/api/service.ts`), without breaking demo mode and without presenting demo values as real.
Nothing below has been applied to the frontend yet; the backend branch only adds `services/api/`.

Source of truth for shapes: `services/api/app/schemas.py` and `services/api/docs/openapi.json`.
All JSON is camelCase. All new fields are **additive** to `src/lib/api/types.ts`.

---

## Step 0: Run the backend

```bash
cd services/api && cp .env.example .env && docker compose up --build
```

```bash
curl http://localhost:8000/api/v1/health
```

The first command starts the stack; the second checks it is up. Without Docling model weights
(e.g. a restricted network), set `FINAUDIT_PARSER=auto` or `pymupdf` in `services/api/.env`.
CORS already allows `http://localhost:8080`, `:5173` and `:3000` (`FINAUDIT_CORS_ORIGINS`).

## Step 1: Environment variable

Create `/.env.local` at the repo root. `*.local` is already git-ignored:

```
VITE_FINAUDIT_API_URL=http://localhost:8000
```

When this variable is unset the app must keep using `demoService`, as it does today.

## Step 2: Extend `src/lib/api/types.ts` (additive, keeps demo data valid)

```ts
export type DocumentStatus = "processing" | "ready" | "failed";            // unchanged

export interface FinDocument {
  id: string;
  title: string;
  issuer: string | null;                                                    // backend: null if not supplied
  period: string | null;
  type: "Annual Report" | "Quarterly Report" | "Prospectus" | "Sustainability Report" | null;
  pages: number;
  uploadedAt: string;                                                       // ISO-8601 datetime from backend
  status: DocumentStatus;
  sizeMb: number;
  // backend-only (optional so demo data still type-checks)
  filename?: string;
  sha256?: string;
  processedAt?: string | null;
  latestJobId?: string | null;
  parser?: { name: "docling" | "pymupdf"; version: string; options: Record<string, unknown> } | null;
  warnings?: string[];
  error?: ApiErrorBody | null;
}

export type BlockKind = "heading" | "paragraph" | "table" | "chart" | "figure"; // + "figure"

export interface BBox { l: number; t: number; r: number; b: number; coordOrigin: "top-left"; unit: "pt" }
export interface NormalizedBBox { x: number; y: number; width: number; height: number } // 0..1 of page

export interface Provenance {
  documentId: string; sourceSha256: string; page: number;
  bbox: BBox; bboxNormalized: NormalizedBBox; pageWidth: number; pageHeight: number;
  charspan: [number, number] | null; sourceRef: string | null;
  parser: "docling" | "pymupdf"; parserVersion: string; method: string; jobId: string;
}

export interface TableData {
  columns: string[];
  rows: { label: string; values: string[]; emphasis?: boolean }[];
  // backend-only
  numRows?: number; numCols?: number; headerRows?: number;
  cells?: { row: number; col: number; rowSpan: number; colSpan: number; text: string;
            columnHeader: boolean; rowHeader: boolean; bbox: BBox | null }[];
}

export interface FigureData {
  caption: string | null;
  classification: { className: string; confidence: number | null; createdBy: string | null }[];
  imageUrl: string;                                                         // relative to API base URL
}

export interface PageBlock {
  id: string;
  kind: BlockKind;
  text?: string | null;
  table?: TableData | null;
  chart?: ChartData;                                                        // demo only; backend never sends
  // backend-only
  role?: string; level?: number | null; figure?: FigureData | null; captionBlockId?: string | null;
  bbox?: BBox; bboxNormalized?: NormalizedBBox; provenance?: Provenance;
}

export interface DocumentPage {
  number: number;
  section: string;
  blocks: PageBlock[];
  // backend-only
  width?: number; height?: number; rotation?: number; hasTextLayer?: boolean;
  charCount?: number; imageCount?: number; imageUrl?: string;
  confidence?: { layoutScore: number | null; parseScore: number | null;
                 tableScore: number | null; ocrScore: number | null } | null;
}

export type EvidenceCategory = "metric" | "disclosure" | "table" | "chart" | "figure"; // + "figure"

export interface Evidence {
  id: string;
  page: number;
  blockId: string;
  category: EvidenceCategory;
  label: string;
  excerpt: string;
  extracted?: { field: string; value: string; unit?: string }[] | null;    // backend: always null
  confidence: number | null;                                                // backend: null unless parser-reported
  related: string[];
  // backend-only
  detection?: { method: string; rule: string | null };
  provenance?: Provenance;
}

export type JobState = "queued" | "running" | "succeeded" | "failed";
export interface Job {
  id: string; documentId: string; state: JobState;
  stage: "queued" | "inspecting" | "parsing" | "assembling" | "persisting" | "done";
  progress: number; attempts: number; maxAttempts: number; requestedParser: string;
  error: ApiErrorBody | null; createdAt: string; startedAt: string | null;
  finishedAt: string | null; heartbeatAt: string | null;
}
export interface ApiErrorBody { code: string; message: string }
export interface UploadMeta { title?: string; issuer?: string; period?: string; type?: NonNullable<FinDocument["type"]> }
```

Then fix the compile errors this surfaces. They are expected at:
- `src/components/workspace/evidence-inspector.tsx`: `ConfidenceBar value={selected.confidence}` now
  takes `number | null`. Render "Not reported" for `null` (see Step 6).
- `src/components/app/documents-table.tsx`: `d.issuer`, `d.type` and `d.period` may be `null`.
  Render `"—"`.

## Step 3: Create `src/lib/api/http-service.ts`

```ts
import type { DocumentPage, Evidence, FinDocument, Job, TrendPoint, UploadMeta } from "./types";

export const API_URL = (import.meta.env.VITE_FINAUDIT_API_URL as string | undefined)?.replace(/\/$/, "");
const V1 = `${API_URL}/api/v1`;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${V1}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.error?.code ?? `http_${res.status}`, body?.error?.message ?? res.statusText);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

/** Resolve a backend-relative URL (imageUrl fields) to an absolute one. */
export const apiAsset = (relative: string) => `${API_URL}${relative}`;

export const httpService = {
  listDocuments: () => req<FinDocument[]>("/documents"),
  getDocument: (id: string) => req<FinDocument>(`/documents/${encodeURIComponent(id)}`),
  getPages: (id: string) => req<DocumentPage[]>(`/documents/${encodeURIComponent(id)}/pages`),
  getEvidence: (id: string) => req<Evidence[]>(`/documents/${encodeURIComponent(id)}/evidence`),
  // No backend endpoint in this milestone: trends require financial extraction (not implemented).
  getTrends: async (_id: string): Promise<TrendPoint[]> => { throw new ApiError(501, "not_implemented", "Trends are not available from the backend yet"); },

  uploadDocument: (file: File, meta: UploadMeta = {}) => {
    const fd = new FormData();
    fd.append("file", file);
    for (const [k, v] of Object.entries(meta)) if (v) fd.append(k, v);
    return req<{ document: FinDocument; job: Job }>("/documents", { method: "POST", body: fd });
  },
  getJob: (jobId: string) => req<Job>(`/jobs/${encodeURIComponent(jobId)}`),
  deleteDocument: (id: string) => req<void>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  reprocessDocument: (id: string) => req<Job>(`/documents/${encodeURIComponent(id)}/reprocess`, { method: "POST" }),
};
```

## Step 4: Switch the implementation in `src/lib/api/service.ts`

Change only the selection lines and add the upload and job helpers:

```ts
import { API_URL, httpService } from "./http-service";

export interface FinAuditService {
  listDocuments(): Promise<FinDocument[]>;
  getDocument(id: string): Promise<FinDocument>;
  getPages(id: string): Promise<DocumentPage[]>;
  getEvidence(id: string): Promise<Evidence[]>;
  getTrends(id: string): Promise<TrendPoint[]>;
  uploadDocument?(file: File, meta?: UploadMeta): Promise<{ document: FinDocument; job: Job }>;
  getJob?(jobId: string): Promise<Job>;
}

export const IS_DEMO = !API_URL;
export const api: FinAuditService = IS_DEMO ? demoService : httpService;
/** Demo-mode default only.  In live mode there is no fixed default document. */
export const DEFAULT_DOCUMENT_ID: string | null = IS_DEMO ? "nhc-ar-2025" : null;

export const jobQuery = (jobId: string) =>
  queryOptions({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob!(jobId),
    refetchInterval: (q) => (q.state.data && ["succeeded", "failed"].includes(q.state.data.state) ? false : 1500),
  });
```

`trendsQuery` keeps calling `demoService.getTrends` explicitly while the backend lacks trends,
and the Trends page keeps its `DemoBadge`:
`queryFn: () => demoService.getTrends(id)`.

## Step 5: Routes that assume the demo default document

- `src/routes/intelligence.tsx`: replace `search.doc ?? DEFAULT_DOCUMENT_ID` with
  `search.doc ?? DEFAULT_DOCUMENT_ID ?? firstReadyId`. In the loader, `firstReadyId` comes from
  `ensureQueryData(documentsQuery())` and `.find(d => d.status === "ready")?.id`. If there is none,
  render the existing `EmptyState` ("Upload a report to begin"). The empty-state action
  "Open demo report" should only render when `IS_DEMO`.
- `src/routes/index.tsx`: the "Evidence regions" stat uses `evidenceQuery(DEFAULT_DOCUMENT_ID)`. In
  live mode, either drop the stat or sum `getEvidence` over ready documents. Show `DemoBadge` only
  when `IS_DEMO`.
- `src/components/app/app-header.tsx`: render `<DemoBadge />` only when `IS_DEMO`.
- `src/routes/documents.tsx`: enable the Upload button when `!IS_DEMO` (Step 7).

## Step 6: Workspace rendering of real parser output

- `evidence-inspector.tsx`:
  - `confidence === null`: show "Confidence: not reported by parser" instead of the bar.
  - Show `DemoBadge` and the "Extraction is illustrative" note only when `IS_DEMO`.
  - In live mode show `provenance.parser`, `provenance.method`, `p. {page}` and the bbox, plus
    `detection.rule` for `disclosure` items. Add `figure: "Figure"` to `CATEGORY_LABEL`.
  - Guard `selected.extracted &&`; it is already guarded, and `null` is falsy.
- `document-page.tsx` `BlockContent`: add
  `if (block.kind === "figure" && block.figure) return <figure><img src={apiAsset(block.figure.imageUrl)} alt={block.figure.caption ?? "Figure"} className="max-w-full" />{block.figure.caption && <figcaption>…</figcaption>}</figure>;`
- Recommended for traceability: render the real page image
  `apiAsset(page.imageUrl + "?dpi=110")` as the page background. Overlay each evidence block as an
  absolutely positioned button using `block.bboxNormalized`:
  `left: x*100%`, `top: y*100%`, `width: width*100%`, `height: height*100%`.
  Use `aspect-ratio: page.width / page.height` instead of the fixed `aspect-[1/1.3]`. This
  replaces the "paper sheet" approximation that the component comment already anticipates.
- `page-navigator.tsx` works unchanged. It only uses `number`, `section` and the evidence counts.

## Step 7: Upload flow (`src/routes/documents.tsx`)

1. Add a hidden `<input type="file" accept="application/pdf">` behind the Upload button, and an
   optional small form for `issuer`, `period` and `type`.
2. Call `api.uploadDocument(file, meta)`. On `ApiError`, show `error.message` (e.g. "PDF is
   password-protected…") through `sonner` `toast.error`.
3. On 202, `queryClient.invalidateQueries({ queryKey: ["documents"] })`, then poll
   `jobQuery(job.id)`. Show `stage` and `Math.round(progress*100)%` next to the
   `DocStatus` "Processing" indicator.
4. When the job state is `succeeded` or `failed`, invalidate `["documents"]` and `["document", id]`.
   For `failed`, show `document.error.message`.

## Step 8: Verify

```bash
npm run test
```

```bash
npm run build
```

Then run `npm run dev` with `VITE_FINAUDIT_API_URL` set, upload
`services/api/tests/fixtures/annual_report_excerpt.pdf`, wait for Ready, and open it in Document
Intelligence. Expect:
- 3 pages
- a 7×4 income-statement table on page 2, with cells exactly as in the PDF
- a figure on page 3 with its caption
- evidence items whose highlight positions match the rendered page

Unset the variable and confirm the demo workspace still works, with DEMO badges.

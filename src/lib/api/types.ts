// Domain types shared by the UI and the FastAPI backend contract.
// Backend fields are additive. Demo data stays valid because new fields are optional
// and newly nullable fields still accept the demo strings and confidence scores.

export type DocumentStatus = "processing" | "ready" | "failed";

export type DocumentType =
  "Annual Report" | "Quarterly Report" | "Prospectus" | "Sustainability Report";

export interface ApiErrorBody {
  code: string;
  message: string;
}

export interface ParserInfo {
  name: "docling" | "pymupdf";
  version: string;
  options: Record<string, unknown>;
}

export interface FinDocument {
  id: string;
  title: string;
  issuer: string | null;
  period: string | null;
  type: DocumentType | null;
  pages: number;
  uploadedAt: string;
  status: DocumentStatus;
  sizeMb: number;
  filename?: string;
  sha256?: string;
  processedAt?: string | null;
  latestJobId?: string | null;
  parser?: ParserInfo | null;
  warnings?: string[];
  error?: ApiErrorBody | null;
}

export type BlockKind = "heading" | "paragraph" | "table" | "chart" | "figure";

export interface BBox {
  l: number;
  t: number;
  r: number;
  b: number;
  coordOrigin: "top-left";
  unit: "pt";
}

export interface NormalizedBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Provenance {
  documentId: string;
  sourceSha256: string;
  page: number;
  bbox: BBox;
  bboxNormalized: NormalizedBBox;
  pageWidth: number;
  pageHeight: number;
  charspan: [number, number] | null;
  sourceRef: string | null;
  parser: "docling" | "pymupdf";
  parserVersion: string;
  method: string;
  jobId: string;
}

export interface TableCell {
  row: number;
  col: number;
  rowSpan: number;
  colSpan: number;
  text: string;
  columnHeader: boolean;
  rowHeader: boolean;
  bbox: BBox | null;
}

export interface TableData {
  columns: string[];
  rows: { label: string; values: string[]; emphasis?: boolean }[];
  numRows?: number;
  numCols?: number;
  headerRows?: number;
  cells?: TableCell[];
}

export interface ChartData {
  title: string;
  series: { label: string; value: number }[];
}

export interface FigureClassification {
  className: string;
  confidence: number | null;
  createdBy: string | null;
}

export interface FigureData {
  caption: string | null;
  classification: FigureClassification[];
  imageUrl: string;
}

export interface PageBlock {
  id: string;
  kind: BlockKind;
  text?: string | null;
  table?: TableData | null;
  chart?: ChartData;
  role?: string;
  level?: number | null;
  figure?: FigureData | null;
  captionBlockId?: string | null;
  bbox?: BBox;
  bboxNormalized?: NormalizedBBox;
  provenance?: Provenance;
}

export interface PageConfidence {
  layoutScore: number | null;
  parseScore: number | null;
  tableScore: number | null;
  ocrScore: number | null;
}

export interface DocumentPage {
  number: number;
  section: string;
  blocks: PageBlock[];
  width?: number;
  height?: number;
  rotation?: number;
  hasTextLayer?: boolean;
  charCount?: number;
  imageCount?: number;
  imageUrl?: string;
  confidence?: PageConfidence | null;
}

export type EvidenceCategory = "metric" | "disclosure" | "table" | "chart" | "figure";

export interface EvidenceDetection {
  method: string;
  rule: string | null;
}

export interface Evidence {
  id: string;
  page: number;
  blockId: string;
  category: EvidenceCategory;
  label: string;
  excerpt: string;
  extracted?: { field: string; value: string; unit?: string }[] | null;
  confidence: number | null;
  related: string[];
  detection?: EvidenceDetection;
  provenance?: Provenance;
}

export type JobState = "queued" | "running" | "succeeded" | "failed";
export type JobStage =
  "queued" | "inspecting" | "parsing" | "assembling" | "persisting" | "indexing" | "done";
export type JobKind = "parse" | "index";

export interface Job {
  id: string;
  documentId: string;
  /** "parse" jobs parse the PDF; "index" jobs build chunks, FinancialFacts and vectors. */
  kind?: JobKind;
  state: JobState;
  stage: JobStage;
  progress: number;
  attempts: number;
  maxAttempts: number;
  requestedParser: string;
  error: ApiErrorBody | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  heartbeatAt: string | null;
}

export interface UploadMeta {
  title?: string;
  issuer?: string;
  period?: string;
  type?: DocumentType;
}

export interface TrendPoint {
  period: string;
  revenue: number;
  operatingIncome: number;
  netIncome: number;
}

export interface CitedRegion {
  page: number;
  blockId: string | null;
  role: string | null;
  bbox: BBox;
  bboxNormalized: NormalizedBBox;
  workspaceEvidenceId: string | null;
}

export interface ChunkRef {
  chunkId: string;
  chunkSet: "layout" | "flat";
  kind: "text" | "table" | "figure" | "window";
  documentId: string;
  documentTitle: string | null;
  company: string | null;
  period: string | null;
  pages: number[];
  sectionPath: string[];
  content: string;
  regions: CitedRegion[];
  table: {
    caption: string | null;
    title: string | null;
    units: string | null;
    columns: string[];
  } | null;
  figure: { caption: string | null; imageUrl: string | null } | null;
  pageImageUrl: string;
  sourceSha256: string;
  parser: string;
  parserVersion: string;
  indexVersion: string;
}

export interface QACitation {
  evidenceId: string;
  quote: string | null;
  evidenceKind: ChunkRef["kind"];
  chunk: ChunkRef;
}

export interface QAOperand {
  id: string;
  value: string;
  quote: string;
  label: string;
  evidenceId: string;
  scale: string;
  valueKind: "reported" | "visual_estimate";
  evidenceKind: ChunkRef["kind"];
  /** Source row label / metric phrase quoted by the model (verified against the evidence). */
  rowLabel?: string | null;
  /** Period claimed by the model; the validator checks it against the bound column/clause. */
  period?: string | null;
  metric?: string | null;
  currency?: string | null;
  /** FinancialFact the operand was bound to (table evidence). */
  factId?: string | null;
  periodType?: string | null;
  binding?: "fact" | "table_text" | "statement" | "figure" | null;
}

export interface QACalculation {
  id: string;
  op: string;
  description: string;
  inputs: { ref: string; value: string }[];
  result: string;
  scale: string;
  valueKind: "reported" | "visual_estimate";
}

export type ValueKind = "reported" | "calculated" | "visual_estimate";

export interface QAResponse {
  status: "answered" | "abstained";
  question: string;
  answer: string | null;
  value: { value: string; unit: string | null; valueKind: ValueKind; source: string } | null;
  operands: QAOperand[];
  calculations: QACalculation[];
  citations: QACitation[];
  abstention: {
    reason: "no_evidence" | "insufficient_evidence" | "validation_failed" | "model_refused";
    detail: string;
  } | null;
  documentsConsidered: { documentId: string; issuer?: string; period?: string; title?: string }[];
  retrieved: { rank: number; score: number; chunk: ChunkRef }[];
  usage: {
    provider: string | null;
    model: string | null;
    inputTokens: number | null;
    outputTokens: number | null;
    llmCalls: number;
    costUsd: number | null;
  };
  timingsMs: Record<string, number>;
  warnings: string[];
  note: string;
}

export interface QARequest {
  question: string;
  documentIds?: string[] | null;
  topK?: number;
}

// ---------------------------------------------------------------------------------------------------------------
// Structured financial evidence (GET /api/v1/documents/{id}/facts). Unknown metadata stays explicitly unknown.
export type FactPeriodType =
  "annual" | "quarterly" | "ytd" | "cumulative" | "point_in_time" | "unknown";
export type FactScale =
  "units" | "thousands" | "millions" | "billions" | "percent" | "per_share" | "unknown";
export type FactScope = "consolidated" | "segment" | "unknown";
export type FactValueStatus = "parsed" | "nil" | "malformed" | "non_numeric" | "empty";

export interface FactPeriod {
  label: string | null;
  fiscalYear: number | null;
  endDate: string | null;
  periodType: FactPeriodType;
  source: "column_header" | "column_header_geometric" | "narrative_clause" | "unknown";
}

export interface FinancialFact {
  factId: string;
  normalizationVersion: string;
  documentId: string;
  issuer: string | null;
  sourceSha256: string;
  tableId: string;
  page: number;
  rowIndex: number;
  colIndices: number[];
  slotIndex: number;
  rowLabel: string;
  rowGroup: string | null;
  columnHeader: string | null;
  /** Verbatim cell text, e.g. "(7.0)%". */
  cellText: string;
  /** Exact decimal string; null unless valueStatus is "parsed". */
  value: string | null;
  valueStatus: FactValueStatus;
  isPercent: boolean;
  period: FactPeriod;
  scale: FactScale;
  scaleSource: string | null;
  currency: string | null;
  currencySource: string | null;
  scope: FactScope;
  scopeSource: string | null;
  bbox: BBox | null;
  parser: string;
  parserVersion: string;
}

export interface ChartPoint {
  series: string | null;
  label: string;
  value: string;
  unit: string | null;
  valueKind: "visual_estimate";
  printedOnChart: boolean;
}

export interface TableCheck {
  label: string;
  estimate: string;
  tableValue: string | null;
  tableChunkId: string | null;
  relativeDifference: number | null;
  status: "consistent" | "conflict" | "no_table_evidence";
}

export interface ChartInterpretation {
  documentId: string;
  blockId: string;
  chartType: string | null;
  title: string | null;
  points: ChartPoint[];
  tableChecks: TableCheck[];
  cropUrl: string;
  provider: string;
  model: string;
  createdAt: string;
  caveat: string;
}

export interface RetrieveResponse {
  query: string;
  method: string;
  effectiveMethod: string;
  warnings: string[];
  results: { rank: number; score: number; chunk: ChunkRef }[];
}

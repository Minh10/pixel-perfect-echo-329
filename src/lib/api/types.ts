// Domain types shared by the UI and the FastAPI backend contract.
// Backend fields are additive. Demo data stays valid because new fields are optional
// and newly nullable fields still accept the demo strings and confidence scores.

export type DocumentStatus = "processing" | "ready" | "failed";

export type DocumentType =
  | "Annual Report"
  | "Quarterly Report"
  | "Prospectus"
  | "Sustainability Report";

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
export type JobStage = "queued" | "inspecting" | "parsing" | "assembling" | "persisting" | "done";

export interface Job {
  id: string;
  documentId: string;
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

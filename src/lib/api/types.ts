// Domain types shared by the UI and the (future) FastAPI backend contract.

export type DocumentStatus = "processing" | "ready" | "failed";

export interface FinDocument {
  id: string;
  title: string;
  issuer: string;
  period: string;
  type: "Annual Report" | "Quarterly Report" | "Prospectus" | "Sustainability Report";
  pages: number;
  uploadedAt: string;
  status: DocumentStatus;
  sizeMb: number;
}

export type BlockKind = "heading" | "paragraph" | "table" | "chart";

export interface TableData {
  columns: string[];
  rows: { label: string; values: string[]; emphasis?: boolean }[];
}

export interface ChartData {
  title: string;
  series: { label: string; value: number }[];
}

export interface PageBlock {
  id: string;
  kind: BlockKind;
  text?: string;
  table?: TableData;
  chart?: ChartData;
}

export interface DocumentPage {
  number: number;
  section: string;
  blocks: PageBlock[];
}

export type EvidenceCategory = "metric" | "disclosure" | "table" | "chart";

export interface Evidence {
  id: string;
  page: number;
  blockId: string;
  category: EvidenceCategory;
  label: string;
  excerpt: string;
  extracted?: { field: string; value: string; unit?: string }[];
  confidence: number; // 0..1 extraction confidence (demo)
  related: string[]; // other evidence ids
}

export interface TrendPoint {
  period: string;
  revenue: number;
  operatingIncome: number;
  netIncome: number;
}

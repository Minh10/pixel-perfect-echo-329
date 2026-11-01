// Replaceable typed service layer. Swap `demoService` for an HTTP client
// targeting the FastAPI backend without touching UI code.
import { queryOptions } from "@tanstack/react-query";
import { DEMO_DOCUMENTS, DEMO_EVIDENCE, DEMO_PAGES, DEMO_TRENDS } from "./demo-data";
import type { DocumentPage, Evidence, FinDocument, TrendPoint } from "./types";

export interface FinAuditService {
  listDocuments(): Promise<FinDocument[]>;
  getDocument(id: string): Promise<FinDocument>;
  getPages(id: string): Promise<DocumentPage[]>;
  getEvidence(id: string): Promise<Evidence[]>;
  getTrends(id: string): Promise<TrendPoint[]>;
}

const delay = <T,>(value: T, ms = 350) => new Promise<T>((r) => setTimeout(() => r(value), ms));

export const demoService: FinAuditService = {
  listDocuments: () => delay(DEMO_DOCUMENTS),
  getDocument: async (id) => {
    const doc = DEMO_DOCUMENTS.find((d) => d.id === id);
    if (!doc) throw new Error(`Document ${id} not found`);
    return delay(doc);
  },
  getPages: (id) => delay(id === "nhc-ar-2025" ? DEMO_PAGES : []),
  getEvidence: (id) => delay(id === "nhc-ar-2025" ? DEMO_EVIDENCE : []),
  getTrends: () => delay(DEMO_TRENDS),
};

/** Whether the active service returns demo data (drives DEMO labels in UI). */
export const IS_DEMO = true;
export const api: FinAuditService = demoService;

export const DEFAULT_DOCUMENT_ID = "nhc-ar-2025";

export const documentsQuery = () => queryOptions({ queryKey: ["documents"], queryFn: () => api.listDocuments() });
export const documentQuery = (id: string) => queryOptions({ queryKey: ["document", id], queryFn: () => api.getDocument(id) });
export const pagesQuery = (id: string) => queryOptions({ queryKey: ["pages", id], queryFn: () => api.getPages(id) });
export const evidenceQuery = (id: string) => queryOptions({ queryKey: ["evidence", id], queryFn: () => api.getEvidence(id) });
export const trendsQuery = (id: string) => queryOptions({ queryKey: ["trends", id], queryFn: () => api.getTrends(id) });

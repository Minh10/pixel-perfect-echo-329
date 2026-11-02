// Replaceable typed service layer. Live mode uses the FastAPI client when
// VITE_FINAUDIT_SERVICE_MODE is explicitly set to proxy. Demo mode stays on fictional fixtures and is
// never mixed into live document, page, or evidence results.
import { queryOptions } from "@tanstack/react-query";
import { DEMO_DOCUMENTS, DEMO_EVIDENCE, DEMO_PAGES, DEMO_TRENDS } from "./demo-data";
import { configureHttpService, httpService } from "./http-service";
import type {
  ChartInterpretation,
  ChunkRef,
  DocumentPage,
  Evidence,
  FinDocument,
  FinancialFact,
  Job,
  QARequest,
  QAResponse,
  RetrieveResponse,
  TrendPoint,
  UploadMeta,
} from "./types";

export interface FinAuditService {
  listDocuments(): Promise<FinDocument[]>;
  getDocument(id: string): Promise<FinDocument>;
  getPages(id: string): Promise<DocumentPage[]>;
  getEvidence(id: string): Promise<Evidence[]>;
  getTrends(id: string): Promise<TrendPoint[]>;
  uploadDocument?(
    file: File,
    meta?: UploadMeta,
    onProgress?: (fraction: number) => void,
  ): Promise<{ document: FinDocument; job: Job }>;
  getJob?(jobId: string): Promise<Job>;
  ask?(body: QARequest): Promise<QAResponse>;
  getCitation?(chunkId: string): Promise<ChunkRef>;
  getFacts?(id: string): Promise<FinancialFact[]>;
  getFigureInterpretation?(documentId: string, blockId: string): Promise<ChartInterpretation>;
  interpretFigure?(documentId: string, blockId: string): Promise<ChartInterpretation>;
  searchEvidence?(query: string, documentIds: string[]): Promise<RetrieveResponse>;
}

const delay = <T>(value: T, ms = 350) => new Promise<T>((r) => setTimeout(() => r(value), ms));

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
export let IS_DEMO = true;
export let api: FinAuditService = demoService;
/** Demo-mode default only. In live mode there is no fixed default document. */
export let DEFAULT_DOCUMENT_ID: string | null = "nhc-ar-2025";
// Called only from a browser effect after server verification, never during SSR.
export function configureDemoService(live: boolean) {
  IS_DEMO = !live;
  api = live ? httpService : demoService;
  DEFAULT_DOCUMENT_ID = live ? null : "nhc-ar-2025";
  configureHttpService(live);
}

export const documentsQuery = () =>
  queryOptions({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
    refetchInterval: (query) =>
      !IS_DEMO && query.state.data?.some((doc) => doc.status === "processing") ? 2000 : false,
  });

export const documentQuery = (id: string) =>
  queryOptions({
    queryKey: ["document", id],
    queryFn: () => api.getDocument(id),
    refetchInterval: (query) =>
      !IS_DEMO && query.state.data?.status === "processing" ? 1500 : false,
  });

export const pagesQuery = (id: string) =>
  queryOptions({ queryKey: ["pages", id], queryFn: () => api.getPages(id) });

export const evidenceQuery = (id: string) =>
  queryOptions({ queryKey: ["evidence", id], queryFn: () => api.getEvidence(id) });

// Demo mode keeps the labelled fictional series. Live mode does not call this.
export const trendsQuery = (id: string | null) =>
  queryOptions({
    queryKey: ["trends", "demo", id ?? "none"],
    queryFn: () => demoService.getTrends(id ?? "demo"),
  });

export const jobQuery = (jobId: string) =>
  queryOptions({
    queryKey: ["job", jobId],
    queryFn: () => {
      if (!api.getJob) throw new Error("Job status is only available from the backend");
      return api.getJob(jobId);
    },
    refetchInterval: (query) =>
      query.state.data && ["succeeded", "failed"].includes(query.state.data.state) ? false : 1500,
  });

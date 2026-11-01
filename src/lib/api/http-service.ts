import type {
  DocumentPage,
  Evidence,
  FinDocument,
  Job,
  TrendPoint,
  UploadMeta,
} from "./types";

export const API_URL = (import.meta.env["VITE_FINAUDIT_API_URL"] as string | undefined)?.replace(
  /\/$/,
  "",
);

const V1 = `${API_URL}/api/v1`;
const JSON_TIMEOUT_MS = 20_000;
const UPLOAD_TIMEOUT_MS = 120_000;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function asApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  if (err instanceof DOMException && (err.name === "TimeoutError" || err.name === "AbortError")) {
    return new ApiError(0, "timeout", "The document service timed out. Try again in a moment.");
  }
  if (err instanceof TypeError) {
    return new ApiError(
      0,
      "backend_unavailable",
      "The document service is not reachable. Check that the API is running.",
    );
  }
  return new ApiError(0, "network_error", err instanceof Error ? err.message : "Request failed");
}

async function req<T>(path: string, init?: RequestInit, timeoutMs = JSON_TIMEOUT_MS): Promise<T> {
  if (!API_URL) {
    throw new ApiError(0, "backend_unavailable", "The document service URL is not configured.");
  }
  let res: Response;
  try {
    res = await fetch(`${V1}${path}`, {
      ...init,
      signal: init?.signal ?? AbortSignal.timeout(timeoutMs),
    });
  } catch (err) {
    throw asApiError(err);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(
      res.status,
      body?.error?.code ?? `http_${res.status}`,
      body?.error?.message ?? res.statusText,
    );
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

/** Resolve a backend-relative URL (imageUrl fields, source PDF) to an absolute one. */
export const apiAsset = (relative: string) => {
  if (/^https?:\/\//i.test(relative)) return relative;
  return `${API_URL}${relative.startsWith("/") ? relative : `/${relative}`}`;
};

export const sourceDocumentUrl = (id: string) =>
  apiAsset(`/api/v1/documents/${encodeURIComponent(id)}/source`);

export const httpService = {
  listDocuments: () => req<FinDocument[]>("/documents"),
  getDocument: (id: string) => req<FinDocument>(`/documents/${encodeURIComponent(id)}`),
  getPages: (id: string) => req<DocumentPage[]>(`/documents/${encodeURIComponent(id)}/pages`),
  getEvidence: (id: string) => req<Evidence[]>(`/documents/${encodeURIComponent(id)}/evidence`),
  // Trends need financial extraction, which this backend milestone does not implement.
  getTrends: async (_id: string): Promise<TrendPoint[]> => {
    throw new ApiError(501, "not_implemented", "Trends are not available from the backend yet");
  },

  uploadDocument: (file: File, meta: UploadMeta = {}, onProgress?: (fraction: number) => void) => {
    if (!API_URL) {
      return Promise.reject(
        new ApiError(0, "backend_unavailable", "The document service URL is not configured."),
      );
    }
    return new Promise<{ document: FinDocument; job: Job }>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const fd = new FormData();
      fd.append("file", file);
      for (const [key, value] of Object.entries(meta)) {
        if (value) fd.append(key, value);
      }
      xhr.open("POST", `${V1}/documents`);
      xhr.timeout = UPLOAD_TIMEOUT_MS;
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && event.total > 0) onProgress?.(event.loaded / event.total);
      };
      xhr.onload = () => {
        let body: { document?: FinDocument; job?: Job; error?: { code?: string; message?: string } } | null =
          null;
        try {
          body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
        } catch {
          body = null;
        }
        if (xhr.status >= 200 && xhr.status < 300 && body?.document && body.job) {
          onProgress?.(1);
          resolve({ document: body.document, job: body.job });
          return;
        }
        reject(
          new ApiError(
            xhr.status,
            body?.error?.code ?? `http_${xhr.status}`,
            body?.error?.message ?? (xhr.statusText || "Upload failed"),
          ),
        );
      };
      xhr.onerror = () =>
        reject(
          new ApiError(
            0,
            "backend_unavailable",
            "The document service is not reachable. Check that the API is running.",
          ),
        );
      xhr.ontimeout = () =>
        reject(new ApiError(0, "timeout", "The upload timed out before the service accepted the PDF."));
      xhr.send(fd);
    });
  },
  getJob: (jobId: string) => req<Job>(`/jobs/${encodeURIComponent(jobId)}`),
  deleteDocument: (id: string) => req<void>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  reprocessDocument: (id: string) =>
    req<Job>(`/documents/${encodeURIComponent(id)}/reprocess`, { method: "POST" }),
};

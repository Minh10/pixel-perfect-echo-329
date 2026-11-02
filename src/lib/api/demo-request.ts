import { PDFDocument } from "pdf-lib";
import { z } from "zod";
import { MAX_JSON_BYTES, MAX_PDF_BYTES, MAX_PDF_PAGES } from "../temporary-demo";
const ids = z.array(z.string().regex(/^[A-Za-z0-9_-]{1,160}$/)).max(4).nullable().optional();
const shared = { documentIds: ids, method: z.enum(["bm25", "dense", "hybrid"]).optional(), chunkSet: z.enum(["layout", "flat"]).optional() };
const qa = z.object({ ...shared, question: z.string().min(3).max(2000), topK: z.number().int().min(1).max(5).optional(), includeFigures: z.boolean().optional() }).strict();
const retrieve = z.object({ ...shared, query: z.string().min(2).max(2000), k: z.number().int().min(1).max(5).optional(), rerank: z.literal(false).optional() }).strict();
export async function boundedBody(request: Request, max: number): Promise<Uint8Array> {
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks: Uint8Array[] = []; let total = 0;
  while (true) {
    const next = await reader.read(); if (next.done) break;
    total += next.value.length;
    if (total > max) { await reader.cancel(); throw new Error("Request exceeds demo size limit"); }
    chunks.push(next.value);
  }
  const bytes = new Uint8Array(total); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}
export async function validateDemoBody(request: Request, path: string): Promise<Uint8Array | undefined> {
  if (request.method === "GET") return undefined;
  const upload = path === "api/v1/documents" && request.method === "POST";
  const bytes = await boundedBody(request, upload ? MAX_PDF_BYTES + 16 * 1024 : MAX_JSON_BYTES);
  if (upload) {
    if (!request.headers.get("content-type")?.startsWith("multipart/form-data;")) throw new Error("Multipart PDF required");
    const form = await new Request(request.url, { method: "POST", headers: request.headers, body: bytes }).formData();
    if (Array.from(form.keys()).some(k => !["file", "title", "issuer", "period", "type"].includes(k))) throw new Error("Invalid upload metadata");
    const files = form.getAll("file"); const file = files[0];
    if (files.length !== 1 || !file || typeof file === "string" || file.size > MAX_PDF_BYTES) throw new Error("One PDF up to 10 MiB required");
    const content = await file.arrayBuffer();
    if (new TextDecoder().decode(content.slice(0, 5)) !== "%PDF-") throw new Error("PDF required");
    const pdf = await PDFDocument.load(content, { updateMetadata: false });
    if (pdf.getPageCount() < 1 || pdf.getPageCount() > MAX_PDF_PAGES) throw new Error("PDF must contain 1–30 pages");
    for (const [k, v] of form) if (k !== "file" && (typeof v !== "string" || v.length > (k === "period" ? 50 : 300))) throw new Error("Invalid metadata");
  } else if (path === "api/v1/qa" || path === "api/v1/retrieve") {
    if (!request.headers.get("content-type")?.startsWith("application/json")) throw new Error("JSON required");
    (path.endsWith("/qa") ? qa : retrieve).parse(JSON.parse(new TextDecoder().decode(bytes)));
  } else if (bytes.length > 0) throw new Error("This action does not accept a body");
  return bytes;
}
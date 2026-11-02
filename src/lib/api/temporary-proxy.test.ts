// @vitest-environment node
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { PDFDocument } from "pdf-lib";
vi.mock("@tanstack/react-start", () => ({ createServerOnlyFn: (fn: unknown) => fn }));
const guard = vi.hoisted(() => ({ consume: vi.fn(), valid: vi.fn() }));
vi.mock("../demo-guard", () => ({ demoGuard: async () => guard }));
import { proxyDocumentRequest, validDocumentQuery } from "./document-proxy";
import { signDemoSession, MAX_PDF_BYTES, MAX_PDF_PAGES } from "../temporary-demo";
import { validateDemoBody } from "./demo-request";
const config = {
  demoEnabled: "true",
  demoSecret: "test-fixture-not-deployed",
  backendUrl: "https://test.example",
  backendToken: "fixture-upstream",
};
async function req(path: string, method = "GET", body?: BodyInit, contentType?: string) {
  const cookie = await signDemoSession("12345678-1234-1234-1234-123456789abc", config.demoSecret);
  return new Request(`https://app.example/api/document-service/${path}`, {
    method,
    headers: {
      Cookie: `__Host-finaudit_demo=${cookie}`,
      Origin: "https://app.example",
      ...(contentType ? { "Content-Type": contentType } : {}),
    },
    ...(body ? { body } : {}),
  });
}
beforeEach(() => {
  guard.consume.mockResolvedValue(true);
  guard.valid.mockResolvedValue(true);
});
afterEach(() => vi.restoreAllMocks());
it.each([
  "pages",
  "pages/1/image",
  "blocks/chart/image",
  "source",
  "facts",
  "export/docling",
  "figures/chart/interpretation",
])("guards and streams %s", async (suffix) => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("resource", {
      headers: {
        "Content-Type": "application/pdf",
        "Set-Cookie": "must-not-pass",
        Authorization: "must-not-pass",
      },
    }),
  );
  const path = `api/v1/documents/report/${suffix}`;
  const response = await proxyDocumentRequest(await req(path), path, config);
  expect(response.status).toBe(200);
  expect(await response.text()).toBe("resource");
  const headers = new Headers(fetch.mock.calls[0]?.[1]?.headers);
  expect(headers.get("Authorization")).toBe("Bearer fixture-upstream");
  expect(headers.has("Cookie")).toBe(false);
  expect(response.headers.has("Authorization")).toBe(false);
  expect(response.headers.has("Set-Cookie")).toBe(false);
});
it("rejects no cookie, invalid cookie, revoked session and CSRF", async () => {
  const path = "api/v1/documents";
  expect(
    (await proxyDocumentRequest(new Request("https://app.example/api"), path, config)).status,
  ).toBe(401);
  expect(
    (
      await proxyDocumentRequest(
        new Request("https://app.example/api", {
          headers: { Cookie: "__Host-finaudit_demo=sample-only" },
        }),
        path,
        config,
      )
    ).status,
  ).toBe(401);
  guard.valid.mockResolvedValue(false);
  expect((await proxyDocumentRequest(await req(path), path, config)).status).toBe(401);
  guard.valid.mockResolvedValue(true);
  const request = await req(path, "POST");
  request.headers.set("Origin", "https://evil.example");
  expect((await proxyDocumentRequest(request, path, config)).status).toBe(403);
});
it("preserves legitimate multipart PDF upload bytes", async () => {
  const pdf = await PDFDocument.create();
  pdf.addPage();
  const form = new FormData();
  form.set(
    "file",
    new Blob([new Uint8Array(await pdf.save())], { type: "application/pdf" }),
    "report.pdf",
  );
  const request = await req("api/v1/documents", "POST", form);
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      Response.json({ document: { id: "real-fixture" }, job: { id: "job-fixture" } }),
    );
  const response = await proxyDocumentRequest(request, "api/v1/documents", config);
  expect(response.status).toBe(200);
  const outgoing = new Request("https://test.example", {
    method: "POST",
    headers: new Headers(fetch.mock.calls[0]?.[1]?.headers),
    body: fetch.mock.calls[0]?.[1]?.body ?? null,
  });
  const file = (await outgoing.formData()).get("file");
  expect(typeof file === "string" ? 0 : file?.size).toBeGreaterThan(0);
});
it("enforces concrete PDF size and page limits", async () => {
  expect(MAX_PDF_BYTES).toBe(10485760);
  expect(MAX_PDF_PAGES).toBe(30);
  const pdf = await PDFDocument.create();
  for (let i = 0; i < 31; i++) pdf.addPage();
  const form = new FormData();
  form.set("file", new Blob([new Uint8Array(await pdf.save())]), "too-long.pdf");
  await expect(
    validateDemoBody(await req("api/v1/documents", "POST", form), "api/v1/documents"),
  ).rejects.toThrow("1–30");
  const large = new FormData();
  large.set("file", new Blob([new Uint8Array(10485761)]), "large.pdf");
  await expect(
    validateDemoBody(await req("api/v1/documents", "POST", large), "api/v1/documents"),
  ).rejects.toThrow("10 MiB");
});
it("preserves QA/retrieval contract and bounds inputs", async () => {
  await expect(
    validateDemoBody(
      await req(
        "api/v1/qa",
        "POST",
        JSON.stringify({ question: "What is revenue?", documentIds: ["report"] }),
        "application/json",
      ),
      "api/v1/qa",
    ),
  ).resolves.toBeTruthy();
  await expect(
    validateDemoBody(
      await req(
        "api/v1/retrieve",
        "POST",
        JSON.stringify({
          query: "revenue",
          documentIds: ["report"],
          k: 5,
          method: "hybrid",
          chunkSet: "layout",
        }),
        "application/json",
      ),
      "api/v1/retrieve",
    ),
  ).resolves.toBeTruthy();
  await expect(
    validateDemoBody(
      await req(
        "api/v1/qa",
        "POST",
        JSON.stringify({ question: "revenue", topK: 50 }),
        "application/json",
      ),
      "api/v1/qa",
    ),
  ).rejects.toThrow();
  expect(validDocumentQuery("dpi", "999")).toBe(false);
  expect(validDocumentQuery("category", "disclosure")).toBe(true);
});
it("fails closed on rate/guard failure and blocks admin routes", async () => {
  guard.consume.mockResolvedValue(false);
  expect(
    (await proxyDocumentRequest(await req("api/v1/documents"), "api/v1/documents", config)).status,
  ).toBe(429);
  guard.consume.mockRejectedValue(new Error("offline"));
  expect(
    (await proxyDocumentRequest(await req("api/v1/documents"), "api/v1/documents", config)).status,
  ).toBe(503);
  expect(
    (await proxyDocumentRequest(await req("api/v1/admin"), "api/v1/admin", config)).status,
  ).toBe(404);
});
it("reserves global daily work/upload budgets and per-minute request caps", async () => {
  guard.consume.mockClear();
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ ok: true }));
  await proxyDocumentRequest(await req("api/v1/documents", "POST"), "api/v1/documents", config);
  const calls = guard.consume.mock.calls;
  expect(calls.some(([bucket, limit]) => bucket.startsWith("requests:") && limit === 120)).toBe(
    true,
  );
  expect(calls.some(([bucket, limit]) => bucket.startsWith("session:") && limit === 60)).toBe(true);
  expect(calls.some(([bucket, limit]) => bucket.startsWith("work:") && limit === 20)).toBe(true);
  expect(calls.some(([bucket, limit]) => bucket.startsWith("work-minute:") && limit === 2)).toBe(
    true,
  );
  expect(calls.some(([bucket, limit]) => bucket.startsWith("uploads:") && limit === 3)).toBe(true);
  expect(fetch).not.toHaveBeenCalled();
});
it("redacts upstream authentication errors and blocks redirects", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response("fixture-upstream", { status: 401 }));
  const response = await proxyDocumentRequest(
    await req("api/v1/documents"),
    "api/v1/documents",
    config,
  );
  expect(response.status).toBe(502);
  expect(await response.text()).not.toContain("fixture-upstream");
  fetch.mockResolvedValue(
    new Response(null, { status: 302, headers: { Location: "https://evil.example" } }),
  );
  expect(
    (await proxyDocumentRequest(await req("api/v1/documents"), "api/v1/documents", config)).status,
  ).toBe(502);
});

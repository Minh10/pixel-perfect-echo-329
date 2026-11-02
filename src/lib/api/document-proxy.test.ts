// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
vi.mock("@tanstack/react-start", () => ({ createServerOnlyFn: (fn: unknown) => fn }));
const auth = vi.hoisted(() => ({ getUser: vi.fn() }));
vi.mock("@supabase/supabase-js", () => ({ createClient: () => ({ auth }) }));
import { proxyDocumentRequest } from "./document-proxy";

describe("document proxy fails closed", () => {
  it("does not contact an upstream when configuration is missing", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await proxyDocumentRequest(
      new Request("https://app.example/api/document-service/api/v1/documents"),
      "api/v1/documents",
      {},
    );
    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
    upstream.mockRestore();
  });
  it("rejects an anonymous request even with service configuration", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await proxyDocumentRequest(
      new Request("https://app.example/api/document-service/api/v1/documents"),
      "api/v1/documents",
      {
        backendUrl: "https://documents.example.org",
        backendToken: "test-only-token",
        authorizedUserId: "owner",
        authUrl: "https://auth.example.org",
        authKey: "test-only-key",
      },
    );
    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
    upstream.mockRestore();
  });
  it.each([
    "api/v1/documents/report/pages",
    "api/v1/documents/report/pages/1/image",
    "api/v1/documents/report/blocks/chart/image",
    "api/v1/documents/report/source",
  ])("authenticates %s using the same HttpOnly session cookie", async (path) => {
    auth.getUser.mockResolvedValue({ data: { user: { id: "owner" } }, error: null });
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("test resource", { headers: { "Content-Type": "application/pdf" } }));
    const response = await proxyDocumentRequest(new Request(`https://app.example/api/document-service/${path}`, { headers: { Cookie: "__Host-finaudit_access=test-only-access" } }), path, {
      backendUrl: "https://documents.example.org", backendToken: "test-only-upstream", authorizedUserId: "owner", authUrl: "https://auth.example.org", authKey: "test-only-key",
    });
    expect(response.status).toBe(200);
    expect(auth.getUser).toHaveBeenCalledWith("test-only-access");
    expect(response.headers.get("Cache-Control")).toBe("private, no-store");
    expect(await response.text()).toBe("test resource");
    expect(upstream).toHaveBeenCalledOnce();
    upstream.mockRestore();
    auth.getUser.mockClear();
  });
  it("rejects a second account before requesting a private resource", async () => {
    auth.getUser.mockResolvedValue({ data: { user: { id: "other" } }, error: null });
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await proxyDocumentRequest(new Request("https://app.example/api/document-service/api/v1/documents", { headers: { Cookie: "__Host-finaudit_access=test-only-access" } }), "api/v1/documents", {
      backendUrl: "https://documents.example.org", backendToken: "test-only-upstream", authorizedUserId: "owner", authUrl: "https://auth.example.org", authKey: "test-only-key",
    });
    expect(response.status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();
    upstream.mockRestore();
  });
});

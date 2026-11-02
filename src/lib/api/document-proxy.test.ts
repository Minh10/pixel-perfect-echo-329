// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
vi.mock("@tanstack/react-start", () => ({ createServerOnlyFn: (fn: unknown) => fn }));
import { proxyDocumentRequest } from "./document-proxy";

describe("document proxy fails closed", () => {
  it("does not contact an upstream when configuration is missing", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await proxyDocumentRequest(new Request("https://app.example/api/document-service/api/v1/documents"), "api/v1/documents", {});
    expect(response.status).toBe(503);
    expect(upstream).not.toHaveBeenCalled();
    upstream.mockRestore();
  });
  it("rejects an anonymous request even with service configuration", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await proxyDocumentRequest(new Request("https://app.example/api/document-service/api/v1/documents"), "api/v1/documents", { backendUrl: "https://documents.example.org", backendToken: "test-only-token", authorizedUserId: "owner", authUrl: "https://auth.example.org", authKey: "test-only-key" });
    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
    upstream.mockRestore();
  });
});
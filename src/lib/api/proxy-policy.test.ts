import { describe, expect, it } from "vitest";
import { allowedProxyPath, authorizedUser, configuredBackend } from "./proxy-policy";

describe("private FastAPI proxy policy", () => {
  it("does not authorize anyone until the single account is configured", () => {
    expect(authorizedUser("owner", undefined)).toBe(false);
  });
  it("authorizes only the exact configured account", () => {
    expect(authorizedUser("owner", "owner")).toBe(true);
    expect(authorizedUser("visitor", "owner")).toBe(false);
  });
  it("preserves PDF intake and the existing document tools", () => {
    expect(allowedProxyPath("POST", "api/v1/documents")).toBe(true);
    expect(allowedProxyPath("GET", "api/v1/documents/report/pages/1/image")).toBe(true);
    expect(allowedProxyPath("GET", "api/v1/documents/report/source")).toBe(true);
    expect(allowedProxyPath("POST", "api/v1/documents/report/figures/chart/interpret")).toBe(true);
    expect(allowedProxyPath("GET", "api/v1/citations/chunk")).toBe(true);
    expect(allowedProxyPath("POST", "api/v1/qa")).toBe(true);
  });
  it("rejects arbitrary and encoded upstream paths", () => {
    for (const path of [
      "admin",
      "api/v1/../admin",
      "api/v1/documents/%2e%2e",
      "https://other.example/api/v1/documents",
    ])
      expect(allowedProxyPath("GET", path)).toBe(false);
  });
  it("accepts only a fixed HTTPS service origin", () => {
    expect(configuredBackend("https://documents.example.org")?.origin).toBe(
      "https://documents.example.org",
    );
    for (const url of [
      undefined,
      "http://documents.example.org",
      "https://localhost",
      "https://127.0.0.1",
      "https://documents.example.org/api/v1",
      "https://user:pass@documents.example.org",
    ])
      expect(configuredBackend(url)).toBeNull();
  });
});

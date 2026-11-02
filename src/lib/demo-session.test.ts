// @vitest-environment node
import { beforeEach, expect, it, vi } from "vitest";
vi.mock("@tanstack/react-start", () => ({ createServerOnlyFn: (fn: unknown) => fn }));
const guard = vi.hoisted(() => ({
  consume: vi.fn(),
  create: vi.fn(),
  valid: vi.fn(),
  revoke: vi.fn(),
}));
vi.mock("./demo-guard", () => ({ demoGuard: async () => guard }));
import { handleDemoSession } from "./demo-session";
import { verifyDemoSession } from "./temporary-demo";
const config = {
  demoEnabled: "true",
  demoSecret: "test-fixture-not-deployed",
  backendUrl: "https://test.example",
  backendToken: "fixture",
};
const request = (method = "POST", password = "admin", origin = "https://app.example") =>
  new Request("https://app.example/api/public/demo-session", {
    method,
    headers: { Origin: origin, "Content-Type": "application/json" },
    ...(method === "POST" ? { body: JSON.stringify({ username: "admin", password }) } : {}),
  });
beforeEach(() => {
  vi.clearAllMocks();
  guard.consume.mockResolvedValue(true);
  guard.valid.mockResolvedValue(true);
});
it("sets a signed Secure HttpOnly SameSite cookie only for demo entry", async () => {
  const response = await handleDemoSession(request(), config);
  expect(response.status).toBe(200);
  const header = response.headers.get("set-cookie") ?? "";
  expect(header).toContain("Secure; HttpOnly; SameSite=Strict");
  expect(header).toContain("Max-Age=3600");
  const value = header.split(";")[0]?.split("=")[1];
  expect(await verifyDemoSession(value, config.demoSecret)).toBeTruthy();
  expect(await response.json()).toEqual({ ok: true });
});
it("rejects incorrect credentials and cross-origin login", async () => {
  expect((await handleDemoSession(request("POST", "wrong"), config)).status).toBe(401);
  expect(
    (await handleDemoSession(request("POST", "admin", "https://evil.example"), config)).status,
  ).toBe(403);
});
it("fails closed when activation or durable budgets are unavailable", async () => {
  expect((await handleDemoSession(request(), {})).status).toBe(503);
  guard.consume.mockRejectedValue(new Error("offline"));
  expect((await handleDemoSession(request(), config)).status).toBe(503);
});
it("rejects unsupported methods and throttles entries", async () => {
  expect((await handleDemoSession(request("PUT"), config)).status).toBe(405);
  guard.consume.mockResolvedValue(false);
  expect((await handleDemoSession(request(), config)).status).toBe(429);
});
it("logout revokes the same session and clears its cookie", async () => {
  const login = await handleDemoSession(request(), config);
  const cookie = login.headers.get("set-cookie")?.split(";")[0] ?? "";
  const logout = await handleDemoSession(
    new Request("https://app.example/api/public/demo-session", {
      method: "DELETE",
      headers: { Origin: "https://app.example", Cookie: cookie },
    }),
    config,
  );
  expect(logout.status).toBe(200);
  expect(guard.revoke).toHaveBeenCalledOnce();
  expect(logout.headers.get("set-cookie")).toContain("Max-Age=0");
});

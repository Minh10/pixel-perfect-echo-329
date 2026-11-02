// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("@tanstack/react-start", () => ({ createServerOnlyFn: (fn: unknown) => fn }));
const guard = vi.hoisted(() => ({ consume: vi.fn(), valid: vi.fn() }));
vi.mock("../demo-guard", () => ({ demoGuard: async () => guard }));
const proxy = vi.hoisted(() => vi.fn());
vi.mock("../api/document-proxy", () => ({ proxyDocumentRequest: proxy }));
const gateway = vi.hoisted(() => vi.fn());
vi.mock("./responses.server", () => ({ createResponsesCall: gateway }));
const state = vi.hoisted(() => ({ payload: undefined as unknown }));
vi.mock("@/integrations/supabase/client.server", () => ({
  supabaseAdmin: {
    from: () => ({
      select: () => ({
        eq: () => ({
          maybeSingle: async () => ({ data: { payload: state.payload }, error: null }),
        }),
      }),
      upsert: async () => ({ error: null }),
    }),
  },
}));
import { handleChartSummary } from "./chart-summary.server";
import { signDemoSession } from "../temporary-demo";
async function request(
  origin = "https://app.example",
  body = { documentId: "report", blockId: "chart" },
) {
  const cookie = await signDemoSession("12345678-1234-1234-1234-123456789abc", "test-signing-key");
  return new Request("https://app.example/api/chart-summary", {
    method: "POST",
    headers: {
      Origin: origin,
      Cookie: `__Host-finaudit_demo=${cookie}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}
beforeEach(() => {
  vi.stubEnv("FINAUDIT_TEMPORARY_DEMO_ENABLED", "true");
  vi.stubEnv("FINAUDIT_DEMO_SESSION_SECRET", "test-signing-key");
  vi.stubEnv("FINAUDIT_BACKEND_URL", "https://fixture.example");
  vi.stubEnv("FINAUDIT_API_TOKEN", "test-token");
  vi.stubEnv("LOVABLE_API_KEY", "test-gateway-key");
  guard.valid.mockResolvedValue(true);
  guard.consume.mockResolvedValue(true);
  state.payload = undefined;
  proxy.mockImplementation(async (_request, path) =>
    path.endsWith("evidence")
      ? Response.json([
          { blockId: "chart", category: "figure", page: 1, excerpt: "Synthetic chart" },
        ])
      : new Response(new Uint8Array([1, 2]), { headers: { "Content-Type": "image/png" } }),
  );
});
afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllEnvs();
});
describe("signed Gateway chart endpoint", () => {
  it("starts AI after consuming POST JSON without cloning a used request body", async () => {
    gateway.mockImplementation((incoming: Request) => {
      expect(incoming.body).toBeNull();
      expect(incoming.bodyUsed).toBe(false);
      return {
        getRunId: () => undefined,
        result: {
          text: Promise.resolve("Synthetic chart summary"),
          fullStream: (async function* () {
            yield { type: "text-delta", text: "Synthetic chart summary" };
            yield { type: "finish", finishReason: "stop" };
          })(),
        },
      };
    });
    const response = await handleChartSummary(await request());
    expect(response.status).toBe(200);
    expect(await response.text()).toContain('"type":"done","summary":"Synthetic chart summary"');
    expect(gateway).toHaveBeenCalledTimes(1);
    expect(guard.consume).toHaveBeenCalledWith(
      expect.stringMatching(/^gateway-charts:\d{4}-\d{2}-\d{2}$/),
      200,
    );
  });
  it("rejects anonymous requests before storage or AI", async () => {
    expect(
      (await handleChartSummary(new Request("https://app.example/api/chart-summary"))).status,
    ).toBe(401);
    expect(gateway).not.toHaveBeenCalled();
  });
  it("rejects revoked sessions", async () => {
    guard.valid.mockResolvedValue(false);
    expect((await handleChartSummary(await request())).status).toBe(401);
    expect(gateway).not.toHaveBeenCalled();
  });
  it("rejects cross-origin paid requests", async () => {
    expect((await handleChartSummary(await request("https://other.example"))).status).toBe(403);
    expect(gateway).not.toHaveBeenCalled();
  });
  it("fails closed when demo is off", async () => {
    vi.stubEnv("FINAUDIT_TEMPORARY_DEMO_ENABLED", "false");
    expect((await handleChartSummary(await request())).status).toBe(503);
    expect(gateway).not.toHaveBeenCalled();
  });
  it("rejects arbitrary URLs as chart identifiers", async () => {
    expect(
      (
        await handleChartSummary(
          await request(undefined, {
            documentId: "report",
            blockId: "https://other.example/image",
          }),
        )
      ).status,
    ).toBe(400);
    expect(proxy).not.toHaveBeenCalled();
  });
  it("stops before AI when the 200 gateway allowance is exhausted", async () => {
    guard.consume.mockImplementation(
      async (bucket: string) => !bucket.startsWith("gateway-charts:"),
    );
    expect((await handleChartSummary(await request())).status).toBe(429);
    expect(guard.consume).toHaveBeenCalledWith(
      expect.stringMatching(/^gateway-charts:\d{4}-\d{2}-\d{2}$/),
      200,
    );
    expect(gateway).not.toHaveBeenCalled();
  });
  it("preserves 40 daily and 2 per minute work caps", async () => {
    guard.consume.mockImplementation(async (bucket: string) => !bucket.startsWith("work-minute:"));
    expect((await handleChartSummary(await request())).status).toBe(429);
    expect(guard.consume).toHaveBeenCalledWith(expect.stringMatching(/^work:/), 40);
    expect(guard.consume).toHaveBeenCalledWith(expect.stringMatching(/^work-minute:/), 2);
    expect(gateway).not.toHaveBeenCalled();
  });
  it("keeps provider denial paused across new requests", async () => {
    state.payload = { status: 403, message: "Provider access denied" };
    // No summary cached; supply pause only on the second read.
    const original = state.payload;
    let reads = 0;
    Object.defineProperty(state, "payload", {
      configurable: true,
      get: () => (++reads % 2 === 0 ? original : undefined),
    });
    expect((await handleChartSummary(await request())).status).toBe(403);
    expect((await handleChartSummary(await request())).status).toBe(403);
    expect(gateway).not.toHaveBeenCalled();
    Object.defineProperty(state, "payload", {
      configurable: true,
      writable: true,
      value: undefined,
    });
  });
});

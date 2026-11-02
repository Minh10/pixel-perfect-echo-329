// @vitest-environment node
import { describe, expect, it } from "vitest";
import { demoConfigured, demoSameOrigin, signDemoSession, verifyDemoSession, DEMO_TTL } from "./temporary-demo";
const secret = "unit-test-fixture-not-a-deployed-credential";
const id = "12345678-1234-1234-1234-123456789abc";
describe("temporary demo policy", () => {
  it("defaults off and requires all private configuration", () => {
    expect(demoConfigured({})).toBe(false);
    expect(demoConfigured({ demoEnabled: "true", demoSecret: secret, backendUrl: "https://test.example" })).toBe(false);
    expect(demoConfigured({ demoEnabled: "true", demoSecret: secret, backendUrl: "https://test.example", backendToken: "fixture" })).toBe(true);
  });
  it("expires a signed demo session after one hour", async () => {
    const cookie = await signDemoSession(id, secret, 100000);
    expect(DEMO_TTL).toBe(3600);
    expect(await verifyDemoSession(cookie, secret, 100001)).toBe(id);
    expect(await verifyDemoSession(cookie, secret, 100000 + 3600000)).toBeNull();
  });
  it("rejects tampered and unsigned cookies", async () => {
    expect(await verifyDemoSession("sample-only", secret)).toBeNull();
    const cookie = await signDemoSession(id, secret);
    expect(await verifyDemoSession(`X${cookie}`, secret)).toBeNull();
    expect(await verifyDemoSession(cookie, "wrong-fixture")).toBeNull();
  });
  it("requires same-origin mutation requests", () => {
    expect(demoSameOrigin(new Request("https://app.example/api", { headers: { Origin: "https://app.example" } }))).toBe(true);
    expect(demoSameOrigin(new Request("https://app.example/api"))).toBe(false);
    expect(demoSameOrigin(new Request("https://app.example/api", { headers: { Origin: "https://other.example" } }))).toBe(false);
  });
});
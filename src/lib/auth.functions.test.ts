// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  login: vi.fn(), save: vi.fn(), clear: vi.fn(), logout: vi.fn(), session: vi.fn(),
}));
vi.mock("@tanstack/react-start", () => ({ createServerFn: () => {
  const chain = { inputValidator: () => chain, handler: (fn: unknown) => fn };
  return chain;
} }));
vi.mock("@tanstack/react-start/server", () => ({
  getRequest: () => new Request("https://app.example/login", { headers: { Origin: "https://app.example" } }),
  setResponseHeader: vi.fn(), getCookie: vi.fn(),
}));
vi.mock("./auth-session", () => ({
  authClient: () => ({ auth: { signInWithPassword: mocks.login, signOut: mocks.logout } }),
  saveAuthCookies: mocks.save, clearAuthCookies: mocks.clear, readOwnerSession: mocks.session,
}));
import { signIn } from "./auth.functions";
const invoke = signIn as unknown as (input: { data: { email: string; password: string } }) => Promise<{ success: boolean; message: string }>;
describe("owner login server boundary", () => {
  beforeEach(() => { vi.clearAllMocks(); vi.stubEnv("FINAUDIT_AUTHORIZED_USER_ID", "owner"); });
  it("rejects a valid but unauthorized account and never creates cookies", async () => {
    mocks.login.mockResolvedValue({ data: { user: { id: "other" }, session: {} }, error: null });
    const result = await invoke({ data: { email: "test@example.org", password: "test-only" } });
    expect(result.success).toBe(false);
    expect(mocks.save).not.toHaveBeenCalled();
    expect(mocks.logout).toHaveBeenCalledOnce();
  });
  it("sets cookies only after the owner is authenticated and returns no tokens", async () => {
    const session = { access_token: "test-only-access", refresh_token: "test-only-refresh" };
    mocks.login.mockResolvedValue({ data: { user: { id: "owner" }, session }, error: null });
    const result = await invoke({ data: { email: "test@example.org", password: "test-only" } });
    expect(result).toEqual({ success: true, message: "" });
    expect(mocks.save).toHaveBeenCalledWith(session);
  });
  it("fails closed without an owner configuration", async () => {
    vi.stubEnv("FINAUDIT_AUTHORIZED_USER_ID", "");
    expect((await invoke({ data: { email: "test@example.org", password: "test-only" } })).success).toBe(false);
    expect(mocks.login).not.toHaveBeenCalled();
  });
});
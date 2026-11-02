import { describe, expect, it } from "vitest";
import { adminPassword as password } from "./admin-credential";
describe("administrator password requirement", () => {
  it("rejects the public admin default", () => {
    expect(password.safeParse("admin").success).toBe(false);
  });
  it("requires at least twelve characters", () => {
    expect(password.safeParse("12345678901").success).toBe(false);
    expect(password.safeParse("test-only-long-passphrase").success).toBe(true);
  });
});
// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  AUTH_COOKIE,
  AUTH_COOKIE_OPTIONS,
  REFRESH_COOKIE,
  isOwner,
  sameOrigin,
} from "./auth-policy";
describe("single-owner session policy", () => {
  it("only authorizes the configured account", () => {
    expect(isOwner("owner", "owner")).toBe(true);
    expect(isOwner("other", "owner")).toBe(false);
    expect(isOwner("owner", undefined)).toBe(false);
  });
  it("uses Secure HttpOnly SameSite cookies without a domain", () => {
    expect(AUTH_COOKIE_OPTIONS).toEqual({
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
    });
    expect(AUTH_COOKIE.startsWith("__Host-")).toBe(true);
    expect(REFRESH_COOKIE.startsWith("__Host-")).toBe(true);
  });
  it("rejects cross-site session changes", () => {
    expect(
      sameOrigin(
        new Request("https://app.example/login", { headers: { Origin: "https://app.example" } }),
      ),
    ).toBe(true);
    expect(
      sameOrigin(
        new Request("https://app.example/login", {
          headers: { Origin: "https://attacker.example" },
        }),
      ),
    ).toBe(false);
    expect(sameOrigin(new Request("https://app.example/login"))).toBe(false);
  });
});

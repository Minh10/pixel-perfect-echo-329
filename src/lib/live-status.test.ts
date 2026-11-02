import { describe, expect, it } from "vitest";
import { entryState } from "./live-status";

const status = (enabled: boolean, entered: boolean) => ({ checked: true, enabled, entered });

describe("entryState", () => {
  it("treats a stale sample-only entry as not live when the live demo is on", () => {
    expect(entryState(status(true, false), true)).toBe("activate");
  });
  it("is live only with a server-verified signed session", () => {
    expect(entryState(status(true, true), false)).toBe("live");
  });
  it("keeps sample entry when the live demo is off", () => {
    expect(entryState(status(false, false), true)).toBe("sample-entered");
    expect(entryState(status(false, false), false)).toBe("sample");
  });
  it("never reports live when the switch is off, even if a cookie was accepted earlier", () => {
    expect(entryState(status(false, true), false)).toBe("sample");
  });
});

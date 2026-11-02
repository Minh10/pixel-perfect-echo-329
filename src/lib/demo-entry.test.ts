import { describe, expect, it } from "vitest";
import { acceptsDemoEntry, setDemoEntry } from "./demo-entry";

describe("public sample entry only", () => {
  it("accepts exactly the requested public admin/admin combination", () => {
    expect(acceptsDemoEntry("admin", "admin")).toBe(true);
    expect(acceptsDemoEntry("admin", "wrong")).toBe(false);
    expect(acceptsDemoEntry("other", "admin")).toBe(false);
  });
  it("stores only a tab-local sample flag and removes it on demo exit", () => {
    setDemoEntry(true);
    expect(sessionStorage.getItem("finaudit-sample-entry")).toBe("sample-only");
    setDemoEntry(false);
    expect(sessionStorage.getItem("finaudit-sample-entry")).toBeNull();
  });
});
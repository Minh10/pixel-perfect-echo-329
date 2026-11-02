import { describe, expect, it } from "vitest";
import { defaultTrendSelection } from "./report-selection";
import type { FinDocument } from "./api/types";

function doc(partial: Pick<FinDocument, "id" | "uploadedAt" | "issuer" | "status">): FinDocument {
  return {
    title: partial.id,
    period: null,
    type: null,
    pages: 1,
    sizeMb: 1,
    ...partial,
  };
}

describe("defaultTrendSelection", () => {
  it("returns nothing when no report is ready", () => {
    expect(
      defaultTrendSelection([
        doc({ id: "a", uploadedAt: "2026-01-01", issuer: "North", status: "processing" }),
      ]),
    ).toEqual([]);
  });

  it("keeps a single ready report selected", () => {
    expect(
      defaultTrendSelection([
        doc({ id: "a", uploadedAt: "2026-01-01", issuer: "North", status: "ready" }),
      ]),
    ).toEqual(["a"]);
  });

  it("compares the preferred issuer instead of unrelated reports", () => {
    const selected = defaultTrendSelection(
      [
        doc({ id: "other", uploadedAt: "2026-03-01", issuer: "South", status: "ready" }),
        doc({ id: "new", uploadedAt: "2026-02-01", issuer: "North", status: "ready" }),
        doc({ id: "old", uploadedAt: "2026-01-01", issuer: "North", status: "ready" }),
      ],
      "old",
    );
    expect(selected).toEqual(["new", "old"]);
  });

  it("uses the two newest reports when issuers do not match", () => {
    expect(
      defaultTrendSelection([
        doc({ id: "a", uploadedAt: "2026-01-01", issuer: "North", status: "ready" }),
        doc({ id: "b", uploadedAt: "2026-03-01", issuer: "South", status: "ready" }),
        doc({ id: "c", uploadedAt: "2026-02-01", issuer: "East", status: "ready" }),
      ]),
    ).toEqual(["b", "c"]);
  });
});

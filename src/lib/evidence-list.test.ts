import { describe, expect, it } from "vitest";
import { evidenceRows, readableExcerpt } from "./evidence-list";
import type { Evidence } from "@/lib/api/types";

const ev = (id: string, page: number, category: Evidence["category"], excerpt: string): Evidence => ({
  id,
  page,
  blockId: id,
  category,
  label: id,
  excerpt,
  confidence: null,
  related: [],
});

describe("evidence list", () => {
  it("replaces empty 0x0 table text", () => {
    expect(readableExcerpt(ev("t", 1, "table", "0×0 table"))).toBe(
      "Table (structure not extracted)",
    );
  });

  it("groups uncaptioned figures per page", () => {
    const fig = "Figure region (no caption detected; content not extracted)";
    const rows = evidenceRows([ev("a", 10, "figure", fig), ev("b", 10, "figure", fig), ev("c", 10, "figure", fig)], 1);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ kind: "group", page: 10, count: 3 });
  });

  it("lists current page first", () => {
    const rows = evidenceRows([ev("a", 2, "table", "x"), ev("b", 5, "table", "y")], 5);
    expect(rows[0]).toMatchObject({ kind: "item", evidence: { id: "b" } });
  });
});

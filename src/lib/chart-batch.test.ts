import { describe, expect, it } from "vitest";
import { chartStatus, chartsToRead, summariseCharts } from "./chart-batch";
import type { ChartInterpretation } from "@/lib/api/types";

const reading = { tableChecks: [] } as unknown as ChartInterpretation;

describe("chart batch", () => {
  it("only reads charts without a stored reading", () => {
    expect(chartsToRead(["a", "b", "c"], { b: reading })).toEqual(["a", "c"]);
  });
  it("marks missing readings as unread and empty checks as no-values", () => {
    expect(chartStatus(undefined, [])).toBe("unread");
    expect(chartStatus(reading, [])).toBe("no-values");
  });
  it("counts each status", () => {
    expect(summariseCharts(["unread", "match", "match", "discrepancy"])).toMatchObject({
      unread: 1,
      match: 2,
      discrepancy: 1,
      insufficient: 0,
    });
  });
});

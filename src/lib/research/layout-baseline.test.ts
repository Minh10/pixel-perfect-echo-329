import { describe, expect, it } from "vitest";
import baseline from "./layout-baseline.json";
describe("Published layout baseline", () => {
  it("retains the actual 200-page experiment and IoU 0.5", () => {
    expect(baseline.sampleSize).toBe(200);
    expect(baseline.iou).toBe(0.5);
    expect(baseline.scoreThreshold).toBe(0.3);
  });
  it("preserves table and figure counts, including false positives", () => {
    expect(baseline.metrics.find((row) => row.class === "table")?.tp).toBe(91);
    expect(baseline.metrics.find((row) => row.class === "figure")?.fp).toBe(215);
  });
});

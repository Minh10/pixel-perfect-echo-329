import { describe, expect, it } from "vitest";
import { pdfDisplayWidth } from "./pdf-view";

describe("PDF reader fit", () => {
  it("fits available width instead of a fixed small sheet", () => {
    expect(pdfDisplayWidth("width", 900, 800, 210 / 297, 1)).toBe(852);
  });
  it("fits an A4 page inside both canvas dimensions", () => {
    const width = pdfDisplayWidth("page", 900, 800, 210 / 297, 1);
    expect(width / (210 / 297)).toBeCloseTo(728);
    expect(width).toBeLessThan(852);
  });
  it("keeps explicit zoom independent of pane resizing", () => {
    expect(pdfDisplayWidth("custom", 900, 800, 210 / 297, 1.5)).toBe(1191);
    expect(pdfDisplayWidth("custom", 700, 600, 210 / 297, 1.5)).toBe(1191);
  });
});

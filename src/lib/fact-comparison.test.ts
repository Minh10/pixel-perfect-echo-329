import { describe, expect, it } from "vitest";
import { compareReports, visualDiscrepancy } from "./fact-comparison";
import type { FinancialFact, TableCheck } from "@/lib/api/types";

function fact(overrides: Partial<FinancialFact>): FinancialFact {
  return {
    factId: "f",
    normalizationVersion: "v1",
    documentId: "d",
    issuer: "Example",
    sourceSha256: "abc",
    tableId: "t",
    page: 2,
    rowIndex: 1,
    colIndices: [1],
    slotIndex: 0,
    rowLabel: "Revenue",
    rowGroup: null,
    columnHeader: "2025",
    cellText: "4,812",
    value: "4812",
    valueStatus: "parsed",
    isPercent: false,
    period: {
      label: "2025",
      fiscalYear: 2025,
      endDate: null,
      periodType: "annual",
      source: "column_header",
    },
    scale: "millions",
    scaleSource: "table",
    currency: "GBP",
    currencySource: "table",
    scope: "consolidated",
    scopeSource: "table",
    bbox: null,
    parser: "docling",
    parserVersion: "2",
    ...overrides,
  };
}

describe("compareReports", () => {
  it("plots two aligned reported values and calls the result a comparison", () => {
    const result = compareReports(
      [
        { documentId: "a", title: "Report A", facts: [fact({ documentId: "a", factId: "a1" })] },
        {
          documentId: "b",
          title: "Report B",
          facts: [
            fact({
              documentId: "b",
              factId: "b1",
              value: "4281",
              cellText: "4,281",
              period: {
                label: "2024",
                fiscalYear: 2024,
                endDate: null,
                periodType: "annual",
                source: "column_header",
              },
            }),
          ],
        },
      ],
      "Revenue",
    );
    expect(result.points.map((point) => point.displayValue)).toEqual(["4281", "4812"]);
    expect(result.note).toContain("not a comprehensive trend");
  });

  it("does not plot a value with a different currency", () => {
    const result = compareReports(
      [
        { documentId: "a", title: "A", facts: [fact({ factId: "a1" })] },
        {
          documentId: "b",
          title: "B",
          facts: [fact({ documentId: "b", factId: "b1", currency: "USD" })],
        },
      ],
      "revenue",
    );
    expect(result.points).toHaveLength(1);
    expect(result.note).toContain("left out");
  });

  it("shows one observation when two reports agree on the same year", () => {
    const result = compareReports(
      [
        {
          documentId: "a",
          title: "Annual Report 2024",
          facts: [fact({ documentId: "a", factId: "a1", value: "3200", cellText: "3,200" })],
        },
        {
          documentId: "b",
          title: "Annual Report 2025",
          facts: [fact({ documentId: "b", factId: "b1", value: "3200", cellText: "3,200" })],
        },
      ],
      "Revenue",
    );
    expect(result.points).toHaveLength(1);
    expect(result.points[0]?.documentTitle).toBe("Annual Report 2025");
    expect(result.note).toContain("shown once");
  });

  it("does not plot a year when the reports disagree", () => {
    const result = compareReports(
      [
        {
          documentId: "a",
          title: "Annual Report 2024",
          facts: [fact({ factId: "a1", value: "3200" })],
        },
        {
          documentId: "b",
          title: "Annual Report 2025",
          facts: [fact({ factId: "b1", value: "3000" })],
        },
      ],
      "Revenue",
    );
    expect(result.points).toHaveLength(0);
    expect(result.note).toContain("disagree");
  });
});

describe("visualDiscrepancy", () => {
  const check = (status: TableCheck["status"]): TableCheck => ({
    label: "Revenue",
    estimate: "4800",
    tableValue: status === "no_table_evidence" ? null : "4812",
    tableChunkId: null,
    relativeDifference: null,
    status,
  });

  it("refuses a discrepancy when several facts could match", () => {
    const result = visualDiscrepancy(check("conflict"), [
      fact({ factId: "1" }),
      fact({ factId: "2", period: { ...fact({}).period, fiscalYear: 2024, label: "2024" } }),
    ]);
    expect(result.status).toBe("INSUFFICIENT_EVIDENCE");
  });

  it("labels a single aligned conflict as potential, not verified", () => {
    const result = visualDiscrepancy({ ...check("conflict"), factId: "f" }, [fact({})]);
    expect(result.status).toBe("POTENTIAL_DISCREPANCY");
    expect(result.detail).toContain("not a verified discrepancy");
    expect(result.page).toBe(2);
  });

  it("does not treat an unlinked chart reading as a discrepancy", () => {
    const result = visualDiscrepancy(check("conflict"), [fact({})]);
    expect(result.status).toBe("INSUFFICIENT_EVIDENCE");
  });
});

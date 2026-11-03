import { describe, expect, it } from "vitest";
import { libraryTrend, loadLibraryIntelligence, type LibraryIntelligence } from "./library-intelligence";
import type { FinancialFact } from "./api/types";
import type { FinAuditService } from "./api/service";

const fact = (documentId: string, year: number, issuer = "Public issuer"): FinancialFact => ({
  factId: `${documentId}-fact`, documentId, issuer, normalizationVersion: "1", sourceSha256: "public", tableId: "table-1", page: 1, rowIndex: 1, colIndices: [1], slotIndex: 0, rowLabel: "Revenue", rowGroup: null, columnHeader: `${year}`, cellText: "100", value: "100", valueStatus: "parsed", isPercent: false, period: { label: `${year}`, fiscalYear: year, endDate: null, periodType: "annual", source: "column_header" }, scale: "millions", scaleSource: "header", currency: "USD", currencySource: "header", scope: "consolidated", scopeSource: "header", bbox: null, parser: "docling", parserVersion: "1",
});
const data = (facts: FinancialFact[]): LibraryIntelligence => ({ reports: [], evidence: [], readings: [], facts, unavailable: new Set(), sample: false });

describe("Conservative library preview", () => {
  it("links compatible periods from two reports to source page 1", () => {
    const result = libraryTrend(data([fact("a", 2024), fact("b", 2025)]));
    expect(result?.points.map((point) => [point.documentId, point.page])).toEqual([["a", 1], ["b", 1]]);
  });
  it("never compares different issuers", () => expect(libraryTrend(data([fact("a", 2024), fact("b", 2025, "Other issuer")]))).toBeNull());
  it("never mixes annual and quarterly periods", () => {
    const quarter = fact("b", 2025); quarter.period.periodType = "quarterly";
    expect(libraryTrend(data([fact("a", 2024), quarter]))).toBeNull();
  });
  it("never mixes currencies", () => {
    const other = fact("b", 2025); other.currency = "GBP";
    expect(libraryTrend(data([fact("a", 2024), other]))).toBeNull();
  });
  it("does not present a synthetic series as real financial findings", () => {
    expect(libraryTrend({ ...data([fact("a", 2024), fact("b", 2025)]), sample: true })).toBeNull();
  });
  it("marks missing fact and reading capabilities unavailable, not measured zero", async () => {
    const service: FinAuditService = { listDocuments: async () => [], getDocument: async () => { throw new Error(); }, getPages: async () => [], getEvidence: async () => [], getTrends: async () => [] };
    const result = await loadLibraryIntelligence(service, [], false, null);
    expect([...result.unavailable]).toEqual(["facts", "readings"]);
  });
});
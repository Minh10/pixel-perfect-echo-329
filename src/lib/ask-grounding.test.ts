import { describe, expect, it } from "vitest";
import { groundedRequest, supportedQuestions } from "./ask-grounding";
import type { FinancialFact } from "./api/types";

const fact = {
  documentId: "berkshire",
  rowLabel: "Net earnings attributable to Berkshire shareholders ........",
  value: "4603",
  valueStatus: "parsed",
  period: { label: "First Quarter 2025", source: "column_header" },
} as FinancialFact;

describe("document-grounded questions", () => {
  it("suggests the extracted metric and period, not an invented annual period", () => {
    expect(supportedQuestions([fact], "berkshire")).toEqual([
      "What was Net earnings attributable to Berkshire shareholders for First Quarter 2025?",
    ]);
  });
  it("does not suggest another report's facts or unknown periods", () => {
    expect(supportedQuestions([fact], "other")).toEqual([]);
    expect(
      supportedQuestions([{ ...fact, period: { ...fact.period, source: "unknown" } }], "berkshire"),
    ).toEqual([]);
  });
  it("does not suggest unparsed values", () => {
    expect(
      supportedQuestions([{ ...fact, valueStatus: "malformed", value: null }], "berkshire"),
    ).toEqual([]);
  });
  it("keeps the open PDF in scope and uses the allowed five retrieval results", () => {
    expect(groundedRequest("  What were earnings?  ", ["other", "other"], "berkshire")).toEqual({
      question: "What were earnings?",
      documentIds: ["berkshire", "other"],
      topK: 5,
    });
  });
});

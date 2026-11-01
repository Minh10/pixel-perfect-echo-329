// DEMO data only. Fictional issuer; not real financial information.
import type { DocumentPage, Evidence, FinDocument, TrendPoint } from "./types";

export const DEMO_DOCUMENTS: FinDocument[] = [
  { id: "nhc-ar-2025", title: "Northwind Holdings — Annual Report 2025", issuer: "Northwind Holdings plc (Demo)", period: "FY2025", type: "Annual Report", pages: 6, uploadedAt: "2026-10-28", status: "ready", sizeMb: 8.4 },
  { id: "nhc-q3-2026", title: "Northwind Holdings — Q3 2026 Interim", issuer: "Northwind Holdings plc (Demo)", period: "Q3 2026", type: "Quarterly Report", pages: 24, uploadedAt: "2026-10-30", status: "processing", sizeMb: 2.1 },
  { id: "arc-esg-2025", title: "Arcadia Energy — Sustainability Report", issuer: "Arcadia Energy SA (Demo)", period: "FY2025", type: "Sustainability Report", pages: 88, uploadedAt: "2026-10-21", status: "ready", sizeMb: 14.9 },
  { id: "hel-pro-2026", title: "Helix Bio — IPO Prospectus", issuer: "Helix Bio Inc. (Demo)", period: "2026", type: "Prospectus", pages: 212, uploadedAt: "2026-10-12", status: "failed", sizeMb: 31.2 },
];

export const DEMO_PAGES: DocumentPage[] = [
  {
    number: 1, section: "Cover",
    blocks: [
      { id: "p1-h", kind: "heading", text: "Northwind Holdings plc — Annual Report and Accounts 2025" },
      { id: "p1-p1", kind: "paragraph", text: "Building resilient infrastructure for a connected economy. This report covers the financial year ended 31 December 2025." },
    ],
  },
  {
    number: 2, section: "Chair's statement",
    blocks: [
      { id: "p2-h", kind: "heading", text: "Chair's statement" },
      { id: "p2-p1", kind: "paragraph", text: "2025 was a year of disciplined growth. Group revenue increased 12.4% to £4,812 million, driven by strong demand in our Networks division and continued pricing discipline across Services." },
      { id: "p2-p2", kind: "paragraph", text: "Operating margin expanded by 80 basis points to 14.6%, reflecting procurement savings and the completion of our efficiency programme. The Board proposes a final dividend of 18.2p per share." },
      { id: "p2-p3", kind: "paragraph", text: "We remain mindful of macroeconomic uncertainty, particularly energy input costs, which we discuss in the Principal Risks section." },
    ],
  },
  {
    number: 3, section: "Financial review",
    blocks: [
      { id: "p3-h", kind: "heading", text: "Financial review" },
      { id: "p3-p1", kind: "paragraph", text: "The table below summarises the Group income statement. All figures are presented in £ millions unless otherwise stated." },
      {
        id: "p3-t1", kind: "table",
        table: {
          columns: ["", "2025", "2024", "Change"],
          rows: [
            { label: "Revenue", values: ["4,812", "4,281", "+12.4%"], emphasis: true },
            { label: "Cost of sales", values: ["(3,018)", "(2,722)", "+10.9%"] },
            { label: "Gross profit", values: ["1,794", "1,559", "+15.1%"] },
            { label: "Operating expenses", values: ["(1,091)", "(968)", "+12.7%"] },
            { label: "Operating profit", values: ["703", "591", "+18.9%"], emphasis: true },
            { label: "Net finance costs", values: ["(84)", "(77)", "+9.1%"] },
            { label: "Profit before tax", values: ["619", "514", "+20.4%"] },
            { label: "Profit for the year", values: ["471", "392", "+20.2%"], emphasis: true },
          ],
        },
      },
      { id: "p3-p2", kind: "paragraph", text: "Operating profit of £703 million corresponds to an operating margin of 14.6% (2024: 13.8%)." },
    ],
  },
  {
    number: 4, section: "Segment performance",
    blocks: [
      { id: "p4-h", kind: "heading", text: "Segment performance" },
      { id: "p4-c1", kind: "chart", chart: { title: "Revenue by segment, 2025 (£m)", series: [ { label: "Networks", value: 2410 }, { label: "Services", value: 1580 }, { label: "Energy", value: 612 }, { label: "Other", value: 210 } ] } },
      { id: "p4-p1", kind: "paragraph", text: "Networks remained the largest segment, contributing approximately half of Group revenue. Energy revenue declined 3% as legacy contracts rolled off." },
    ],
  },
  {
    number: 5, section: "Cash flow",
    blocks: [
      { id: "p5-h", kind: "heading", text: "Cash flow and balance sheet" },
      {
        id: "p5-t1", kind: "table",
        table: {
          columns: ["", "2025", "2024"],
          rows: [
            { label: "Cash generated from operations", values: ["812", "701"] },
            { label: "Capital expenditure", values: ["(366)", "(342)"] },
            { label: "Free cash flow", values: ["446", "359"], emphasis: true },
            { label: "Net debt at year end", values: ["1,204", "1,318"] },
          ],
        },
      },
      { id: "p5-p1", kind: "paragraph", text: "Leverage, measured as net debt to EBITDA, fell to 1.3x (2024: 1.6x), within our target range of 1.0x–1.5x." },
    ],
  },
  {
    number: 6, section: "Principal risks",
    blocks: [
      { id: "p6-h", kind: "heading", text: "Principal risks" },
      { id: "p6-p1", kind: "paragraph", text: "Energy price volatility: a 10% increase in wholesale energy prices would reduce operating profit by an estimated £22 million." },
      { id: "p6-p2", kind: "paragraph", text: "Customer concentration: our top five customers account for 31% of Group revenue." },
    ],
  },
];

export const DEMO_EVIDENCE: Evidence[] = [
  { id: "ev-rev-narr", page: 2, blockId: "p2-p1", category: "metric", label: "Group revenue (narrative)", excerpt: "Group revenue increased 12.4% to £4,812 million…", extracted: [ { field: "Revenue FY2025", value: "4,812", unit: "£m" }, { field: "YoY growth", value: "12.4", unit: "%" } ], confidence: 0.96, related: ["ev-is-table", "ev-seg-chart"] },
  { id: "ev-margin", page: 2, blockId: "p2-p2", category: "metric", label: "Operating margin & dividend", excerpt: "Operating margin expanded by 80 basis points to 14.6%…", extracted: [ { field: "Operating margin", value: "14.6", unit: "%" }, { field: "Final dividend", value: "18.2", unit: "p/share" } ], confidence: 0.93, related: ["ev-margin-calc"] },
  { id: "ev-is-table", page: 3, blockId: "p3-t1", category: "table", label: "Group income statement", excerpt: "Summary income statement, 2025 vs 2024 (£m).", extracted: [ { field: "Revenue", value: "4,812", unit: "£m" }, { field: "Operating profit", value: "703", unit: "£m" }, { field: "Profit for the year", value: "471", unit: "£m" } ], confidence: 0.91, related: ["ev-rev-narr", "ev-margin-calc"] },
  { id: "ev-margin-calc", page: 3, blockId: "p3-p2", category: "disclosure", label: "Operating margin statement", excerpt: "Operating profit of £703 million corresponds to an operating margin of 14.6%…", extracted: [ { field: "Operating margin", value: "14.6", unit: "%" } ], confidence: 0.94, related: ["ev-margin", "ev-is-table"] },
  { id: "ev-seg-chart", page: 4, blockId: "p4-c1", category: "chart", label: "Revenue by segment", excerpt: "Bar chart of 2025 segment revenue.", extracted: [ { field: "Networks", value: "2,410", unit: "£m" }, { field: "Services", value: "1,580", unit: "£m" }, { field: "Energy", value: "612", unit: "£m" }, { field: "Other", value: "210", unit: "£m" } ], confidence: 0.82, related: ["ev-rev-narr"] },
  { id: "ev-fcf", page: 5, blockId: "p5-t1", category: "table", label: "Cash flow summary", excerpt: "Cash generation, capex, free cash flow and net debt.", extracted: [ { field: "Free cash flow", value: "446", unit: "£m" }, { field: "Net debt", value: "1,204", unit: "£m" } ], confidence: 0.9, related: ["ev-leverage"] },
  { id: "ev-leverage", page: 5, blockId: "p5-p1", category: "disclosure", label: "Leverage ratio", excerpt: "Net debt to EBITDA fell to 1.3x (2024: 1.6x)…", extracted: [ { field: "Net debt / EBITDA", value: "1.3", unit: "x" } ], confidence: 0.95, related: ["ev-fcf"] },
  { id: "ev-energy-risk", page: 6, blockId: "p6-p1", category: "disclosure", label: "Energy price sensitivity", excerpt: "A 10% increase in wholesale energy prices would reduce operating profit by £22 million.", extracted: [ { field: "Sensitivity", value: "-22", unit: "£m per +10%" } ], confidence: 0.88, related: [] },
];

export const DEMO_TRENDS: TrendPoint[] = [
  { period: "FY2021", revenue: 3420, operatingIncome: 401, netIncome: 262 },
  { period: "FY2022", revenue: 3705, operatingIncome: 455, netIncome: 301 },
  { period: "FY2023", revenue: 3990, operatingIncome: 528, netIncome: 349 },
  { period: "FY2024", revenue: 4281, operatingIncome: 591, netIncome: 392 },
  { period: "FY2025", revenue: 4812, operatingIncome: 703, netIncome: 471 },
];

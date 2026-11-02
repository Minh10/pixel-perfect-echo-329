import { visualDiscrepancy } from "@/lib/fact-comparison";
import type { ChartInterpretation } from "@/lib/api/types";

type Facts = Parameters<typeof visualDiscrepancy>[1];

export type ChartStatus = "unread" | "match" | "discrepancy" | "insufficient" | "no-values";

/** Figures that still need a model reading; stored readings are never re-requested. */
export function chartsToRead(
  blockIds: string[],
  readings: Record<string, ChartInterpretation | undefined>,
): string[] {
  return blockIds.filter((id) => !readings[id]);
}

/** Worst-case status for one chart reading against the document's table facts. */
export function chartStatus(reading: ChartInterpretation | undefined, facts: Facts): ChartStatus {
  if (!reading) return "unread";
  const results = (reading.tableChecks ?? []).map(
    (check) => visualDiscrepancy(check, facts).status,
  );
  if (results.length === 0) return "no-values";
  if (results.includes("POTENTIAL_DISCREPANCY")) return "discrepancy";
  if (results.every((status) => status === "MATCH")) return "match";
  return "insufficient";
}

export function summariseCharts(statuses: ChartStatus[]): Record<ChartStatus, number> {
  const counts: Record<ChartStatus, number> = {
    unread: 0,
    match: 0,
    discrepancy: 0,
    insufficient: 0,
    "no-values": 0,
  };
  for (const status of statuses) counts[status] += 1;
  return counts;
}

import type { FinancialFact, TableCheck } from "@/lib/api/types";

export type ComparisonStatus = "MATCH" | "POTENTIAL_DISCREPANCY" | "INSUFFICIENT_EVIDENCE";

export interface ComparedPoint {
  documentId: string;
  documentTitle: string;
  factId: string;
  /** Evidence id for the source table, `ev-{tableId}`. */
  tableEvidenceId: string;
  page: number;
  periodLabel: string;
  sortKey: number;
  value: number;
  displayValue: string;
  scale: string;
  currency: string | null;
  scope: string;
  rowLabel: string;
}

const norm = (value: string) => value.toLowerCase().replace(/\s+/g, " ").trim();

export function compareReports(
  groups: { documentId: string; title: string; facts: FinancialFact[] }[],
  metric: string,
): { points: ComparedPoint[]; note: string } {
  const wanted = norm(metric);
  const candidates = groups.flatMap((group) =>
    group.facts
      .filter(
        (fact) =>
          fact.valueStatus === "parsed" &&
          fact.value != null &&
          norm(fact.rowLabel) === wanted &&
          Number.isFinite(Number(fact.value)),
      )
      .map((fact) => ({ group, fact })),
  );
  if (candidates.length === 0) {
    return {
      points: [],
      note: "No parsed table value matches that metric. Nothing is plotted.",
    };
  }
  const signature = (fact: FinancialFact) =>
    [fact.scale, fact.currency ?? "", fact.scope, fact.isPercent ? "percent" : "amount"].join("|");
  const counts = new Map<string, number>();
  for (const item of candidates) {
    const key = signature(item.fact);
    const docs = new Set(
      candidates
        .filter((other) => signature(other.fact) === key)
        .map((other) => other.group.documentId),
    );
    counts.set(key, docs.size);
  }
  const best = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  const aligned = candidates.filter((item) => signature(item.fact) === best);
  const dropped = candidates.length - aligned.length;
  const byDocPeriod = new Map<string, ComparedPoint>();
  let ambiguous = false;
  for (const { group, fact } of aligned) {
    const periodLabel = fact.period.fiscalYear?.toString() ?? fact.period.label ?? "period unknown";
    const key = `${group.documentId}:${periodLabel}`;
    const point: ComparedPoint = {
      documentId: group.documentId,
      documentTitle: group.title,
      factId: fact.factId,
      tableEvidenceId: `ev-${fact.tableId}`,
      page: fact.page,
      periodLabel,
      sortKey: fact.period.fiscalYear ?? Number.MAX_SAFE_INTEGER,
      value: Number(fact.value),
      displayValue: fact.value ?? fact.cellText,
      scale: fact.scale,
      currency: fact.currency,
      scope: fact.scope,
      rowLabel: fact.rowLabel,
    };
    const existing = byDocPeriod.get(key);
    if (existing && existing.displayValue !== point.displayValue) ambiguous = true;
    if (!existing) byDocPeriod.set(key, point);
  }
  if (ambiguous) {
    return {
      points: [],
      note: "More than one parsed value exists for the same report and period. The comparison is not plotted.",
    };
  }
  const points = [...byDocPeriod.values()].sort(
    (a, b) => a.sortKey - b.sortKey || a.documentTitle.localeCompare(b.documentTitle),
  );
  const sample = points[0];
  const note = [
    sample
      ? `Aligned on ${sample.rowLabel}, scale ${sample.scale}, currency ${sample.currency ?? "not stated"}, scope ${sample.scope}.`
      : "",
    dropped > 0
      ? `${dropped} value(s) were left out because unit, currency, or scope did not match.`
      : "",
    points.length <= 2
      ? "This is a comparison of the aligned reported values, not a comprehensive trend."
      : "",
  ]
    .filter(Boolean)
    .join(" ");
  return { points, note };
}

export function visualDiscrepancy(
  check: TableCheck,
  facts: FinancialFact[],
): { status: ComparisonStatus; detail: string } {
  const label = norm(check.label);
  const matches = facts.filter(
    (fact) =>
      fact.valueStatus === "parsed" && norm(fact.rowLabel).includes(label) && label.length > 0,
  );
  if (check.status === "no_table_evidence" || matches.length === 0) {
    return {
      status: "INSUFFICIENT_EVIDENCE",
      detail: "No reported table fact is aligned with this chart reading.",
    };
  }
  const scales = new Set(
    matches.map((fact) => `${fact.scale}|${fact.currency ?? ""}|${fact.scope}`),
  );
  if (scales.size !== 1 || matches.length !== 1) {
    return {
      status: "INSUFFICIENT_EVIDENCE",
      detail:
        "Several table facts could match this label, so period, unit, or scope is not unique.",
    };
  }
  if (check.status === "consistent") {
    return {
      status: "MATCH",
      detail: `Visual estimate ${check.estimate} is close to reported ${matches[0]?.cellText}. The chart value remains an estimate.`,
    };
  }
  if (check.status === "conflict") {
    return {
      status: "POTENTIAL_DISCREPANCY",
      detail: `Visual estimate ${check.estimate} differs from reported ${matches[0]?.cellText}. This is not a verified discrepancy.`,
    };
  }
  return { status: "INSUFFICIENT_EVIDENCE", detail: "The chart reading could not be checked." };
}

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
  const ordered = [...byDocPeriod.values()].sort(
    (a, b) => a.sortKey - b.sortKey || a.documentTitle.localeCompare(b.documentTitle),
  );
  const byPeriod = new Map<string, ComparedPoint[]>();
  for (const point of ordered) {
    const group = byPeriod.get(point.periodLabel) ?? [];
    group.push(point);
    byPeriod.set(point.periodLabel, group);
  }
  const points: ComparedPoint[] = [];
  const conflicts: string[] = [];
  let collapsed = 0;
  for (const [period, group] of byPeriod) {
    const values = new Set(group.map((point) => point.displayValue));
    if (values.size > 1) {
      conflicts.push(period);
      continue;
    }
    collapsed += group.length - 1;
    points.push(group.find((point) => point.documentTitle.includes(period)) ?? group[0]!);
  }
  const sample = points[0];
  const note = [
    sample
      ? `Aligned on ${sample.rowLabel}, scale ${sample.scale}, currency ${sample.currency ?? "not stated"}, scope ${sample.scope}.`
      : "",
    dropped > 0
      ? `${dropped} value(s) were left out because unit, currency, or scope did not match.`
      : "",
    collapsed > 0 ? "Overlapping years that report the same value are shown once." : "",
    conflicts.length > 0
      ? `${conflicts.join(", ")} is not plotted because the reports disagree.`
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
): { status: ComparisonStatus; detail: string; page: number | null; evidenceId: string | null } {
  const linked = check.factId ? facts.find((fact) => fact.factId === check.factId) : undefined;
  const aligned =
    linked != null &&
    linked.valueStatus === "parsed" &&
    (check.tableValue == null ||
      linked.value === check.tableValue ||
      linked.cellText === check.tableValue);
  if (!aligned || check.status === "no_table_evidence") {
    return {
      status: "INSUFFICIENT_EVIDENCE",
      detail: "No single reported fact shares this chart label, period, unit, currency, and scope.",
      page: null,
      evidenceId: null,
    };
  }
  const page = linked.page;
  const evidenceId = linked.tableId ? `ev-${linked.tableId}` : null;
  const difference = check.absoluteDifference
    ? ` Absolute difference ${check.absoluteDifference}.`
    : "";
  const period = linked.period.label ?? check.period ?? "the same period";
  if (check.status === "consistent") {
    return {
      status: "MATCH",
      detail: `Chart ${check.estimate} is close to reported ${linked.cellText} for ${period}.${difference} The chart value remains an estimate.`,
      page,
      evidenceId,
    };
  }
  if (check.status === "conflict") {
    return {
      status: "POTENTIAL_DISCREPANCY",
      detail: `Chart ${check.estimate} differs from reported ${linked.cellText} for ${period}.${difference} This is not a verified discrepancy.`,
      page,
      evidenceId,
    };
  }
  return {
    status: "INSUFFICIENT_EVIDENCE",
    detail: "The chart reading could not be checked.",
    page: null,
    evidenceId: null,
  };
}

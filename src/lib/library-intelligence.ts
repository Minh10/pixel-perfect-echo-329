import type { FinAuditService } from "./api/service";
import type { ChartInterpretation, Evidence, FinDocument, FinancialFact } from "./api/types";
import { compareReports } from "./fact-comparison";

export function recentReports(documents: FinDocument[]) {
  return [...documents].sort((a, b) => {
    const time = (value: string) => Number.isNaN(Date.parse(value)) ? 0 : Date.parse(value);
    return time(b.uploadedAt) - time(a.uploadedAt);
  });
}

export interface LibraryIntelligence {
  reports: FinDocument[];
  evidence: Evidence[];
  facts: FinancialFact[];
  readings: ChartInterpretation[];
  unavailable: Set<"evidence" | "facts" | "readings">;
  sample: boolean;
}

/** Read-only, bounded preview; never triggers a model or changes processing. */
export async function loadLibraryIntelligence(
  service: FinAuditService,
  documents: FinDocument[],
  sample: boolean,
  sampleId: string | null,
): Promise<LibraryIntelligence> {
  const reports = recentReports(documents).filter((doc) => doc.status === "ready" && (!sample || doc.id === sampleId)).slice(0, 6);
  const result: LibraryIntelligence = { reports, evidence: [], facts: [], readings: [], unavailable: new Set(), sample };
  if (!service.getFacts) result.unavailable.add("facts");
  if (!service.getFigureInterpretation) result.unavailable.add("readings");
  for (const doc of reports) {
    try { result.evidence.push(...await service.getEvidence(doc.id)); }
    catch { result.unavailable.add("evidence"); }
    if (service.getFacts) {
      try { result.facts.push(...await service.getFacts(doc.id)); }
      catch { result.unavailable.add("facts"); }
    }
  }
  // Up to eight stored crops: no burst of requests and no automatic AI generation.
  const figures = result.evidence.filter((item) => item.category === "figure" && item.provenance).slice(0, 8);
  for (const figure of figures) {
    if (!service.getFigureInterpretation || !figure.provenance) continue;
    try { result.readings.push(await service.getFigureInterpretation(figure.provenance.documentId, figure.blockId)); }
    catch (error) {
      if (!(error instanceof Error && "status" in error && error.status === 404)) result.unavailable.add("readings");
    }
  }
  if (result.evidence.filter((item) => item.category === "figure").length > figures.length && !sample)
    result.unavailable.add("readings");
  return result;
}

/** Conservative preview only; the existing comparison engine remains unchanged. */
export function libraryTrend(data: LibraryIntelligence) {
  if (data.sample || data.unavailable.has("facts")) return null;
  const groups = new Map<string, FinancialFact[]>();
  for (const fact of data.facts) {
    if (!fact.issuer?.trim() || !fact.currency || fact.scale === "unknown" || fact.scope === "unknown" || fact.period.periodType === "unknown" || (!fact.period.label && !fact.period.fiscalYear) || fact.valueStatus !== "parsed" || fact.value == null) continue;
    const key = [fact.issuer.trim().toLowerCase(), fact.rowLabel.toLowerCase(), fact.rowGroup ?? "", fact.currency, fact.scale, fact.scope, fact.period.periodType, fact.isPercent].join("|");
    groups.set(key, [...(groups.get(key) ?? []), fact]);
  }
  for (const facts of groups.values()) {
    const ids = [...new Set(facts.map((fact) => fact.documentId))];
    if (ids.length < 2) continue;
    const first = facts[0];
    if (!first) continue;
    const result = compareReports(ids.map((id) => ({ documentId: id, title: data.reports.find((doc) => doc.id === id)?.title ?? id, facts: facts.filter((fact) => fact.documentId === id) })), first.rowLabel);
    if (result.points.length >= 2) return { ...result, issuer: first.issuer, metric: first.rowLabel };
  }
  return null;
}
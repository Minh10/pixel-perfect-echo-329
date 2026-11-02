import type { FinDocument } from "./api/types";

/** Ready reports to compare without asking the user to tick boxes first. */
export function defaultTrendSelection(documents: FinDocument[], preferredId?: string): string[] {
  const ready = documents
    .filter((doc) => doc.status === "ready")
    .slice()
    .sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt));
  const first = ready[0];
  if (!first) return [];

  const preferred = ready.find((doc) => doc.id === preferredId);
  const anchor = preferred ?? first;
  const sameIssuer = anchor.issuer ? ready.filter((doc) => doc.issuer === anchor.issuer) : [];
  const pool = sameIssuer.length >= 2 ? sameIssuer : ready;
  const ids = pool.map((doc) => doc.id);
  if (preferred && !ids.includes(preferred.id)) ids.unshift(preferred.id);

  const limit = sameIssuer.length >= 2 ? Math.min(ids.length, 6) : Math.min(ids.length, 2);
  const chosen = ids.slice(0, limit);
  if (preferred && !chosen.includes(preferred.id)) {
    return [preferred.id, ...chosen.filter((id) => id !== preferred.id)].slice(0, limit);
  }
  return chosen;
}

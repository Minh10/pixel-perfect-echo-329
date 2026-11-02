import type { Evidence } from "@/lib/api/types";

export type EvidenceRow =
  | { kind: "item"; evidence: Evidence; excerpt: string }
  | { kind: "group"; page: number; count: number; first: Evidence };

const UNCAPTIONED = /no caption detected/i;

/** Plain-language excerpt: hides empty "0×0 table" sizes from the parser. */
export function readableExcerpt(e: Evidence): string {
  if (e.category === "table" && /^\s*0\s*[x×]\s*0\s*table\s*$/i.test(e.excerpt))
    return "Table (structure not extracted)";
  return e.excerpt;
}

/**
 * Presentation-only ordering: current page first, then by page.
 * Uncaptioned figures on the same page collapse into one row.
 */
export function evidenceRows(evidence: Evidence[], currentPage: number): EvidenceRow[] {
  const sorted = [...evidence].sort((a, b) => {
    const ac = a.page === currentPage ? 0 : 1;
    const bc = b.page === currentPage ? 0 : 1;
    return ac - bc || a.page - b.page;
  });
  const rows: EvidenceRow[] = [];
  const groups = new Map<number, Extract<EvidenceRow, { kind: "group" }>>();
  for (const e of sorted) {
    if (e.category === "figure" && UNCAPTIONED.test(e.excerpt)) {
      const g = groups.get(e.page);
      if (g) {
        g.count += 1;
        continue;
      }
      const row = { kind: "group" as const, page: e.page, count: 1, first: e };
      groups.set(e.page, row);
      rows.push(row);
      continue;
    }
    rows.push({ kind: "item", evidence: e, excerpt: readableExcerpt(e) });
  }
  return rows;
}

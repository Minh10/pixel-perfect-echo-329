import { X } from "lucide-react";
import type { DocumentPage, Evidence, EvidenceCategory } from "@/lib/api/types";
import { IS_DEMO } from "@/lib/api/service";
import { Button } from "@/components/ui/button";
import { DemoBadge } from "@/components/app/states";
import { BlockContent } from "@/components/workspace/document-page";
import { cn } from "@/lib/utils";

const CATEGORY_LABEL: Record<EvidenceCategory, string> = {
  metric: "Metric",
  disclosure: "Disclosure",
  table: "Table",
  chart: "Chart",
  figure: "Figure",
};

const FILTERS = ["all", "metric", "table", "chart", "figure", "disclosure"] as const;

interface Props {
  evidence: Evidence[];
  pages: DocumentPage[];
  selected: Evidence | null;
  filter: EvidenceCategory | "all";
  onFilter: (f: EvidenceCategory | "all") => void;
  onSelect: (id: string | null) => void;
}

export function EvidenceInspector({
  evidence,
  pages,
  selected,
  filter,
  onFilter,
  onSelect,
}: Props) {
  const filtered = filter === "all" ? evidence : evidence.filter((e) => e.category === filter);
  const related = selected ? evidence.filter((e) => selected.related.includes(e.id)) : [];
  const selectedBlock = selected
    ? pages.flatMap((page) => page.blocks).find((block) => block.id === selected.blockId)
    : undefined;
  const filters = FILTERS.filter(
    (item) => item !== "figure" || evidence.some((entry) => entry.category === "figure"),
  );

  return (
    <div className="flex min-h-0 h-full flex-col">
      {selected ? (
        <section
          className="border-b border-l-2 border-l-evidence bg-evidence-soft/40 p-4"
          aria-label="Selected evidence"
        >
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <p className="eyebrow">
                {CATEGORY_LABEL[selected.category]} · p. {selected.page}
              </p>
              <h3 className="mt-1 text-sm font-semibold leading-snug">{selected.label}</h3>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => onSelect(null)}
              aria-label="Clear selection"
            >
              <X className="size-4" />
            </Button>
          </div>
          <blockquote className="border-l-2 border-evidence pl-3 text-sm text-foreground/80">
            {selected.excerpt}
          </blockquote>
          {selectedBlock && (selectedBlock.table || selectedBlock.figure) ? (
            <div className="mt-4">
              <BlockContent block={selectedBlock} />
            </div>
          ) : null}
          {selected.extracted && (
            <dl className="mt-4 divide-y rounded-sm border">
              {selected.extracted.map((f) => (
                <div
                  key={f.field}
                  className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-3 px-3 py-2 text-xs"
                >
                  <dt className="text-muted-foreground">{f.field}</dt>
                  <dd className="font-mono tabular font-medium">
                    {f.value}
                    {f.unit && <span className="ml-1 text-muted-foreground">{f.unit}</span>}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <div className="mt-4 flex items-center justify-between gap-3">
            {selected.confidence == null ? (
              <p className="text-[11px] text-muted-foreground">
                Confidence: not reported by parser
              </p>
            ) : (
              <ConfidenceBar value={selected.confidence} />
            )}
            {IS_DEMO && <DemoBadge />}
          </div>
          {IS_DEMO && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Extraction is illustrative. No figure has been verified against source filings.
            </p>
          )}
          {!IS_DEMO && selected.provenance && (
            <dl className="mt-3 space-y-1 font-mono text-[11px] text-muted-foreground">
              <div>
                {selected.provenance.parser} · {selected.provenance.method}
              </div>
              <div>
                p. {selected.provenance.page} · bbox {selected.provenance.bbox.l.toFixed(1)},{" "}
                {selected.provenance.bbox.t.toFixed(1)}, {selected.provenance.bbox.r.toFixed(1)},{" "}
                {selected.provenance.bbox.b.toFixed(1)} pt
              </div>
              {selected.category === "disclosure" && selected.detection?.rule && (
                <div className="font-sans">{selected.detection.rule}</div>
              )}
            </dl>
          )}
          {related.length > 0 && (
            <div className="mt-4">
              <p className="eyebrow mb-2">Linked evidence</p>
              <div className="flex flex-wrap gap-1.5">
                {related.map((r) => (
                  <Button
                    variant="ghost"
                    key={r.id}
                    type="button"
                    onClick={() => onSelect(r.id)}
                    className="h-auto whitespace-normal rounded-sm border px-2 py-1 text-[11px] hover:border-evidence hover:text-evidence"
                  >
                    p.{r.page} · {r.label}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </section>
      ) : (
        <section className="border-b p-4">
          <h2 className="text-base font-semibold">Evidence Inspector</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {IS_DEMO
              ? "Report evidence · illustrative extraction only."
              : "Parser regions traced back to the source PDF. Values are not verified facts."}
          </p>
        </section>
      )}

      <div className="flex flex-wrap items-center gap-1 border-b px-3 py-2">
        {filters.map((f) => (
          <Button
            variant="ghost"
            key={f}
            type="button"
            onClick={() => onFilter(f)}
            aria-pressed={filter === f}
            className={cn(
              "h-7 rounded-sm px-2 py-1 text-[11px] font-medium text-muted-foreground hover:text-foreground",
              filter === f && "bg-primary text-primary-foreground hover:text-primary-foreground",
            )}
          >
            {f === "all" ? "All" : CATEGORY_LABEL[f]}
          </Button>
        ))}
      </div>

      <ul className="flex-1 overflow-y-auto">
        {filtered.length === 0 && (
          <li className="p-4 text-sm text-muted-foreground">No evidence in this category.</li>
        )}
        {filtered.map((e) => (
          <li key={e.id}>
            <Button
              variant="ghost"
              type="button"
              onClick={() => onSelect(e.id)}
              className={cn(
                "flex h-auto w-full justify-start whitespace-normal rounded-none gap-3 border-b px-4 py-3 text-left transition-colors hover:bg-muted",
                selected?.id === e.id && "bg-evidence-soft/60",
              )}
            >
              <span className="w-8 shrink-0 font-mono text-[11px] text-muted-foreground">
                p.{e.page}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-medium">{e.label}</span>
                <span className="block truncate text-[11px] text-muted-foreground">
                  {e.excerpt}
                </span>
              </span>
              <span className="shrink-0 font-mono text-[10px] uppercase text-muted-foreground">
                {CATEGORY_LABEL[e.category]}
              </span>
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
      <span>Extraction confidence</span>
      <span className="h-1 w-16 overflow-hidden rounded-full bg-muted">
        <span className="block h-full bg-evidence" style={{ width: `${value * 100}%` }} />
      </span>
      <span className="font-mono tabular">{Math.round(value * 100)}%</span>
    </div>
  );
}

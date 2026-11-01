import type { DocumentPage, Evidence, PageBlock } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  page: DocumentPage;
  totalPages: number;
  evidence: Evidence[];
  selectedId: string | null;
  showHighlights: boolean;
  zoom: number;
  onSelect: (id: string) => void;
  documentTitle: string;
}

/** Renders a page as a paper sheet. Replace with a real PDF renderer (e.g. pdf.js) + bbox overlay later. */
export function DocumentPageView({
  page,
  totalPages,
  evidence,
  selectedId,
  showHighlights,
  zoom,
  onSelect,
  documentTitle,
}: Props) {
  const byBlock = new Map(
    evidence.filter((e) => e.page === page.number).map((e) => [e.blockId, e]),
  );

  return (
    <article
      className="mx-auto aspect-[1/1.3] w-full origin-top bg-paper p-[7%] text-[0.8125rem] leading-relaxed shadow-page transition-transform"
      style={{ maxWidth: 720 * zoom }}
      aria-label={`Page ${page.number}`}
    >
      <div className="mb-8 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b pb-2 font-mono text-[10px] text-muted-foreground">
        <span className="truncate">{documentTitle}</span>
        <span>{page.section}</span>
      </div>
      <div className="space-y-4">
        {page.blocks.map((block) => {
          const ev = byBlock.get(block.id);
          const content = <BlockContent block={block} />;
          if (!ev) return <div key={block.id}>{content}</div>;
          const selected = selectedId === ev.id;
          return (
            <Button
              variant="ghost"
              key={block.id}
              type="button"
              onClick={() => onSelect(ev.id)}
              aria-pressed={selected}
              aria-label={`Evidence: ${ev.label}`}
              className={cn(
                "group relative h-auto whitespace-normal -mx-2 block w-[calc(100%+1rem)] rounded-sm px-2 py-1 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                showHighlights && "bg-evidence-soft/60 hover:bg-evidence-soft",
                !showHighlights && "hover:bg-muted",
                selected && "bg-evidence-soft ring-2 ring-evidence hover:bg-evidence-soft",
              )}
            >
              {showHighlights && (
                <span
                  className={cn(
                    "absolute -left-3 top-1 bottom-1 w-0.5 rounded-full bg-evidence/50",
                    selected && "bg-evidence",
                  )}
                />
              )}
              {content}
            </Button>
          );
        })}
      </div>
      <div className="mt-10 text-center font-mono text-[10px] text-muted-foreground">
        {page.number} / {totalPages}
      </div>
    </article>
  );
}

function BlockContent({ block }: { block: PageBlock }) {
  if (block.kind === "heading")
    return <h2 className="text-xl font-semibold leading-snug text-foreground">{block.text}</h2>;
  if (block.kind === "paragraph") return <p className="text-foreground/85">{block.text}</p>;
  if (block.kind === "table" && block.table) {
    return (
      <table className="w-full border-collapse tabular text-[0.75rem]">
        <thead>
          <tr className="border-b-2 border-primary">
            {block.table.columns.map((c, i) => (
              <th
                scope="col"
                key={i}
                className={cn("py-1.5 font-semibold", i === 0 ? "text-left" : "text-right")}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.table.rows.map((r) => (
            <tr
              key={r.label}
              className={cn("border-b border-border/70", r.emphasis && "font-semibold")}
            >
              <td className="py-1.5">{r.label}</td>
              {r.values.map((v, i) => (
                <td key={i} className="py-1.5 text-right font-mono">
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (block.kind === "chart" && block.chart) {
    const max = Math.max(...block.chart.series.map((s) => s.value));
    return (
      <figure>
        <figcaption className="mb-3 text-xs font-semibold">{block.chart.title}</figcaption>
        <div className="space-y-2">
          {block.chart.series.map((s) => (
            <div
              key={s.label}
              className="grid grid-cols-[72px_1fr_48px] items-center gap-2 text-[0.75rem]"
            >
              <span className="text-muted-foreground">{s.label}</span>
              <span
                className="h-4 rounded-[2px] bg-primary/85"
                style={{ width: `${(s.value / max) * 100}%` }}
              />
              <span className="text-right font-mono tabular">{s.value.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </figure>
    );
  }
  return null;
}

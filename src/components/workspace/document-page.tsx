import type { DocumentPage, Evidence, PageBlock } from "@/lib/api/types";
import { API_URL, apiAsset } from "@/lib/api/http-service";
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
  const live =
    Boolean(API_URL) &&
    Boolean(page.imageUrl) &&
    typeof page.width === "number" &&
    typeof page.height === "number" &&
    page.width > 0 &&
    page.height > 0;

  if (live && page.imageUrl && page.width && page.height) {
    const extracted = page.blocks.filter(
      (block) => (block.kind === "table" && block.table) || (block.kind === "figure" && block.figure),
    );
    return (
      <div className="mx-auto w-full space-y-6" style={{ maxWidth: 720 * zoom }}>
        <article
          className="relative w-full origin-top bg-paper shadow-page"
          style={{ aspectRatio: `${page.width} / ${page.height}` }}
          aria-label={`Page ${page.number}`}
        >
          <img
            src={apiAsset(`${page.imageUrl}?dpi=110`)}
            alt={`Page ${page.number} of ${documentTitle}`}
            className="absolute inset-0 h-full w-full"
          />
          {page.blocks.map((block) => {
            const ev = byBlock.get(block.id);
            const box = block.bboxNormalized;
            if (!ev || !box) return null;
            const selected = selectedId === ev.id;
            return (
              <button
                key={block.id}
                type="button"
                onClick={() => onSelect(ev.id)}
                aria-pressed={selected}
                aria-label={`Evidence: ${ev.label}`}
                title={ev.label}
                className={cn(
                  "absolute rounded-[2px] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                  showHighlights && "border border-evidence/80 bg-evidence-soft/35 hover:bg-evidence-soft/70",
                  !showHighlights && "hover:bg-evidence-soft/40",
                  selected && "z-10 border-evidence bg-evidence-soft/60 ring-2 ring-evidence",
                )}
                style={{
                  left: `${box.x * 100}%`,
                  top: `${box.y * 100}%`,
                  width: `${box.width * 100}%`,
                  height: `${box.height * 100}%`,
                }}
              />
            );
          })}
        </article>
        <p className="text-center font-mono text-[10px] text-muted-foreground">
          {page.number} / {totalPages}
          {page.section ? ` · ${page.section}` : ""}
          {page.hasTextLayer === false ? " · no text layer" : ""}
        </p>
        {extracted.length > 0 && (
          <section className="space-y-4 rounded-md border bg-card p-4" aria-label="Extracted regions">
            <h2 className="text-sm font-semibold">Extracted on this page</h2>
            {extracted.map((block) => {
              const ev = byBlock.get(block.id);
              return (
                <div key={block.id} className="border-t pt-4 first:border-t-0 first:pt-0">
                  {ev ? (
                    <Button
                      variant="ghost"
                      type="button"
                      onClick={() => onSelect(ev.id)}
                      aria-pressed={selectedId === ev.id}
                      className="mb-2 h-auto px-0 text-xs font-medium text-evidence hover:bg-transparent hover:text-evidence"
                    >
                      {ev.label}
                    </Button>
                  ) : null}
                  <BlockContent block={block} />
                </div>
              );
            })}
          </section>
        )}
      </div>
    );
  }

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

export function BlockContent({ block }: { block: PageBlock }) {
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
          {block.table.rows.map((r, rowIndex) => (
            <tr
              key={`${rowIndex}-${r.label}`}
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
  if (block.kind === "figure" && block.figure) {
    return (
      <figure>
        <img
          src={apiAsset(block.figure.imageUrl)}
          alt={block.figure.caption ?? "Figure"}
          className="max-w-full"
        />
        {block.figure.caption && (
          <figcaption className="mt-2 text-xs text-muted-foreground">{block.figure.caption}</figcaption>
        )}
      </figure>
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

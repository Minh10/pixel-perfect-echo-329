import { useEffect, useRef, useState } from "react";
import { pdfDisplayWidth, type PdfFit } from "@/lib/pdf-view";
import type { DocumentPage, Evidence, NormalizedBBox, PageBlock } from "@/lib/api/types";
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
  fit?: PdfFit;
  onSelect: (id: string) => void;
  documentTitle: string;
  focus?: NormalizedBBox[];
}

/** Renders a page as a paper sheet. Replace with a real PDF renderer (e.g. pdf.js) + bbox overlay later. */
export function DocumentPageView({
  page,
  totalPages,
  evidence,
  selectedId,
  showHighlights,
  zoom,
  fit = "width",
  onSelect,
  documentTitle,
  focus,
}: Props) {
  const root = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 800, height: 800 });
  const [failedImage, setFailedImage] = useState<string | null>(null);
  useEffect(() => {
    const parent = root.current?.parentElement;
    if (!parent) return;
    const observer = new ResizeObserver(() =>
      setSize({ width: parent.clientWidth, height: parent.clientHeight }),
    );
    observer.observe(parent);
    setSize({ width: parent.clientWidth, height: parent.clientHeight });
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const frame = requestAnimationFrame(() =>
      root.current
        ?.querySelector('[aria-pressed="true"]')
        ?.scrollIntoView({ block: "nearest", inline: "nearest" }),
    );
    return () => cancelAnimationFrame(frame);
  }, [selectedId, page.number]);
  const aspect = page.width && page.height ? page.width / page.height : 210 / 297;
  const displayWidth = pdfDisplayWidth(fit, size.width, size.height, aspect, zoom);
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
    return (
      <div ref={root} className="pdf-sheet mx-auto" style={{ width: displayWidth }}>
        <article
          className="relative w-full origin-top bg-paper shadow-page"
          style={{ aspectRatio: `${page.width} / ${page.height}` }}
          aria-label={`Page ${page.number}`}
        >
          <span className="absolute inset-0 animate-pulse bg-muted" aria-hidden />
          {failedImage === page.imageUrl ? (
            <div className="absolute inset-0 flex items-center justify-center p-8 text-sm text-muted-foreground">
              Page image unavailable. Try reopening this report.
            </div>
          ) : (
            <img
              key={page.imageUrl}
              src={apiAsset(`${page.imageUrl}?dpi=110`)}
              alt={`Page ${page.number} of ${documentTitle}`}
              decoding="async"
              onError={() => setFailedImage(page.imageUrl ?? null)}
              className="absolute inset-0 h-full w-full"
            />
          )}
          {page.blocks.map((block) => {
            const ev = byBlock.get(block.id);
            const box = block.bboxNormalized;
            if (!ev || !box) return null;
            const selected = selectedId === ev.id;
            return (
              <Button
                key={block.id}
                variant="ghost"
                type="button"
                onClick={() => onSelect(ev.id)}
                aria-pressed={selected}
                aria-label={`Evidence: ${ev.label}`}
                title={ev.label}
                className={cn(
                  "absolute h-auto min-h-0 p-0 rounded-[2px] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                  showHighlights &&
                    "border border-evidence/80 bg-evidence-soft/35 hover:bg-evidence-soft/70",
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
          {focus?.map((box, index) => (
            <div
              key={`cite-${index}`}
              className="pointer-events-none absolute z-20 rounded-[2px] ring-2 ring-primary"
              style={{
                left: `${box.x * 100}%`,
                top: `${box.y * 100}%`,
                width: `${box.width * 100}%`,
                height: `${box.height * 100}%`,
              }}
              aria-hidden
            />
          ))}
        </article>
        <p className="text-center font-mono text-[10px] text-muted-foreground">
          {page.number} / {totalPages}
          {page.section ? ` · ${page.section}` : ""}
          {page.hasTextLayer === false ? " · no text layer" : ""}
        </p>
      </div>
    );
  }

  return (
    <div ref={root} className="pdf-sheet mx-auto" style={{ width: displayWidth }}>
      <article
        className="min-h-full aspect-[210/297] w-full origin-top bg-paper p-[7%] text-[0.9375rem] leading-relaxed shadow-page"
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
    </div>
  );
}

export function BlockContent({ block }: { block: PageBlock }) {
  if (block.kind === "heading")
    return <h2 className="text-xl font-semibold leading-snug text-foreground">{block.text}</h2>;
  if (block.kind === "paragraph") return <p className="text-foreground/85">{block.text}</p>;
  if (block.kind === "table" && block.table) {
    return (
      <div className="overflow-x-auto">
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
      </div>
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
          <figcaption className="mt-2 text-xs text-muted-foreground">
            {block.figure.caption}
          </figcaption>
        )}
      </figure>
    );
  }
  if (block.kind === "chart" && block.chart) {
    const max = Math.max(1, ...block.chart.series.map((s) => Math.abs(s.value)));
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

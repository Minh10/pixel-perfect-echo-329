import { useState } from "react";
import type { DocumentPage, Evidence } from "@/lib/api/types";
import { API_URL, apiAsset } from "@/lib/api/http-service";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PageNavigator({
  pages,
  current,
  evidence,
  onSelect,
}: {
  pages: DocumentPage[];
  current: number;
  evidence: Evidence[];
  onSelect: (n: number) => void;
}) {
  // A failed thumbnail falls back to the drawn placeholder instead of a broken icon.
  const [failed, setFailed] = useState<Set<number>>(() => new Set());
  return (
    <nav aria-label="Pages" className="space-y-1 p-3">
      <p className="eyebrow px-1 pb-2">Pages · {pages.length}</p>
      {pages.map((p) => {
        const count = evidence.filter((e) => e.page === p.number).length;
        const active = p.number === current;
        return (
          <Button
            variant="ghost"
            key={p.number}
            type="button"
            onClick={() => onSelect(p.number)}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-auto w-full items-center gap-3 rounded-sm p-1.5 text-left transition-colors hover:bg-muted",
              active && "bg-primary-soft text-primary-deep",
            )}
          >
            <span
              className={cn(
                "relative aspect-[3/4] w-10 shrink-0 overflow-hidden border bg-paper",
                !p.imageUrl && "p-1",
                active && "border-primary ring-1 ring-primary",
              )}
            >
              {p.imageUrl && API_URL && !failed.has(p.number) ? (
                <img
                  src={apiAsset(`${p.imageUrl}?dpi=40`)}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  onError={() => setFailed((s) => new Set(s).add(p.number))}
                  className="h-full w-full object-cover object-top"
                />
              ) : (
                <>
                  <span className="block h-1 w-3/4 bg-primary/60" />
                  <span className="mt-1 block h-0.5 w-full bg-muted-foreground/25" />
                  <span className="mt-0.5 block h-0.5 w-5/6 bg-muted-foreground/25" />
                  <span className="mt-0.5 block h-0.5 w-full bg-muted-foreground/25" />
                  {count > 0 && <span className="mt-1 block h-1.5 w-full bg-evidence/40" />}
                </>
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-mono text-[11px] text-muted-foreground">
                p. {p.number}
              </span>
              <span className="block truncate text-xs font-medium">{p.section}</span>
            </span>
            {count > 0 && (
              <span className="rounded-sm bg-evidence-soft px-1.5 font-mono text-[10px] text-evidence">
                {count}
              </span>
            )}
          </Button>
        );
      })}
    </nav>
  );
}

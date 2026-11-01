import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Highlighter, Minus, Plus } from "lucide-react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { DEFAULT_DOCUMENT_ID, documentQuery, evidenceQuery, pagesQuery } from "@/lib/api/service";
import type { EvidenceCategory } from "@/lib/api/types";
import { DocumentPageView } from "@/components/workspace/document-page";
import { PageNavigator } from "@/components/workspace/page-navigator";
import { EvidenceInspector } from "@/components/workspace/evidence-inspector";
import { EmptyState, ErrorState, WorkspaceSkeleton } from "@/components/app/states";

const search = z.object({ doc: z.string().optional(), page: z.number().int().min(1).optional() });

export const Route = createFileRoute("/intelligence")({
  validateSearch: search,
  loaderDeps: ({ search }) => ({ doc: search.doc ?? DEFAULT_DOCUMENT_ID }),
  loader: async ({ context, deps }) => {
    await Promise.all([
      context.queryClient.ensureQueryData(documentQuery(deps.doc)),
      context.queryClient.ensureQueryData(pagesQuery(deps.doc)),
      context.queryClient.ensureQueryData(evidenceQuery(deps.doc)),
    ]);
  },
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Document Intelligence — FINAUDIT AI" },
      { name: "description", content: "Inspect financial report pages, tables and charts with linked evidence." },
      { property: "og:title", content: "Document Intelligence — FINAUDIT AI" },
      { property: "og:description", content: "Inspect financial report pages, tables and charts with linked evidence." },
    ],
  }),
  pendingComponent: WorkspaceSkeleton,
  errorComponent: ({ error }) => {
    const router = useRouter();
    return (
      <div className="p-8">
        <ErrorState message={error instanceof Error ? error.message : String(error)} onRetry={() => router.invalidate()} />
      </div>
    );
  },
  component: Workspace,
});

function Workspace() {
  const { doc: docParam, page: pageParam } = Route.useSearch();
  const docId = docParam ?? DEFAULT_DOCUMENT_ID;
  const navigate = Route.useNavigate();
  const { data: doc } = useSuspenseQuery(documentQuery(docId));
  const { data: pages } = useSuspenseQuery(pagesQuery(docId));
  const { data: evidence } = useSuspenseQuery(evidenceQuery(docId));

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<EvidenceCategory | "all">("all");
  const [showHighlights, setShowHighlights] = useState(true);
  const [zoom, setZoom] = useState(1);

  const current = Math.min(pageParam ?? 1, Math.max(pages.length, 1));
  const page = pages.find((p) => p.number === current);
  const selected = useMemo(() => evidence.find((e) => e.id === selectedId) ?? null, [evidence, selectedId]);

  const goTo = (n: number) => navigate({ search: (s) => ({ ...s, page: n }), replace: true });
  const select = (id: string | null) => {
    setSelectedId(id);
    const ev = evidence.find((e) => e.id === id);
    if (ev && ev.page !== current) goTo(ev.page);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input,textarea")) return;
      if (e.key === "ArrowRight" && current < pages.length) goTo(current + 1);
      if (e.key === "ArrowLeft" && current > 1) goTo(current - 1);
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (doc.status !== "ready" || pages.length === 0) {
    return (
      <div className="p-8">
        <EmptyState
          title={doc.status === "processing" ? "Document is still processing" : doc.status === "failed" ? "Processing failed" : "No pages available"}
          description={`${doc.title} has no parsed pages to display yet.`}
          action={<Button asChild variant="outline" size="sm"><Link to="/intelligence" search={{}}>Open demo report</Link></Button>}
        />
      </div>
    );
  }

  return (
    <div className="grid h-[calc(100svh-3.5rem)] grid-cols-1 grid-rows-[auto_1fr] lg:grid-cols-[220px_minmax(0,1fr)_340px]">
      {/* Toolbar */}
      <div className="col-span-full flex flex-wrap items-center gap-x-4 gap-y-2 border-b bg-card px-4 py-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{doc.title}</p>
          <p className="font-mono text-[11px] text-muted-foreground">{doc.type} · {doc.period} · {doc.pages} pp · {evidence.length} evidence regions</p>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="ghost" size="icon" className="size-8" disabled={current <= 1} onClick={() => goTo(current - 1)} aria-label="Previous page"><ChevronLeft className="size-4" /></Button>
          <span className="w-16 text-center font-mono text-xs tabular">{current} / {pages.length}</span>
          <Button variant="ghost" size="icon" className="size-8" disabled={current >= pages.length} onClick={() => goTo(current + 1)} aria-label="Next page"><ChevronRight className="size-4" /></Button>
        </div>
        <div className="flex items-center gap-1 border-l pl-3">
          <Button variant="ghost" size="icon" className="size-8" onClick={() => setZoom((z) => Math.max(0.7, +(z - 0.1).toFixed(1)))} aria-label="Zoom out"><Minus className="size-4" /></Button>
          <span className="w-10 text-center font-mono text-xs tabular">{Math.round(zoom * 100)}%</span>
          <Button variant="ghost" size="icon" className="size-8" onClick={() => setZoom((z) => Math.min(1.5, +(z + 0.1).toFixed(1)))} aria-label="Zoom in"><Plus className="size-4" /></Button>
        </div>
        <div className="flex items-center gap-2 border-l pl-3">
          <Highlighter className="size-4 text-evidence" />
          <Label htmlFor="hl" className="text-xs">Highlights</Label>
          <Switch id="hl" checked={showHighlights} onCheckedChange={setShowHighlights} />
        </div>
      </div>

      <aside className="hidden overflow-y-auto border-r bg-card lg:block">
        <PageNavigator pages={pages} current={current} evidence={evidence} onSelect={goTo} />
      </aside>

      <main className="overflow-auto bg-canvas px-4 py-8 md:px-10">
        {page && (
          <DocumentPageView
            page={page}
            totalPages={pages.length}
            evidence={evidence}
            selectedId={selectedId}
            showHighlights={showHighlights}
            zoom={zoom}
            onSelect={select}
            documentTitle={doc.title}
          />
        )}
      </main>

      <aside className="border-t bg-card lg:overflow-hidden lg:border-l lg:border-t-0">
        <EvidenceInspector evidence={evidence} selected={selected} filter={filter} onFilter={setFilter} onSelect={select} />
      </aside>
    </div>
  );
}

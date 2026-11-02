import { useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Highlighter,
  Minus,
  Plus,
  PanelLeft,
  PanelRight,
} from "lucide-react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { PdfIntake } from "@/components/app/pdf-intake";
import { DemoBadge } from "@/components/app/states";
import { Label } from "@/components/ui/label";
import { ApiError, apiAsset, sourceDocumentUrl } from "@/lib/api/http-service";
import {
  DEFAULT_DOCUMENT_ID,
  IS_DEMO,
  api,
  documentQuery,
  documentsQuery,
  evidenceQuery,
  jobQuery,
  pagesQuery,
} from "@/lib/api/service";
import type { ChunkRef, EvidenceCategory, FinDocument } from "@/lib/api/types";
import { DocumentPageView } from "@/components/workspace/document-page";
import { PageNavigator } from "@/components/workspace/page-navigator";
import { EvidenceInspector } from "@/components/workspace/evidence-inspector";
import { ErrorState, WorkspaceSkeleton } from "@/components/app/states";

const search = z.object({
  doc: z.string().optional(),
  page: z.number().int().min(1).optional(),
  ev: z.string().optional(),
  chunk: z.string().optional(),
});

export const Route = createFileRoute("/intelligence")({
  validateSearch: search,
  loaderDeps: ({ search }) => ({ doc: search.doc }),
  loader: async ({ context, deps }) => {
    const docs = await context.queryClient.ensureQueryData(documentsQuery());
    const docId =
      deps.doc ?? DEFAULT_DOCUMENT_ID ?? docs.find((doc) => doc.status === "ready")?.id ?? null;
    if (!docId) return { docId: null as string | null };
    await Promise.all([
      context.queryClient.ensureQueryData(documentQuery(docId)),
      context.queryClient.ensureQueryData(pagesQuery(docId)),
      context.queryClient.ensureQueryData(evidenceQuery(docId)),
    ]);
    return { docId };
  },
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Document Intelligence — FINAUDIT AI" },
      {
        name: "description",
        content: "Inspect financial report pages, tables and charts with linked evidence.",
      },
      { property: "og:title", content: "Document Intelligence — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Inspect financial report pages, tables and charts with linked evidence.",
      },
    ],
  }),
  pendingComponent: WorkspaceSkeleton,
  errorComponent: function WorkspaceError({ error }) {
    const router = useRouter();
    const unavailable =
      error instanceof ApiError &&
      (error.code === "backend_unavailable" || error.code === "timeout");
    return (
      <div className="p-8">
        <ErrorState
          title={unavailable ? "Document service unavailable" : "Couldn't load this document"}
          message={error instanceof Error ? error.message : String(error)}
          onRetry={() => router.invalidate()}
        />
      </div>
    );
  },
  component: Workspace,
});

function Workspace() {
  const { docId } = Route.useLoaderData();
  if (!docId) {
    return (
      <div className="page-layout">
        <PdfIntake />
      </div>
    );
  }
  return <WorkspaceReady docId={docId} />;
}

function WorkspaceReady({ docId }: { docId: string }) {
  const { page: pageParam, ev: evParam, chunk: chunkParam } = Route.useSearch();
  const queryClient = useQueryClient();
  const navigate = Route.useNavigate();
  const { data: doc } = useSuspenseQuery(documentQuery(docId));
  const pagesResult = useSuspenseQuery(pagesQuery(docId));
  const pages = pagesResult.data;
  const { data: evidence } = useSuspenseQuery(evidenceQuery(docId));

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<EvidenceCategory | "all">("all");
  const [showHighlights, setShowHighlights] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [showPages, setShowPages] = useState(true);
  const [showInspector, setShowInspector] = useState(true);

  const previousStatus = useRef(doc.status);
  const retriedEmptyPages = useRef(false);
  useEffect(() => {
    const becameReady = previousStatus.current === "processing" && doc.status !== "processing";
    const readyWithoutPages =
      doc.status === "ready" && pages.length === 0 && !retriedEmptyPages.current;
    if (becameReady || readyWithoutPages) {
      retriedEmptyPages.current = true;
      void queryClient.invalidateQueries({ queryKey: ["pages", docId] });
      void queryClient.invalidateQueries({ queryKey: ["evidence", docId] });
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    }
    previousStatus.current = doc.status;
  }, [doc.status, docId, pages.length, queryClient]);

  const citationQuery = useQuery({
    queryKey: ["citation", chunkParam],
    queryFn: () => api.getCitation!(chunkParam!),
    enabled: Boolean(chunkParam && api.getCitation),
  });
  const citation = citationQuery.data ?? null;

  useEffect(() => {
    if (!evParam) return;
    const ev = evidence.find((item) => item.id === evParam);
    if (!ev) return;
    setSelectedId(ev.id);
    if (ev.page !== (pageParam ?? 1)) {
      void navigate({ search: (s) => ({ ...s, page: ev.page }), replace: true });
    }
  }, [evParam, evidence, pageParam, navigate]);

  const current = Math.min(pageParam ?? 1, Math.max(pages.length, 1));
  const page = pages.find((p) => p.number === current);
  const focus =
    citation?.regions
      .filter((region) => region.page === current)
      .map((region) => region.bboxNormalized) ?? [];
  const selected = useMemo(
    () => evidence.find((e) => e.id === selectedId) ?? null,
    [evidence, selectedId],
  );

  const goTo = (n: number) => navigate({ search: (s) => ({ ...s, page: n }), replace: true });
  const select = (id: string | null) => {
    setSelectedId(id);
    const ev = evidence.find((e) => e.id === id);
    if (ev && ev.page !== current) goTo(ev.page);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        (e.target as HTMLElement)?.closest(
          "input,textarea,select,[contenteditable=true],[role=separator]",
        )
      )
        return;
      if (e.key === "ArrowRight" && current < pages.length) goTo(current + 1);
      if (e.key === "ArrowLeft" && current > 1) goTo(current - 1);
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (doc.status === "ready" && pages.length === 0 && pagesResult.isFetching) {
    return <WorkspaceSkeleton />;
  }

  if (doc.status !== "ready" || pages.length === 0) {
    return <AwaitingPages doc={doc} />;
  }

  return (
    <div className="flex min-w-0 flex-col lg:h-[calc(100svh-3.5rem)]">
      {/* Toolbar */}
      <div className="grid shrink-0 grid-cols-1 items-center gap-3 border-b bg-card px-4 py-3 xl:grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-3">
            <p className="truncate text-sm font-semibold">{doc.title}</p>
            {IS_DEMO && <DemoBadge className="shrink-0" />}
          </div>
          <p className="text-xs text-muted-foreground">
            {[
              doc.issuer,
              doc.type,
              doc.period,
              `${doc.pages} pp`,
              `${evidence.length} evidence regions`,
            ]
              .filter(Boolean)
              .join(" · ")}
            {!IS_DEMO && doc.parser ? ` · ${doc.parser.name}` : ""}
          </p>
          <p className="mt-1 flex flex-wrap gap-x-3 text-xs">
            {IS_DEMO ? (
              <Link to="/trends" search={{ doc: undefined }} className="text-primary">
                View the sample trend
              </Link>
            ) : (
              <>
                <Link to="/audit" search={{ doc: doc.id }} className="text-primary">
                  Check charts
                </Link>
                <Link to="/trends" search={{ doc: doc.id }} className="text-primary">
                  Compare trends
                </Link>
                <Link to="/analysis" search={{ doc: doc.id }} className="text-primary">
                  Ask about this report
                </Link>
              </>
            )}
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <div className="flex shrink-0 items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              disabled={current <= 1}
              onClick={() => goTo(current - 1)}
              title="Previous page"
              aria-label="Previous page"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="w-16 text-center font-mono text-xs tabular">
              {current} / {pages.length}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              disabled={current >= pages.length}
              onClick={() => goTo(current + 1)}
              title="Next page"
              aria-label="Next page"
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
          <div className="flex items-center gap-1 border-l pl-3">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={() => setZoom((z) => Math.max(0.7, +(z - 0.1).toFixed(1)))}
              title="Zoom out"
              aria-label="Zoom out"
            >
              <Minus className="size-4" />
            </Button>
            <span className="w-10 text-center font-mono text-xs tabular">
              {Math.round(zoom * 100)}%
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={() => setZoom((z) => Math.min(1.5, +(z + 0.1).toFixed(1)))}
              title="Zoom in"
              aria-label="Zoom in"
            >
              <Plus className="size-4" />
            </Button>
          </div>
          <div className="flex items-center gap-2 border-l pl-3">
            <Highlighter className="size-4 text-evidence" />
            <Label htmlFor="hl" className="text-xs">
              Highlights
            </Label>
            <Switch id="hl" checked={showHighlights} onCheckedChange={setShowHighlights} />
          </div>
          {!IS_DEMO && (
            <Button asChild variant="outline" size="sm">
              <a href={sourceDocumentUrl(doc.id)} target="_blank" rel="noreferrer">
                <Download /> Source PDF
              </a>
            </Button>
          )}
          <div className="flex shrink-0 items-center gap-1 border-l pl-3">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              title="Toggle page navigator"
              aria-label="Toggle page navigator"
              aria-pressed={showPages}
              onClick={() => setShowPages((v) => !v)}
            >
              <PanelLeft />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              title="Toggle evidence inspector"
              aria-label="Toggle evidence inspector"
              aria-pressed={showInspector}
              onClick={() => setShowInspector((v) => !v)}
            >
              <PanelRight />
            </Button>
          </div>
        </div>
      </div>
      {!IS_DEMO && doc.warnings && doc.warnings.length > 0 && (
        <p className="border-b bg-warning-soft px-4 py-2 text-xs text-warning">
          {doc.warnings.join(" ")}
        </p>
      )}

      <div className="hidden min-h-0 flex-1 lg:block">
        <ResizablePanelGroup orientation="horizontal" id="document-workspace">
          {showPages && (
            <>
              <ResizablePanel id="pages" defaultSize="17%" minSize="140px" maxSize="25%">
                <aside className="h-full overflow-y-auto bg-card">
                  <PageNavigator
                    pages={pages}
                    current={current}
                    evidence={evidence}
                    onSelect={goTo}
                  />
                </aside>
              </ResizablePanel>
              <ResizableHandle withHandle aria-label="Resize page navigator" />
            </>
          )}
          <ResizablePanel id="document" minSize="35%">
            <main className="h-full overflow-auto bg-canvas px-6 py-8">
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
                  focus={focus}
                />
              )}
            </main>
          </ResizablePanel>
          {showInspector && (
            <>
              <ResizableHandle withHandle aria-label="Resize evidence inspector" />
              <ResizablePanel id="inspector" defaultSize="29%" minSize="280px" maxSize="40%">
                <aside className="h-full overflow-y-auto bg-card">
                  <CitedExcerpt
                    citation={citation}
                    error={citationQuery.error}
                    pending={citationQuery.isFetching}
                  />
                  <EvidenceInspector
                    evidence={evidence}
                    pages={pages}
                    selected={selected}
                    filter={filter}
                    onFilter={setFilter}
                    onSelect={select}
                  />
                </aside>
              </ResizablePanel>
            </>
          )}
        </ResizablePanelGroup>
      </div>
      <div className="min-w-0 lg:hidden">
        {showPages && (
          <aside className="max-h-48 overflow-y-auto border-b bg-card">
            <PageNavigator pages={pages} current={current} evidence={evidence} onSelect={goTo} />
          </aside>
        )}
        <main className="max-h-[75svh] overflow-auto bg-canvas px-3 py-6 sm:px-8">
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
              focus={focus}
            />
          )}
        </main>
        {showInspector && (
          <aside className="max-h-[65svh] overflow-y-auto border-t bg-card">
            <CitedExcerpt
              citation={citation}
              error={citationQuery.error}
              pending={citationQuery.isFetching}
            />
            <EvidenceInspector
              evidence={evidence}
              pages={pages}
              selected={selected}
              filter={filter}
              onFilter={setFilter}
              onSelect={select}
            />
          </aside>
        )}
      </div>
    </div>
  );
}

function CitedExcerpt({
  citation,
  error,
  pending,
}: {
  citation: ChunkRef | null;
  error: unknown;
  pending: boolean;
}) {
  if (!citation && !error && !pending) return null;
  const region = citation?.regions[0];
  return (
    <section className="space-y-2 border-b px-4 py-3" aria-label="Cited evidence">
      <p className="eyebrow">Cited evidence</p>
      {pending && !citation && (
        <p className="text-xs text-muted-foreground">Loading the cited excerpt…</p>
      )}
      {error instanceof Error && <p className="text-xs text-destructive">{error.message}</p>}
      {citation && (
        <>
          <p className="text-xs text-muted-foreground">
            {[
              citation.documentTitle,
              citation.pages[0] ? `p. ${citation.pages[0]}` : null,
              citation.sectionPath.join(" › "),
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="whitespace-pre-wrap text-xs leading-relaxed">{citation.content}</p>
          {citation.table?.units && (
            <p className="font-mono text-[11px] text-muted-foreground">
              Units: {citation.table.units}
            </p>
          )}
          {citation.figure?.imageUrl && (
            <img
              src={apiAsset(citation.figure.imageUrl)}
              alt={citation.figure.caption ?? "Cited figure"}
              className="max-h-40 max-w-full"
            />
          )}
          <dl className="space-y-1 font-mono text-[11px] text-muted-foreground">
            <div>
              {citation.parser} {citation.parserVersion} · index {citation.indexVersion}
            </div>
            <div>sha256 {citation.sourceSha256}</div>
            {region && (
              <div>
                p. {region.page} · bbox {region.bbox.l.toFixed(1)}, {region.bbox.t.toFixed(1)},{" "}
                {region.bbox.r.toFixed(1)}, {region.bbox.b.toFixed(1)} pt
              </div>
            )}
          </dl>
        </>
      )}
    </section>
  );
}

function AwaitingPages({ doc }: { doc: FinDocument }) {
  const jobId = !IS_DEMO && doc.status === "processing" ? (doc.latestJobId ?? null) : null;
  const { data: job } = useQuery({
    ...jobQuery(jobId ?? "idle"),
    enabled: Boolean(jobId),
  });
  const processing = doc.status === "processing";
  const failed = doc.status === "failed";

  return (
    <div className="page-layout">
      <section className="mx-auto max-w-lg space-y-4 rounded-md border bg-card p-6">
        <p className="eyebrow">
          {processing ? "Processing" : failed ? "Processing failed" : "Document"}
        </p>
        <h1 className="text-2xl font-semibold">{doc.title}</h1>
        <p className="text-sm text-muted-foreground">
          {failed && doc.error?.message
            ? doc.error.message
            : processing
              ? "Pages, tables, and charts are being prepared. They appear here automatically."
              : "This report has no parsed pages to display yet."}
        </p>
        {processing && (
          <>
            <p className="text-xs capitalize text-muted-foreground">
              {job
                ? `${job.stage} · ${Math.round(job.progress * 100)}%`
                : "Waiting for the worker…"}
            </p>
            <Progress value={(job?.progress ?? 0) * 100} />
          </>
        )}
        {!processing && (
          <Button asChild variant="outline" size="sm">
            <Link to="/documents">Choose another PDF</Link>
          </Button>
        )}
      </section>
    </div>
  );
}

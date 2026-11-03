import { useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Highlighter,
  Minus,
  Plus,
  PanelLeft,
  PanelRight,
  ListFilter,
  MessageSquareText,
  ShieldCheck,
  TrendingUp,
  BookOpen,
  ScanLine,
  Maximize,
  Copy,
  Check,
  Focus,
  Minimize,
} from "lucide-react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useSidebar } from "@/components/ui/sidebar";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { ReportOverview } from "@/components/workspace/report-overview";
import type { PdfFit } from "@/lib/pdf-view";
import { PdfIntake } from "@/components/app/pdf-intake";
import { AnalysisPanel } from "@/components/workspace/analysis-panel";
import { ChartChecksPanel } from "@/components/workspace/audit-panel";
import { ComparisonPanel } from "@/components/workspace/trends-panel";
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
import { selectWorkspaceDocument } from "@/lib/workspace-selection";

const search = z.object({
  doc: z.string().optional(),
  page: z.number().int().min(1).optional(),
  ev: z.string().optional(),
  chunk: z.string().optional(),
  tool: z.enum(["overview", "evidence", "ask", "charts", "compare"]).optional(),
});

export const Route = createFileRoute("/intelligence")({
  validateSearch: search,
  loaderDeps: ({ search }) => ({ doc: search.doc }),
  loader: async ({ context, deps }) => {
    const docs = await context.queryClient.ensureQueryData(documentsQuery());
    const selection = selectWorkspaceDocument(deps.doc, IS_DEMO, DEFAULT_DOCUMENT_ID, docs);
    const { docId } = selection;
    if (!docId) return selection;
    await Promise.all([
      context.queryClient.ensureQueryData(documentQuery(docId)),
      context.queryClient.ensureQueryData(pagesQuery(docId)),
      context.queryClient.ensureQueryData(evidenceQuery(docId)),
    ]);
    return selection;
  },
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Report workspace — FINAUDIT AI" },
      {
        name: "description",
        content: "Inspect financial report pages, tables and charts with linked evidence.",
      },
      { property: "og:title", content: "Report workspace — FINAUDIT AI" },
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
  const { docId, awaitingLiveSession } = Route.useLoaderData();
  if (awaitingLiveSession)
    return (
      <div className="page-layout space-y-4">
        <h1 className="text-2xl font-semibold">Live report workspace</h1>
        <p className="text-sm text-muted-foreground">
          Checking live access. If no demo session is active, activate the demo to open this PDF.
        </p>
        <Button asChild>
          <Link to="/login">Activate live demo</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/documents">Back to documents</Link>
        </Button>
      </div>
    );
  if (!docId) {
    return (
      <div className="page-layout">
        <PdfIntake />
      </div>
    );
  }
  return <WorkspaceReady key={docId} docId={docId} />;
}

function WorkspaceReady({ docId }: { docId: string }) {
  const { page: pageParam, ev: evParam, chunk: chunkParam, tool = "overview" } = Route.useSearch();
  const queryClient = useQueryClient();
  const navigate = Route.useNavigate();
  const { data: doc } = useSuspenseQuery(documentQuery(docId));
  const pagesResult = useSuspenseQuery(pagesQuery(docId));
  const pages = pagesResult.data;
  const { data: evidence } = useSuspenseQuery(evidenceQuery(docId));
  const [filter, setFilter] = useState<EvidenceCategory | "all">("all");
  const [showHighlights, setShowHighlights] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [fit, setFit] = useState<PdfFit>("width");
  const [showPages, setShowPages] = useState(false);
  const [showInspector, setShowInspector] = useState(true);
  const [copied, setCopied] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [desktop, setDesktop] = useState(false);
  const [visitedTools, setVisitedTools] = useState<string[]>([tool]);
  const { setOpen } = useSidebar();
  const sidebarSetter = useRef(setOpen);
  sidebarSetter.current = setOpen;
  const [preferencesReady, setPreferencesReady] = useState(false);
  useEffect(() => {
    sidebarSetter.current(false);
    const media = window.matchMedia("(min-width: 1024px)");
    const update = () => setDesktop(media.matches);
    update();
    media.addEventListener("change", update);
    return () => {
      media.removeEventListener("change", update);
      sidebarSetter.current(true);
    };
  }, []);
  useEffect(() => {
    try {
      const stored = JSON.parse(
        window.sessionStorage.getItem(`finaudit:reader:${docId}`) || "null",
      );
      if (stored && ["width", "page", "custom"].includes(stored.fit)) {
        setFit(stored.fit);
        if (typeof stored.zoom === "number" && stored.zoom >= 0.5 && stored.zoom <= 2)
          setZoom(stored.zoom);
        setShowHighlights(stored.highlights === true);
      }
    } catch {
      /* Optional reader preferences never affect service selection. */
    }
    setPreferencesReady(true);
  }, [docId]);
  useEffect(() => {
    if (preferencesReady)
      window.sessionStorage.setItem(
        `finaudit:reader:${docId}`,
        JSON.stringify({ fit, zoom, highlights: showHighlights }),
      );
  }, [docId, fit, zoom, showHighlights, preferencesReady]);
  useEffect(() => {
    setVisitedTools((current) => (current.includes(tool) ? current : [...current, tool]));
  }, [tool]);
  const previousStatus = useRef(doc.status);
  const retriedEmptyPages = useRef(false);
  useEffect(() => {
    if (
      (previousStatus.current === "processing" && doc.status !== "processing") ||
      (doc.status === "ready" && pages.length === 0 && !retriedEmptyPages.current)
    ) {
      retriedEmptyPages.current = true;
      for (const key of [["pages", docId], ["evidence", docId], ["documents"]])
        void queryClient.invalidateQueries({ queryKey: key });
    }
    previousStatus.current = doc.status;
  }, [doc.status, docId, pages.length, queryClient]);
  const citationQuery = useQuery({
    queryKey: ["citation", chunkParam],
    queryFn: () => {
      if (!api.getCitation || !chunkParam) throw new Error("Citation unavailable");
      return api.getCitation(chunkParam);
    },
    enabled: Boolean(chunkParam && api.getCitation),
  });
  const loadedCitation = citationQuery.data;
  const citation =
    loadedCitation && loadedCitation.chunkId === chunkParam && loadedCitation.documentId === docId
      ? loadedCitation
      : null;
  const current = Math.min(pageParam ?? 1, Math.max(pages.length, 1));
  const page = pages.find((p) => p.number === current);
  const selected = useMemo(
    () => evidence.find((item) => item.id === evParam) ?? null,
    [evidence, evParam],
  );
  const focus =
    citation?.regions
      .filter((region) => region.page === current)
      .map((region) => region.bboxNormalized) ?? [];
  const goTo = (number: number) => {
    if (number < 1 || number > pages.length) return;
    void navigate({
      search: (s) => ({ ...s, page: number, ev: undefined, chunk: undefined }),
      replace: true,
    });
  };
  const select = (id: string | null) => {
    const item = evidence.find((entry) => entry.id === id);
    setShowInspector(true);
    if (item) setShowHighlights(true);
    void navigate({
      search: (s) => ({
        ...s,
        ev: item?.id,
        page: item?.page ?? current,
        tool: "evidence",
        chunk: undefined,
      }),
      replace: true,
    });
  };
  const changeTool = (next: "overview" | "evidence" | "ask" | "charts" | "compare") => {
    setShowInspector(true);
    void navigate({ search: (s) => ({ ...s, tool: next }), replace: true });
  };
  const lastTool = useRef(tool);
  useEffect(() => {
    const changed = lastTool.current !== tool;
    lastTool.current = tool;
    if (!desktop && changed) {
      const frame = requestAnimationFrame(() => {
        document
          .querySelector<HTMLElement>(".report-inspector:not(:empty)")
          ?.scrollIntoView({ block: "start" });
      });
      return () => cancelAnimationFrame(frame);
    }
    return undefined;
  }, [tool, desktop]);
  useEffect(() => {
    if (selected) {
      setShowHighlights(true);
      setShowInspector(true);
      if (selected.page !== current)
        void navigate({ search: (s) => ({ ...s, page: selected.page }), replace: true });
    }
  }, [selected, current, navigate]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        (event.target as HTMLElement)?.closest(
          "input,textarea,select,button,[role=tab],[contenteditable=true],[role=separator]",
        )
      )
        return;
      if (event.key === "ArrowRight") {
        event.preventDefault();
        goTo(current + 1);
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        goTo(current - 1);
      }
      if (event.key === "Escape") select(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  const tools = [
    { id: "overview", label: "Overview", icon: BookOpen },
    { id: "evidence", label: "Evidence", icon: ListFilter },
    { id: "ask", label: "Ask AI", icon: MessageSquareText },
    { id: "charts", label: "Audit", icon: ShieldCheck },
    { id: "compare", label: "Trends", icon: TrendingUp },
  ] as const;
  const toolContent = (
    <>
      <nav
        className="inspector-tabs sticky top-0 z-10 grid grid-cols-5 border-b bg-card px-2"
        aria-label="Report inspector"
      >
        {tools.map(({ id, label, icon: Icon }) => (
          <Button
            key={id}
            variant="ghost"
            aria-pressed={tool === id}
            className="inspector-tab h-14 min-w-0 flex-col gap-1 rounded-none px-0 text-[11px] font-medium"
            data-active={tool === id}
            onClick={() => changeTool(id)}
          >
            <Icon className="size-4" />
            {label}
          </Button>
        ))}
      </nav>
      <div hidden={tool !== "overview"}>
        <ReportOverview
          doc={doc}
          pages={pages}
          evidence={evidence}
          current={current}
          onPage={goTo}
          onEvidence={() => changeTool("evidence")}
          onTool={changeTool}
        />
      </div>
      <div hidden={tool !== "evidence"}>
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
          currentPage={current}
          onFilter={setFilter}
          onSelect={select}
        />
      </div>
      <div className="@container" hidden={tool === "overview" || tool === "evidence"}>
        {(citation || (chunkParam && citationQuery.isFetching) || citationQuery.error) && (
          <details className="border-b px-4 py-3">
            <summary className="cursor-pointer text-xs font-medium">
              Selected source{citation?.pages[0] ? ` · p. ${citation.pages[0]}` : ""}
            </summary>
            <CitedExcerpt
              citation={citation}
              error={citationQuery.error}
              pending={citationQuery.isFetching}
            />
          </details>
        )}
        {visitedTools.includes("ask") && (
          <div hidden={tool !== "ask"}>
            <AnalysisPanel key={docId} documentId={docId} embedded />
          </div>
        )}
        {visitedTools.includes("charts") && (
          <div hidden={tool !== "charts"}>
            <ChartChecksPanel key={docId} documentId={docId} embedded />
          </div>
        )}
        {visitedTools.includes("compare") && (
          <div hidden={tool !== "compare"}>
            <ComparisonPanel key={docId} documentId={docId} embedded />
          </div>
        )}
      </div>
    </>
  );
  if (doc.status === "ready" && pages.length === 0 && pagesResult.isFetching)
    return <WorkspaceSkeleton />;
  if (doc.status !== "ready" || pages.length === 0) return <AwaitingPages doc={doc} />;
  const adjustZoom = (delta: number) => {
    setFit("custom");
    setZoom((value) => Math.max(0.5, Math.min(2, Number((value + delta).toFixed(1)))));
  };
  const reader = (
    <main className="report-canvas h-full min-h-0 overflow-auto" aria-label="Document canvas">
      {page && (
        <DocumentPageView
          page={page}
          totalPages={pages.length}
          evidence={evidence}
          selectedId={selected?.id ?? null}
          showHighlights={showHighlights}
          zoom={zoom}
          fit={fit}
          onSelect={select}
          documentTitle={doc.title}
          focus={focus}
        />
      )}
    </main>
  );
  return (
    <div
      className={`report-workspace flex min-w-0 flex-col ${focusMode ? "report-focus" : "lg:h-[calc(100svh-3.5rem)]"}`}
    >
      <header className="report-toolbar grid shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-2 border-b bg-card px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <ReaderAction label="Back to library">
            <Button asChild variant="ghost" size="icon" className="size-8 shrink-0">
              <Link to="/documents" aria-label="Back to library">
                <ArrowLeft className="size-4" />
              </Link>
            </Button>
          </ReaderAction>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold" title={doc.title}>
              {doc.title}
            </h1>
            <p className="truncate text-[11px] text-muted-foreground">
              {[doc.issuer, doc.period].filter(Boolean).join(" · ") || `${pages.length} pages`}
              {IS_DEMO ? " · Synthetic sample" : ""}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <ReaderAction label="Previous page">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Previous page"
              disabled={current <= 1}
              onClick={() => goTo(current - 1)}
            >
              <ChevronLeft className="size-4" />
            </Button>
          </ReaderAction>
          <div className="flex items-center font-mono text-xs">
            <Input
              key={current}
              type="number"
              min={1}
              max={pages.length}
              defaultValue={current}
              aria-label="Page number"
              className="h-7 w-10 border-transparent bg-transparent p-1 text-center text-xs [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
              onBlur={(event) => goTo(Number(event.target.value))}
              onKeyDown={(event) => {
                if (event.key === "Enter") goTo(Number(event.currentTarget.value));
              }}
            />
            <span className="pr-1 text-muted-foreground">/ {pages.length}</span>
          </div>
          <ReaderAction label="Next page">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Next page"
              disabled={current >= pages.length}
              onClick={() => goTo(current + 1)}
            >
              <ChevronRight className="size-4" />
            </Button>
          </ReaderAction>
          <span className="mx-1 hidden h-5 border-l sm:block" />
          <ReaderAction label="Pages">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Pages"
              aria-pressed={showPages}
              onClick={() => setShowPages((value) => !value)}
            >
              <PanelLeft className="size-4" />
            </Button>
          </ReaderAction>
          <ReaderAction label="Toggle inspector">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Toggle inspector"
              aria-pressed={showInspector}
              onClick={() => setShowInspector((value) => !value)}
            >
              <PanelRight className="size-4" />
            </Button>
          </ReaderAction>
        </div>
        <div className="report-view-controls col-span-2 flex items-center justify-end gap-0.5 lg:col-span-1">
          <ReaderAction label="Zoom out">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Zoom out"
              onClick={() => adjustZoom(-0.1)}
            >
              <Minus className="size-3.5" />
            </Button>
          </ReaderAction>
          <span className="w-12 text-center font-mono text-[11px] text-muted-foreground">
            {fit === "custom" ? `${Math.round(zoom * 100)}%` : "Auto"}
          </span>
          <ReaderAction label="Zoom in">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Zoom in"
              onClick={() => adjustZoom(0.1)}
            >
              <Plus className="size-3.5" />
            </Button>
          </ReaderAction>
          <ReaderAction label="Fit Width">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Fit Width"
              aria-pressed={fit === "width"}
              onClick={() => setFit("width")}
            >
              <ScanLine className="size-4" />
            </Button>
          </ReaderAction>
          <ReaderAction label="Fit Page">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Fit Page"
              aria-pressed={fit === "page"}
              onClick={() => setFit("page")}
            >
              <Maximize className="size-4" />
            </Button>
          </ReaderAction>
          <ReaderAction label="Highlights">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Highlights"
              aria-pressed={showHighlights}
              onClick={() => setShowHighlights((value) => !value)}
            >
              <Highlighter className="size-4" />
            </Button>
          </ReaderAction>
          <ReaderAction label={focusMode ? "Exit focus mode" : "Focus mode"}>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label={focusMode ? "Exit focus mode" : "Focus mode"}
              aria-pressed={focusMode}
              onClick={() => setFocusMode((value) => !value)}
            >
              {focusMode ? <Minimize className="size-4" /> : <Focus className="size-4" />}
            </Button>
          </ReaderAction>
          {!IS_DEMO && page?.imageUrl && doc.sha256 && (
            <ReaderAction label="Open original PDF">
              <Button asChild variant="ghost" size="icon" className="size-8">
                <a
                  href={sourceDocumentUrl(doc.id)}
                  target="_blank"
                  rel="noreferrer"
                  aria-label="Open original PDF"
                >
                  <ExternalLink className="size-4" />
                </a>
              </Button>
            </ReaderAction>
          )}
          {(selected?.provenance || citation) && (
            <ReaderAction label="Copy citation">
              <Button
                variant="ghost"
                size="icon"
                className="size-8"
                aria-label="Copy citation"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      `${doc.title}, p. ${current}${selected ? ` · ${selected.label}` : ""} — ${window.location.href}`,
                    );
                    setCopied(true);
                    window.setTimeout(() => setCopied(false), 2000);
                  } catch {
                    setCopied(false);
                  }
                }}
              >
                {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              </Button>
            </ReaderAction>
          )}
        </div>
      </header>
      <div className="relative hidden min-h-0 flex-1 lg:block">
        {showPages && (
          <aside
            className="absolute inset-y-0 left-0 z-20 w-60 overflow-y-auto border-r bg-card shadow-page"
            aria-label="Page thumbnails"
          >
            <div className="flex items-center justify-between border-b px-3 py-2">
              <span className="text-xs font-medium">Page thumbnails</span>
              <Button variant="ghost" size="sm" onClick={() => setShowPages(false)}>
                Close
              </Button>
            </div>
            <PageNavigator pages={pages} current={current} evidence={evidence} onSelect={goTo} />
          </aside>
        )}
        <ResizablePanelGroup orientation="horizontal" id="document-workspace">
          <ResizablePanel id="document" defaultSize="65%" minSize="45%">
            {reader}
          </ResizablePanel>
          {showInspector && (
            <>
              <ResizableHandle aria-label="Resize inspector" />
              <ResizablePanel id="inspector" defaultSize="35%" minSize="320px" maxSize="50%">
                <aside
                  className="report-inspector h-full overflow-y-auto bg-card"
                  aria-label="Report inspector"
                >
                  {desktop && toolContent}
                </aside>
              </ResizablePanel>
            </>
          )}
        </ResizablePanelGroup>
      </div>
      <div className="min-w-0 lg:hidden">
        {showPages && (
          <aside className="max-h-52 overflow-auto border-b">
            <PageNavigator pages={pages} current={current} evidence={evidence} onSelect={goTo} />
          </aside>
        )}
        <div className="h-[70svh]">{reader}</div>
        {showInspector && (
          <aside
            className="report-inspector max-h-[75svh] overflow-y-auto border-t bg-card"
            aria-label="Report inspector"
          >
            {!desktop && toolContent}
          </aside>
        )}
      </div>
      <footer className="flex h-7 shrink-0 items-center justify-between border-t bg-card px-4 text-[10px] text-muted-foreground">
        <span className="truncate">
          {page?.section || `Page ${current}`} ·{" "}
          {evidence.filter((item) => item.page === current).length} regions
        </span>
        <span className="ml-3 shrink-0">
          {IS_DEMO
            ? "DEMO · illustrative extraction"
            : `${doc.parser?.name || "Document"} · ${doc.status}`}
        </span>
      </footer>
    </div>
  );
}

function ReaderAction({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
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

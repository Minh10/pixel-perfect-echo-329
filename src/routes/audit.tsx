import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { PendingModule } from "@/components/app/pending-module";
import { EmptyState, ErrorState, PageHeader } from "@/components/app/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiAsset } from "@/lib/api/http-service";
import { visualDiscrepancy } from "@/lib/fact-comparison";
import { IS_DEMO, api, documentsQuery, evidenceQuery, pagesQuery } from "@/lib/api/service";
import type { ChartInterpretation, Evidence, PageBlock } from "@/lib/api/types";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: "Consistency Audit — FINAUDIT AI" },
      {
        name: "description",
        content:
          "Inspect chart crops and compare them with reported table facts when a reading exists.",
      },
    ],
  }),
  component: AuditPage,
});

function AuditPage() {
  if (IS_DEMO || !api.getFacts || !api.searchEvidence) {
    return (
      <PendingModule
        eyebrow="Analysis"
        title="Consistency Audit"
        description="Cross-check figures stated in narrative text against tables and charts to flag potential inconsistencies."
        icon={<ShieldCheck className="size-5" />}
        planned={[
          "Narrative vs. table figure reconciliation",
          "Recomputation of derived ratios",
          "Period-over-period restatement detection",
          "Reviewer sign-off workflow",
        ]}
      />
    );
  }
  return <AuditWorkspace />;
}

function AuditWorkspace() {
  const documents = useQuery(documentsQuery());
  const ready = (documents.data ?? []).filter((doc) => doc.status === "ready");
  const [documentId, setDocumentId] = useState<string>("");
  const selectedId = documentId || ready[0]?.id || "";
  const evidence = useQuery({
    ...evidenceQuery(selectedId),
    enabled: Boolean(selectedId),
  });
  const pages = useQuery({ ...pagesQuery(selectedId), enabled: Boolean(selectedId) });
  const figures = (evidence.data ?? []).filter((item) => item.category === "figure");
  const [blockId, setBlockId] = useState<string>("");
  const figure = figures.find((item) => item.id === blockId) ?? figures[0] ?? null;
  const crop = figure ? figureBlock(pages.data ?? [], figure) : null;
  const facts = useQuery({
    queryKey: ["facts", selectedId],
    queryFn: () => api.getFacts!(selectedId),
    enabled: Boolean(selectedId && api.getFacts),
  });
  const interpretation = useQuery({
    queryKey: ["interpretation", selectedId, figure?.blockId],
    queryFn: () => api.getFigureInterpretation!(selectedId, figure!.blockId),
    enabled: Boolean(selectedId && figure && api.getFigureInterpretation),
    retry: false,
  });
  const queryClient = useQueryClient();
  const interpret = useMutation({
    mutationFn: () => api.interpretFigure!(selectedId, figure!.blockId),
    onSuccess: (data) => {
      queryClient.setQueryData(["interpretation", selectedId, figure?.blockId], data);
    },
  });

  return (
    <div className="page-layout space-y-6">
      <PageHeader
        eyebrow="Analysis"
        title="Consistency Audit"
        description="Inspect an extracted chart crop. A written summary is shown only when a vision model actually reads the image."
      />
      <label className="block max-w-md text-sm">
        <span className="text-xs text-muted-foreground">Processed report</span>
        <select
          className="mt-1 h-9 w-full rounded-md border bg-transparent px-3"
          value={selectedId}
          onChange={(event) => {
            setDocumentId(event.target.value);
            setBlockId("");
          }}
        >
          {ready.map((doc) => (
            <option key={doc.id} value={doc.id}>
              {doc.title}
            </option>
          ))}
        </select>
      </label>
      {figures.length === 0 && !evidence.isLoading && (
        <EmptyState
          title="No figure crop"
          description="This report has no extracted figure. Upload a PDF that contains a chart or diagram."
        />
      )}
      {figure && (
        <section className="grid gap-4 lg:grid-cols-2">
          <article className="rounded-md border bg-card p-4">
            <p className="eyebrow mb-3">Extracted crop</p>
            {crop?.figure?.imageUrl ? (
              <img
                src={apiAsset(crop.figure.imageUrl)}
                alt={crop.figure.caption ?? figure.label}
                className="max-h-80 max-w-full"
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                The parser did not provide a crop image.
              </p>
            )}
            <p className="mt-3 text-sm">{crop?.figure?.caption ?? figure.excerpt}</p>
            <p className="mt-1 text-xs text-muted-foreground">Page {figure.page}</p>
            <SourceLink documentId={selectedId} page={figure.page} evidenceId={figure.id} />
          </article>
          <article className="space-y-3 rounded-md border bg-card p-4">
            <p className="eyebrow">Chart-to-text</p>
            <Button
              type="button"
              disabled={!figure || interpret.isPending || !api.interpretFigure}
              onClick={() => interpret.mutate()}
            >
              {interpret.isPending ? "Reading chart…" : "Read chart with the configured model"}
            </Button>
            <ChartSummary
              reading={interpret.data ?? interpretation.data}
              unavailable={
                interpret.error ??
                (interpretation.error instanceof ApiError && interpretation.error.status === 404
                  ? null
                  : interpretation.error)
              }
              caption={crop?.figure?.caption ?? figure.excerpt}
            />
          </article>
        </section>
      )}
      <section className="space-y-3 rounded-md border bg-card p-4">
        <p className="eyebrow">Visual check</p>
        <DiscrepancyList
          documentId={selectedId}
          reading={interpret.data ?? (interpretation.data as ChartInterpretation | undefined)}
          facts={facts.data ?? []}
        />
      </section>
      <EvidenceSearch documentIds={selectedId ? [selectedId] : []} />
    </div>
  );
}

function figureBlock(pages: { blocks: PageBlock[] }[], evidence: Evidence): PageBlock | null {
  for (const page of pages) {
    const block = page.blocks.find((item) => item.id === evidence.blockId);
    if (block) return block;
  }
  return null;
}

function ChartSummary({
  reading,
  unavailable,
  caption,
}: {
  reading: ChartInterpretation | undefined;
  unavailable: unknown;
  caption: string;
}) {
  const missingModel =
    unavailable instanceof ApiError &&
    (unavailable.status === 503 || unavailable.code === "llm_unavailable");
  if (missingModel || (!reading && unavailable instanceof ApiError)) {
    return (
      <ErrorState
        title="Visual interpretation is unavailable"
        message="No chart summary was generated. The crop and any printed caption are the only evidence shown."
      />
    );
  }
  if (!reading) {
    return (
      <p className="text-sm text-muted-foreground">
        No model reading is stored. Caption from the PDF: {caption || "none"}.
      </p>
    );
  }
  return (
    <div className="space-y-2 text-sm">
      <p>
        {reading.title || reading.chartType || "Chart reading"}{" "}
        <span className="text-xs text-primary">Visual estimate from chart, approximate</span>
      </p>
      <ul className="space-y-1">
        {reading.points.map((point) => (
          <li key={`${point.label}-${point.value}`}>
            {point.label}
            {point.series ? ` (${point.series})` : ""}: {point.value}
            {point.unit ? ` ${point.unit}` : ""}
            {point.printedOnChart ? " · printed label" : " · estimated from the graphic"}
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">{reading.caveat}</p>
      <p className="text-xs text-muted-foreground">
        {reading.provider} · {reading.model}
      </p>
    </div>
  );
}

function DiscrepancyList({
  documentId,
  reading,
  facts,
}: {
  documentId: string;
  reading: ChartInterpretation | undefined;
  facts: Parameters<typeof visualDiscrepancy>[1];
}) {
  if (!reading) {
    return (
      <p className="text-sm">
        <strong>INSUFFICIENT_EVIDENCE.</strong> Automated chart-to-table auditing is not available
        until a vision model reads this crop.
      </p>
    );
  }
  if (reading.tableChecks.length === 0) {
    return (
      <p className="text-sm">
        <strong>INSUFFICIENT_EVIDENCE.</strong> The reading did not include a table comparison.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {reading.tableChecks.map((check) => {
        const result = visualDiscrepancy(check, facts);
        return (
          <li key={`${check.label}-${check.estimate}`} className="text-sm">
            <strong>{result.status}.</strong> {check.label}: {result.detail}
            <span className="mt-1 block">
              <SourceLink documentId={documentId} page={facts[0]?.page ?? 1} evidenceId={null} />
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function EvidenceSearch({ documentIds }: { documentIds: string[] }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("operating profit");
  const search = useMutation({
    mutationFn: () => api.searchEvidence!(query, documentIds),
  });
  return (
    <section className="space-y-3">
      <p className="eyebrow">Search financial evidence</p>
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          if (query.trim().length >= 2) search.mutate();
        }}
      >
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Evidence search"
        />
        <Button type="submit" disabled={search.isPending}>
          {search.isPending ? "Searching…" : "Search"}
        </Button>
      </form>
      {search.isError && (
        <ErrorState
          title="Evidence search failed"
          message={
            search.error instanceof Error ? search.error.message : "The retrieval service failed."
          }
        />
      )}
      <ul className="space-y-2">
        {(search.data?.results ?? []).map((hit) => {
          const region = hit.chunk.regions[0];
          return (
            <li key={hit.chunk.chunkId}>
              <button
                type="button"
                className="w-full rounded-md border px-3 py-2 text-left text-sm"
                onClick={() =>
                  navigate({
                    to: "/intelligence",
                    search: {
                      doc: hit.chunk.documentId,
                      ...(region ? { page: region.page } : {}),
                      ...(region?.workspaceEvidenceId ? { ev: region.workspaceEvidenceId } : {}),
                      chunk: hit.chunk.chunkId,
                    },
                  })
                }
              >
                <span className="text-xs text-muted-foreground">
                  Rank {hit.rank} · {hit.chunk.kind} · p. {hit.chunk.pages[0]} ·{" "}
                  {search.data?.effectiveMethod}
                </span>
                <span className="mt-1 block">{hit.chunk.content.slice(0, 220)}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {search.data && search.data.warnings.length > 0 && (
        <p className="text-xs text-muted-foreground">{search.data.warnings.join(" ")}</p>
      )}
    </section>
  );
}

function SourceLink({
  documentId,
  page,
  evidenceId,
}: {
  documentId: string;
  page: number;
  evidenceId: string | null;
}) {
  const navigate = useNavigate();
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() =>
        navigate({
          to: "/intelligence",
          search: {
            doc: documentId,
            page,
            ...(evidenceId ? { ev: evidenceId } : {}),
          },
        })
      }
    >
      Open source page
    </Button>
  );
}

import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Minus, Plus, ShieldCheck } from "lucide-react";
import { PendingModule } from "@/components/app/pending-module";
import { ReviewStatus } from "@/components/app/review-status";
import { EmptyState, ErrorState, PageHeader } from "@/components/app/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiAsset } from "@/lib/api/http-service";
import { visualDiscrepancy } from "@/lib/fact-comparison";
import { IS_DEMO, api, documentsQuery, evidenceQuery, pagesQuery } from "@/lib/api/service";
import type { ChartInterpretation, Evidence, PageBlock, TableCheck } from "@/lib/api/types";

export const Route = createFileRoute("/audit")({
  validateSearch: (search: Record<string, unknown>) => {
    const doc = search["doc"];
    return { doc: typeof doc === "string" && doc.length > 0 ? doc : undefined };
  },
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
      />
    );
  }
  return <AuditWorkspace />;
}

function AuditWorkspace() {
  const { doc: requestedId } = Route.useSearch();
  const documents = useQuery(documentsQuery());
  const ready = (documents.data ?? []).filter((doc) => doc.status === "ready");
  const [documentId, setDocumentId] = useState<string>(requestedId ?? "");
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
  const [zoom, setZoom] = useState(1);
  const [selectedCheck, setSelectedCheck] = useState<string | null>(null);
  const interpret = useMutation({
    mutationFn: () => api.interpretFigure!(selectedId, figure!.blockId),
    onSuccess: (data) => {
      queryClient.setQueryData(["interpretation", selectedId, figure?.blockId], data);
    },
  });

  const reading = interpret.data ?? (interpretation.data as ChartInterpretation | undefined);
  const document = ready.find((item) => item.id === selectedId);
  const rows = (reading?.tableChecks ?? []).map((check) => ({
    check,
    result: visualDiscrepancy(check, facts.data ?? []),
  }));
  const counts = {
    compared: rows.length,
    matched: rows.filter((row) => row.result.status === "MATCH").length,
    discrepancy: rows.filter((row) => row.result.status === "POTENTIAL_DISCREPANCY").length,
    insufficient: rows.filter((row) => row.result.status === "INSUFFICIENT_EVIDENCE").length,
  };

  return (
    <div className="page-layout space-y-8">
      <PageHeader
        eyebrow="Visual analysis"
        title="Consistency Audit"
        description="Compare a chart reading with the reported table facts from the same document."
      />
      <div className="grid gap-6 border-b pb-6 lg:grid-cols-[minmax(0,1.4fr)_auto] lg:items-end">
        <label className="block max-w-xl text-sm">
          <span className="text-xs text-muted-foreground">Processed report</span>
          <select
            className="mt-1 h-10 w-full rounded-md border bg-card px-3"
            value={selectedId}
            onChange={(event) => {
              setDocumentId(event.target.value);
              setBlockId("");
              setSelectedCheck(null);
            }}
          >
            {ready.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.title}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs text-muted-foreground">
            {[document?.issuer, document?.period, document?.type].filter(Boolean).join(" · ") ||
              "Issuer and period are taken from the processed report."}
          </p>
        </label>
        <p className="text-xs text-muted-foreground">
          {reading
            ? `Model ${reading.provider} · ${reading.model}`
            : "No stored chart reading for this figure."}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border bg-border md:grid-cols-4">
        <Kpi label="Compared values" value={reading ? counts.compared : "—"} />
        <Kpi label="Matches" value={reading ? counts.matched : "—"} />
        <Kpi label="Potential discrepancies" value={reading ? counts.discrepancy : "—"} />
        <Kpi label="Insufficient evidence" value={reading ? counts.insufficient : "—"} />
      </dl>
      {figures.length === 0 && !evidence.isLoading && (
        <EmptyState
          title="No figure crop"
          description="This report has no extracted figure. Upload a PDF that contains a chart or diagram."
        />
      )}
      {figure && (
        <section className="grid items-start gap-8 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
          <article className="min-w-0">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="eyebrow">Source figure</p>
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-8"
                  aria-label="Zoom out"
                  onClick={() => setZoom((value) => Math.max(0.8, +(value - 0.1).toFixed(1)))}
                >
                  <Minus className="size-4" />
                </Button>
                <span className="w-10 text-center font-mono text-xs tabular">
                  {Math.round(zoom * 100)}%
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-8"
                  aria-label="Zoom in"
                  onClick={() => setZoom((value) => Math.min(1.8, +(value + 0.1).toFixed(1)))}
                >
                  <Plus className="size-4" />
                </Button>
              </div>
            </div>
            <div className="overflow-auto rounded-md border bg-paper p-4">
              {crop?.figure?.imageUrl ? (
                <img
                  src={apiAsset(crop.figure.imageUrl)}
                  alt={crop.figure.caption ?? figure.label}
                  style={{ width: `${zoom * 100}%`, maxWidth: "none" }}
                  className="mx-auto"
                />
              ) : (
                <p className="text-sm text-muted-foreground">
                  The parser did not provide a crop image.
                </p>
              )}
            </div>
            <p className="mt-3 text-sm">{crop?.figure?.caption ?? figure.excerpt}</p>
            <div className="mt-2 flex items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">Page {figure.page}</p>
              <SourceLink
                documentId={selectedId}
                page={figure.page}
                evidenceId={figure.id}
                label="Open chart page"
              />
            </div>
          </article>
          <ChartSummary
            reading={reading}
            pending={interpret.isPending}
            canRead={Boolean(figure && api.interpretFigure)}
            onRead={() => interpret.mutate()}
            unavailable={
              interpret.error ??
              (interpretation.error instanceof ApiError && interpretation.error.status === 404
                ? null
                : interpretation.error)
            }
            caption={crop?.figure?.caption ?? figure.excerpt}
          />
        </section>
      )}
      <ComparisonTable
        documentId={selectedId}
        rows={rows}
        selectedKey={selectedCheck}
        onSelect={setSelectedCheck}
        hasReading={Boolean(reading)}
      />
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

function caveatFor(reading: ChartInterpretation): string {
  if (reading.points.length === 0) return "No chart values were extracted.";
  const printed = reading.points
    .filter((point) => point.printedOnChart)
    .map((point) => point.label);
  const estimated = reading.points
    .filter((point) => !point.printedOnChart)
    .map((point) => point.label);
  const parts: string[] = [];
  if (printed.length > 0 && estimated.length === 0) {
    parts.push("Every number was copied from a printed label on the chart.");
  } else if (estimated.length > 0 && printed.length === 0) {
    parts.push("Every number is a visual estimate. No printed data label was read.");
  } else {
    parts.push(`Printed chart labels: ${printed.join(", ")}.`);
    parts.push(`Visual estimates from the graphic: ${estimated.join(", ")}.`);
  }
  parts.push("These readings are not reported table figures.");
  return parts.join(" ");
}

function Kpi({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-card px-4 py-4">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-2 font-serif text-3xl tabular">{value}</dd>
    </div>
  );
}

function ChartSummary({
  reading,
  unavailable,
  caption,
  pending,
  canRead,
  onRead,
}: {
  reading: ChartInterpretation | undefined;
  unavailable: unknown;
  caption: string;
  pending: boolean;
  canRead: boolean;
  onRead: () => void;
}) {
  const missingModel =
    unavailable instanceof ApiError &&
    (unavailable.status === 503 || unavailable.code === "llm_unavailable");
  return (
    <article className="min-w-0 space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Chart-to-text</p>
          <h2 className="mt-1 font-serif text-2xl">
            {reading?.title || reading?.chartType || "No stored reading"}
          </h2>
        </div>
        <Button
          type="button"
          variant={reading ? "outline" : "default"}
          disabled={!canRead || pending}
          onClick={onRead}
        >
          {pending ? "Reading…" : reading ? "Re-analyse" : "Read chart"}
        </Button>
      </div>
      {missingModel || (!reading && unavailable instanceof ApiError) ? (
        <ErrorState
          title="Visual interpretation is unavailable"
          message="No chart summary was generated. The crop and any printed caption are the only evidence shown."
        />
      ) : null}
      {!reading && !unavailable ? (
        <p className="text-sm text-muted-foreground">
          No model reading is stored. Caption from the PDF: {caption || "none"}.
        </p>
      ) : null}
      {reading ? (
        <>
          {reading.summary && (
            <p className="max-w-prose text-[15px] leading-7">{reading.summary}</p>
          )}
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b">
                <th className="px-2 py-2 font-medium">Point</th>
                <th className="px-2 py-2 text-right font-medium">Value</th>
                <th className="px-2 py-2 font-medium">Basis</th>
              </tr>
            </thead>
            <tbody>
              {reading.points.map((point) => (
                <tr key={`${point.label}-${point.value}`} className="border-b">
                  <td className="px-2 py-2">
                    {point.label}
                    {point.series ? ` · ${point.series}` : ""}
                    {point.period ? (
                      <span className="text-muted-foreground"> · {point.period}</span>
                    ) : null}
                  </td>
                  <td className="px-2 py-2 text-right font-mono tabular">
                    {point.value}
                    {point.unit ? ` ${point.unit}` : ""}
                  </td>
                  <td className="px-2 py-2 text-xs text-muted-foreground">
                    {point.printedOnChart ? "Printed on the chart" : "Estimated from the graphic"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs leading-5 text-muted-foreground">{caveatFor(reading)}</p>
          <p className="text-xs text-muted-foreground">
            {reading.provider} · {reading.model}
          </p>
        </>
      ) : null}
    </article>
  );
}

function ComparisonTable({
  documentId,
  rows,
  selectedKey,
  onSelect,
  hasReading,
}: {
  documentId: string;
  rows: { check: TableCheck; result: ReturnType<typeof visualDiscrepancy> }[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
  hasReading: boolean;
}) {
  if (!hasReading) {
    return (
      <p className="text-sm">
        <ReviewStatus status="INSUFFICIENT_EVIDENCE" /> Automated chart-to-table comparison is not
        available until a vision model reads this crop.
      </p>
    );
  }
  if (rows.length === 0) {
    return (
      <p className="text-sm">
        <ReviewStatus status="INSUFFICIENT_EVIDENCE" /> The reading did not include a table
        comparison.
      </p>
    );
  }
  return (
    <section className="space-y-3">
      <div>
        <h2 className="font-serif text-2xl">Chart versus reported table</h2>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          A potential discrepancy means the chart point and one aligned reported fact differ. It is
          not a verified finding of financial fraud.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="text-left text-xs text-muted-foreground">
            <tr className="border-b">
              <th className="px-2 py-2 font-medium">Metric</th>
              <th className="px-2 py-2 font-medium">Period</th>
              <th className="px-2 py-2 text-right font-medium">Chart</th>
              <th className="px-2 py-2 text-right font-medium">Reported</th>
              <th className="px-2 py-2 text-right font-medium">Absolute</th>
              <th className="px-2 py-2 text-right font-medium">Relative</th>
              <th className="px-2 py-2 font-medium">Review</th>
              <th className="px-2 py-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ check, result }) => {
              const key = `${check.label}-${check.estimate}`;
              const tone =
                result.status === "POTENTIAL_DISCREPANCY"
                  ? "bg-warning-soft/70"
                  : selectedKey === key
                    ? "bg-muted/60"
                    : "";
              return (
                <tr
                  key={key}
                  className={`cursor-pointer border-b ${tone}`}
                  onClick={() => onSelect(key)}
                >
                  <td className="px-2 py-3">{check.label}</td>
                  <td className="px-2 py-3">{check.period ?? "—"}</td>
                  <td className="px-2 py-3 text-right font-mono tabular">{check.estimate}</td>
                  <td className="px-2 py-3 text-right font-mono tabular">
                    {check.tableValue ?? "—"}
                  </td>
                  <td className="px-2 py-3 text-right font-mono tabular">
                    {check.absoluteDifference ?? "—"}
                  </td>
                  <td className="px-2 py-3 text-right font-mono tabular">
                    {check.relativeDifference == null
                      ? "—"
                      : `${(check.relativeDifference * 100).toFixed(1)}%`}
                  </td>
                  <td className="px-2 py-3">
                    <ReviewStatus status={result.status} />
                  </td>
                  <td className="px-2 py-3">
                    {result.page != null ? (
                      <SourceLink
                        documentId={documentId}
                        page={result.page}
                        evidenceId={result.evidenceId}
                        label="Table"
                      />
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
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
  label = "Open source page",
}: {
  documentId: string;
  page: number;
  evidenceId: string | null;
  label?: string;
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
      {label}
    </Button>
  );
}

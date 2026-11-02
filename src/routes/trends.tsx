import { useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueries, useSuspenseQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ReportTools } from "@/components/app/report-tools";
import { DemoBadge, EmptyState, PageHeader, PageSkeleton } from "@/components/app/states";
import { compareReports } from "@/lib/fact-comparison";
import { defaultTrendSelection } from "@/lib/report-selection";
import { DEFAULT_DOCUMENT_ID, IS_DEMO, api, documentsQuery, trendsQuery } from "@/lib/api/service";

export const Route = createFileRoute("/trends")({
  validateSearch: (search: Record<string, unknown>) => {
    const doc = search["doc"];
    return { doc: typeof doc === "string" && doc.length > 0 ? doc : undefined };
  },
  loader: ({ context }) =>
    IS_DEMO
      ? context.queryClient.ensureQueryData(trendsQuery(DEFAULT_DOCUMENT_ID))
      : context.queryClient.ensureQueryData(documentsQuery()),
  head: () => ({
    meta: [
      { title: "Trends — FINAUDIT AI" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { property: "og:title", content: "Trends — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Compare reported financial values across processed reports.",
      },
      {
        name: "description",
        content: "Compare reported financial values across processed reports.",
      },
    ],
  }),
  pendingComponent: PageSkeleton,
  component: () => (IS_DEMO || !api.getFacts ? <DemoTrends /> : <LiveComparison />),
});

const demoConfig = {
  revenue: { label: "Revenue", color: "var(--chart-1)" },
  operatingIncome: { label: "Operating profit", color: "var(--chart-2)" },
  netIncome: { label: "Net profit", color: "var(--chart-3)" },
} satisfies ChartConfig;

function DemoTrends() {
  const { data } = useSuspenseQuery(trendsQuery(DEFAULT_DOCUMENT_ID));
  return (
    <div className="page-layout space-y-6">
      <PageHeader
        eyebrow="Analysis"
        title="Compare reports"
        description="Northwind Holdings (demo issuer) · five-year series, £ millions."
        actions={<DemoBadge />}
      />
      <ReportTools sample documentId={DEFAULT_DOCUMENT_ID ?? undefined} />
      <section className="rounded-md border bg-card p-5">
        <ChartContainer config={demoConfig} className="h-72 w-full">
          <BarChart data={data}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="period" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} width={44} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="revenue" fill="var(--color-revenue)" radius={1} />
            <Bar dataKey="operatingIncome" fill="var(--color-operatingIncome)" radius={1} />
            <Bar dataKey="netIncome" fill="var(--color-netIncome)" radius={1} />
          </BarChart>
        </ChartContainer>
      </section>
    </div>
  );
}

const liveConfig = {
  value: { label: "Reported value", color: "var(--chart-1)" },
} satisfies ChartConfig;

function formatReported(value: number) {
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(value);
}

function LiveComparison() {
  const navigate = useNavigate();
  const { doc: requestedId } = Route.useSearch();
  const documents = useSuspenseQuery(documentsQuery());
  const ready = documents.data.filter((doc) => doc.status === "ready");
  const [selected, setSelected] = useState(() => defaultTrendSelection(ready, requestedId));
  const appliedRequest = useRef(requestedId);
  useEffect(() => {
    if (appliedRequest.current === requestedId) return;
    appliedRequest.current = requestedId;
    setSelected(defaultTrendSelection(ready, requestedId));
  }, [ready, requestedId]);
  const [metric, setMetric] = useState("Revenue");
  const [query, setQuery] = useState("");
  const visible = useMemo(
    () => ready.filter((doc) => doc.title.toLowerCase().includes(query.trim().toLowerCase())),
    [ready, query],
  );
  const factQueries = useQueries({
    queries: selected.map((id) => ({
      queryKey: ["facts", id],
      queryFn: () => api.getFacts!(id),
    })),
  });
  const labels = [
    ...new Set(
      factQueries.flatMap((query) =>
        (query.data ?? [])
          .filter((fact) => fact.valueStatus === "parsed")
          .map((fact) => fact.rowLabel),
      ),
    ),
  ].sort();
  const activeMetric = labels.includes(metric) ? metric : (labels[0] ?? "");
  const comparison = compareReports(
    selected.map((id, index) => ({
      documentId: id,
      title: ready.find((doc) => doc.id === id)?.title ?? id,
      facts: factQueries[index]?.data ?? [],
    })),
    activeMetric,
  );
  const factsLoading = factQueries.some((query) => query.isPending);
  const reportCount = new Set(comparison.points.map((point) => point.documentId)).size;
  const chartData = comparison.points.map((point) => ({
    ...point,
    axis: point.periodLabel,
  }));

  return (
    <div className="page-layout space-y-6">
      <PageHeader
        eyebrow="Analysis"
        title="Compare reports"
        description="Compare one reported metric across processed reports. Values come only from parsed table facts."
      />
      <ReportTools documentId={requestedId ?? selected[0]} />
      <div className="grid gap-6 lg:grid-cols-[minmax(16rem,22rem)_minmax(0,1fr)]">
        <section className="space-y-3">
          <label className="block text-sm">
            <span className="text-xs text-muted-foreground">Find a report</span>
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="mt-1 h-9 w-full rounded-md border bg-card px-3"
              placeholder="Search titles"
            />
          </label>
          <fieldset className="max-h-72 space-y-1 overflow-auto pr-1">
            <legend className="mb-2 text-sm font-medium">
              Reports · {selected.length} selected
            </legend>
            {visible.map((doc) => (
              <label
                key={doc.id}
                className="flex items-start gap-2 rounded-sm px-1 py-1.5 text-sm hover:bg-muted/60"
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={selected.includes(doc.id)}
                  onChange={() =>
                    setSelected((current) =>
                      current.includes(doc.id)
                        ? current.filter((id) => id !== doc.id)
                        : [...current, doc.id],
                    )
                  }
                />
                <span>
                  <span className="block leading-snug">{doc.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {[doc.issuer, doc.period].filter(Boolean).join(" · ")}
                  </span>
                </span>
              </label>
            ))}
            {visible.length === 0 && (
              <p className="text-sm text-muted-foreground">No report title matches that search.</p>
            )}
          </fieldset>
        </section>
        <div className="min-w-0 space-y-4">
          <label className="block max-w-sm space-y-2 text-sm font-medium">
            <span>Financial metric</span>
            <select
              className="h-10 w-full rounded-md border border-input bg-card px-3 font-normal"
              value={activeMetric}
              disabled={labels.length === 0}
              onChange={(event) => setMetric(event.target.value)}
            >
              {labels.length === 0 && <option value="">No reported metrics</option>}
              {labels.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {selected.length < 2 && (
            <EmptyState
              title="Two reports are required"
              description="A single report is not shown as a trend."
            />
          )}
          {selected.length >= 2 && factsLoading && (
            <p className="text-sm text-muted-foreground">Loading reported values…</p>
          )}
          {selected.length >= 2 && !factsLoading && reportCount < 2 && (
            <EmptyState
              title="No aligned values"
              description={
                comparison.note ||
                "The metric is not present in two reports with the same unit, currency, and scope."
              }
            />
          )}
          {selected.length >= 2 && !factsLoading && reportCount >= 2 && (
            <section className="min-w-0 space-y-4 overflow-hidden rounded-md border bg-card p-5">
              <p className="eyebrow">
                {new Set(comparison.points.map((point) => point.periodLabel)).size >= 3
                  ? "Source-grounded series from parsed reports"
                  : "Comparison, not a comprehensive trend"}
              </p>
              <p className="text-sm text-muted-foreground">{comparison.note}</p>
              <ChartContainer config={liveConfig} className="aspect-auto h-72 w-full min-w-0">
                <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="axis" tickLine={false} axisLine={false} interval={0} />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    width={56}
                    tickFormatter={(value) => formatReported(Number(value))}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="value" fill="var(--color-value)" radius={1} maxBarSize={72} />
                </BarChart>
              </ChartContainer>
              <ul className="divide-y text-sm">
                {comparison.points.map((point) => (
                  <li
                    key={point.factId}
                    className="flex min-w-0 flex-col gap-2 py-2 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <span className="min-w-0">
                      <span className="font-mono tabular">{point.periodLabel}</span>
                      <span className="text-muted-foreground">
                        {" "}
                        · {formatReported(point.value)} {point.currency ?? ""} {point.scale}
                      </span>
                    </span>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-auto max-w-full whitespace-normal text-left"
                      onClick={() =>
                        navigate({
                          to: "/intelligence",
                          search: {
                            doc: point.documentId,
                            page: point.page,
                            ev: point.tableEvidenceId,
                          },
                        })
                      }
                    >
                      {point.documentTitle} · p. {point.page}
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

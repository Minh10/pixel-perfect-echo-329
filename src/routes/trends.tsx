import { useState } from "react";
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
import { DemoBadge, EmptyState, PageHeader, PageSkeleton } from "@/components/app/states";
import { compareReports } from "@/lib/fact-comparison";
import { DEFAULT_DOCUMENT_ID, IS_DEMO, api, documentsQuery, trendsQuery } from "@/lib/api/service";

export const Route = createFileRoute("/trends")({
  loader: ({ context }) =>
    IS_DEMO
      ? context.queryClient.ensureQueryData(trendsQuery(DEFAULT_DOCUMENT_ID))
      : context.queryClient.ensureQueryData(documentsQuery()),
  head: () => ({
    meta: [
      { title: "Trends — FINAUDIT AI" },
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
        title="Trends"
        description="Northwind Holdings (demo issuer) · five-year series, £ millions."
        actions={<DemoBadge />}
      />
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

function LiveComparison() {
  const navigate = useNavigate();
  const documents = useSuspenseQuery(documentsQuery());
  const ready = documents.data.filter((doc) => doc.status === "ready");
  const [selected, setSelected] = useState<string[]>([]);
  const [metric, setMetric] = useState("Revenue");
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
        title="Trends"
        description="Compare one reported metric across processed reports. Values come only from parsed table facts."
      />
      <fieldset className="space-y-2">
        <legend className="text-xs text-muted-foreground">
          Choose at least two processed reports.
        </legend>
        {ready.map((doc) => (
          <label key={doc.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.includes(doc.id)}
              onChange={() =>
                setSelected((current) =>
                  current.includes(doc.id)
                    ? current.filter((id) => id !== doc.id)
                    : [...current, doc.id],
                )
              }
            />
            {doc.title}
          </label>
        ))}
      </fieldset>
      <label className="block max-w-md text-sm">
        <span className="text-xs text-muted-foreground">Shared metric</span>
        <select
          className="mt-1 h-9 w-full rounded-md border bg-transparent px-3"
          value={activeMetric}
          onChange={(event) => setMetric(event.target.value)}
        >
          {labels.length === 0 && <option value="">Select reports to load metrics</option>}
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
        <section className="space-y-4 rounded-md border bg-card p-5">
          <p className="eyebrow">
            {new Set(comparison.points.map((point) => point.periodLabel)).size >= 3
              ? "Source-grounded series from parsed reports"
              : "Comparison, not a comprehensive trend"}
          </p>
          <p className="text-sm text-muted-foreground">{comparison.note}</p>
          <ChartContainer config={liveConfig} className="h-72 w-full">
            <BarChart data={chartData}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="axis" tickLine={false} axisLine={false} interval={0} />
              <YAxis tickLine={false} axisLine={false} width={48} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="value" fill="var(--color-value)" radius={1} />
            </BarChart>
          </ChartContainer>
          <ul className="space-y-2 text-sm">
            {comparison.points.map((point) => (
              <li key={point.factId}>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
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
                  {point.documentTitle} · {point.periodLabel} · {point.displayValue}{" "}
                  {point.currency ?? ""} {point.scale} · p. {point.page}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

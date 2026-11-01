import { createFileRoute } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { DEFAULT_DOCUMENT_ID, trendsQuery } from "@/lib/api/service";
import { DemoBadge, PageHeader, PageSkeleton } from "@/components/app/states";

export const Route = createFileRoute("/trends")({
  loader: ({ context }) => context.queryClient.ensureQueryData(trendsQuery(DEFAULT_DOCUMENT_ID)),
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Trends — FINAUDIT AI" },
      { name: "description", content: "Multi-period revenue and profitability trends from parsed reports." },
      { property: "og:title", content: "Trends — FINAUDIT AI" },
      { property: "og:description", content: "Multi-period revenue and profitability trends from parsed reports." },
    ],
  }),
  pendingComponent: PageSkeleton,
  component: Trends,
});

const config = {
  revenue: { label: "Revenue", color: "var(--chart-1)" },
  operatingIncome: { label: "Operating profit", color: "var(--chart-2)" },
  netIncome: { label: "Net profit", color: "var(--chart-3)" },
  margin: { label: "Operating margin", color: "var(--chart-2)" },
} satisfies ChartConfig;

function Trends() {
  const { data } = useSuspenseQuery(trendsQuery(DEFAULT_DOCUMENT_ID));
  const withMargin = data.map((d) => ({ ...d, margin: +((d.operatingIncome / d.revenue) * 100).toFixed(1) }));

  return (
    <div className="page-layout space-y-6">
      <PageHeader eyebrow="Analysis" title="Trends" description="Northwind Holdings (demo issuer) · five-year series, £ millions." actions={<DemoBadge />} />
      <div className="grid gap-4 lg:grid-cols-5">
        <section className="rounded-md border bg-card p-5 lg:col-span-3">
          <p className="eyebrow mb-4">Revenue and profit</p>
          <ChartContainer config={config} className="h-72 w-full">
            <BarChart data={data} barGap={2}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="period" tickLine={false} axisLine={false} className="font-mono" />
              <YAxis tickLine={false} axisLine={false} width={44} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="revenue" fill="var(--color-revenue)" radius={1} />
              <Bar dataKey="operatingIncome" fill="var(--color-operatingIncome)" radius={1} />
              <Bar dataKey="netIncome" fill="var(--color-netIncome)" radius={1} />
            </BarChart>
          </ChartContainer>
        </section>
        <section className="rounded-md border bg-card p-5 lg:col-span-2">
          <p className="eyebrow mb-4">Operating margin (%)</p>
          <ChartContainer config={config} className="h-72 w-full">
            <LineChart data={withMargin}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="period" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} width={32} domain={["dataMin - 1", "dataMax + 1"]} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Line dataKey="margin" stroke="var(--color-margin)" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ChartContainer>
        </section>
      </div>
      <div className="overflow-x-auto rounded-md border bg-card">
        <table className="w-full text-sm tabular">
          <thead className="bg-muted/50">
            <tr><th className="eyebrow p-3 text-left">£m</th>{data.map((d) => <th key={d.period} className="eyebrow p-3 text-right">{d.period}</th>)}</tr>
          </thead>
          <tbody>
            {(["revenue", "operatingIncome", "netIncome"] as const).map((k) => (
              <tr key={k} className="border-t">
                <td className="p-3">{config[k].label}</td>
                {data.map((d) => <td key={d.period} className="p-3 text-right font-mono">{d[k].toLocaleString()}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

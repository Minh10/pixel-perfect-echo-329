import { Link } from "@tanstack/react-router";
import {
  ArrowUpRight,
  FileText,
  ScanLine,
  Table2,
  ShieldCheck,
  TrendingUp,
  CircleAlert,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { libraryTrend, type LibraryIntelligence } from "@/lib/library-intelligence";
import type { FinDocument } from "@/lib/api/types";

export function OverviewMetrics({
  documents,
  intelligence,
  pending,
}: {
  documents: FinDocument[];
  intelligence?: LibraryIntelligence | undefined;
  pending: boolean;
}) {
  const partial = intelligence?.unavailable;
  const stats = [
    {
      label: "Processed reports",
      value: documents.filter((doc) => doc.status === "ready").length,
      icon: FileText,
      detail: "Ready to inspect",
    },
    {
      label: "Financial facts",
      value: intelligence?.facts.filter((fact) => fact.valueStatus === "parsed").length,
      icon: Table2,
      detail: partial?.has("facts") ? "Unavailable or incomplete" : "Parsed table values",
      unavailable: partial?.has("facts"),
    },
    {
      label: "Charts interpreted",
      value: intelligence?.readings.length,
      icon: ScanLine,
      detail: partial?.has("readings") ? "Unavailable or incomplete" : "Saved model readings",
      unavailable: partial?.has("readings"),
    },
    {
      label: "Potential discrepancies",
      value: intelligence?.readings.reduce(
        (sum, reading) =>
          sum + reading.tableChecks.filter((check) => check.status === "conflict").length,
        0,
      ),
      icon: ShieldCheck,
      detail: partial?.has("readings")
        ? "Unavailable or incomplete"
        : "Flagged points, not verified errors",
      unavailable: partial?.has("readings"),
    },
  ];
  return (
    <dl className="grid grid-cols-2 border-y bg-card lg:grid-cols-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="metric-surface min-w-0 border-b p-4 odd:border-r lg:border-b-0 lg:border-r lg:last:border-r-0 sm:p-5"
        >
          <dt className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
            {stat.label}
            <stat.icon className="size-4 shrink-0" />
          </dt>
          <dd className="mt-3 font-mono text-3xl font-medium tabular">
            {stat.unavailable
              ? "—"
              : stat.value === undefined
                ? pending
                  ? "…"
                  : "—"
                : stat.value.toLocaleString()}
          </dd>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{stat.detail}</p>
        </div>
      ))}
    </dl>
  );
}

export function OverviewPanels({
  intelligence,
  pending,
  error,
}: {
  intelligence?: LibraryIntelligence | undefined;
  pending: boolean;
  error: boolean;
}) {
  const trend = intelligence ? libraryTrend(intelligence) : null;
  const flags =
    intelligence?.readings.flatMap((reading) =>
      reading.tableChecks
        .filter((check) => check.status === "conflict")
        .map((check) => ({ reading, check })),
    ) ?? [];
  const ready = intelligence?.reports[0];
  const unRead = intelligence?.evidence.find(
    (item) =>
      item.provenance &&
      item.category === "figure" &&
      !intelligence.readings.some(
        (reading) =>
          reading.blockId === item.blockId && reading.documentId === item.provenance?.documentId,
      ),
  );
  return (
    <div className="grid gap-7 xl:grid-cols-2">
      <section className="min-w-0" aria-label="Priority insights">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold">Review priorities</h2>
          <span className="eyebrow">SOURCE-LINKED</span>
        </div>
        {pending && !intelligence ? (
          <p role="status" className="py-5 text-sm text-muted-foreground">
            Loading extracted evidence…
          </p>
        ) : error ? (
          <p className="py-5 text-sm text-muted-foreground">
            Library intelligence unavailable. Reports remain accessible below.
          </p>
        ) : (
          <div className="divide-y border-y">
            {flags.slice(0, 2).map(({ reading, check }, index) => (
              <Button
                key={`${reading.blockId}-${index}`}
                asChild
                variant="ghost"
                className="h-auto w-full justify-start whitespace-normal rounded-none px-0 py-4 text-left"
              >
                <Link
                  to="/intelligence"
                  search={{
                    doc: reading.documentId,
                    tool: "charts",
                    page: check.page ?? undefined,
                  }}
                >
                  <CircleAlert className="size-4 shrink-0 text-warning" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">
                      {check.label}: potential chart–table difference
                    </span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      Chart estimate {check.estimate} · reported {check.tableValue ?? "not stated"}{" "}
                      · requires review
                    </span>
                  </span>
                  <ArrowUpRight className="size-4 shrink-0" />
                </Link>
              </Button>
            ))}
            {unRead && (
              <Button
                asChild
                variant="ghost"
                className="h-auto w-full justify-start whitespace-normal rounded-none px-0 py-4 text-left"
              >
                <Link
                  to="/intelligence"
                  search={{
                    doc: unRead.provenance?.documentId,
                    page: unRead.page,
                    ev: unRead.id,
                    tool: "evidence",
                  }}
                >
                  <ScanLine className="size-4 shrink-0 text-primary" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">{unRead.label}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      Page {unRead.page} · no saved chart reading in this preview
                    </span>
                  </span>
                  <ArrowUpRight className="size-4 shrink-0" />
                </Link>
              </Button>
            )}
            {ready && (
              <Button
                asChild
                variant="ghost"
                className="h-auto w-full justify-start whitespace-normal rounded-none px-0 py-4 text-left"
              >
                <Link to="/intelligence" search={{ doc: ready.id }}>
                  <FileText className="size-4 shrink-0 text-primary" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">{ready.title}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {ready.pages} pages · ready for evidence inspection
                    </span>
                  </span>
                  <ArrowUpRight className="size-4 shrink-0" />
                </Link>
              </Button>
            )}
            {!ready && (
              <p className="py-5 text-sm text-muted-foreground">
                No processed report available yet.
              </p>
            )}
          </div>
        )}
        <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
          {intelligence?.sample
            ? "DEMO · Synthetic evidence is illustrative, not verified financial findings."
            : `Read-only preview of up to six recent ready reports and eight stored chart readings. No new AI analysis is generated.`}
        </p>
      </section>
      <section className="min-w-0" aria-label="Financial trend preview">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold">Reported trends</h2>
          <TrendingUp className="size-4 text-muted-foreground" />
        </div>
        {trend ? (
          <>
            <p className="text-sm font-medium">
              {trend.issuer} · {trend.metric}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {trend.points[0]?.currency} · {trend.points[0]?.scale} · {trend.points[0]?.scope}
            </p>
            <ChartContainer
              config={{ value: { label: "Reported value", color: "var(--chart-1)" } }}
              className="mt-4 h-40 w-full"
            >
              <BarChart accessibilityLayer data={trend.points}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="periodLabel" axisLine={false} tickLine={false} />
                <YAxis width={48} axisLine={false} tickLine={false} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="value" fill="var(--color-value)" radius={2} />
              </BarChart>
            </ChartContainer>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
              {trend.points.map((point) => (
                <Button
                  key={point.factId}
                  asChild
                  variant="link"
                  size="sm"
                  className="h-auto px-0 text-xs"
                >
                  <Link
                    to="/intelligence"
                    search={{
                      doc: point.documentId,
                      page: point.page,
                      ev: point.tableEvidenceId,
                      tool: "evidence",
                    }}
                  >
                    {point.periodLabel}: {point.displayValue} · p.{point.page}
                    <ArrowUpRight className="size-3" />
                  </Link>
                </Button>
              ))}
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">{trend.note}</p>
          </>
        ) : (
          <div className="border-y py-6">
            <p className="text-sm font-medium">Comparable evidence comes first</p>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
              {pending
                ? "Checking available reporting periods…"
                : "Select two comparable financial reports to explore their reported trends."}
            </p>
            <Button asChild variant="link" className="mt-3 h-auto px-0 text-sm">
              <Link to="/intelligence" search={{ doc: ready?.id, tool: "compare" }}>
                Compare reports <ArrowUpRight className="size-3.5" />
              </Link>
            </Button>
            <p className="mt-3 text-[11px] text-muted-foreground">
              Issuer, metric, reporting period, currency, scale and scope must align.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

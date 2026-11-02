import { Link } from "@tanstack/react-router";
import {
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  Clock3,
  FileText,
  Layers,
  ScanSearch,
} from "lucide-react";
import type { FinDocument, Evidence } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { IS_DEMO } from "@/lib/api/service";
import { DemoBadge } from "./states";
import { NAV_ITEMS } from "./nav";

export function OverviewMetrics({
  documents,
  evidence,
}: {
  documents: FinDocument[];
  evidence: Evidence[];
}) {
  const ready = documents.filter((d) => d.status === "ready");
  const stats = [
    {
      label: "Documents",
      value: documents.length,
      detail: "Reports in your library",
      icon: FileText,
    },
    {
      label: "Ready for Review",
      value: ready.length,
      detail: "Available for inspection",
      icon: CheckCircle2,
    },
    {
      label: "Pages Indexed",
      value: ready.reduce((sum, d) => sum + d.pages, 0),
      detail: "Across ready reports",
      icon: Layers,
    },
    {
      label: "Evidence Regions",
      value: evidence.length,
      detail: IS_DEMO ? "In the demo workspace report" : "Across ready reports",
      icon: ScanSearch,
    },
    {
      label: "Tables",
      value: evidence.filter((item) => item.category === "table").length,
      detail: "Extracted table regions",
      icon: Layers,
    },
    {
      label: "Figures",
      value: evidence.filter((item) => item.category === "figure" || item.category === "chart")
        .length,
      detail: "Extracted chart regions",
      icon: ScanSearch,
    },
  ];
  return (
    <dl className="grid gap-px overflow-hidden rounded-md border bg-border sm:grid-cols-2 xl:grid-cols-3">
      {stats.map((s) => (
        <div key={s.label} className="flex min-h-36 min-w-0 flex-col bg-card p-5">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
            <dt className="text-sm font-medium text-muted-foreground">{s.label}</dt>
            <s.icon className="size-5 shrink-0 text-primary" strokeWidth={1.5} />
          </div>
          <dd className="mt-4 text-[2.5rem] font-semibold leading-none tabular">
            {s.value.toLocaleString()}
          </dd>
          <div className="mt-auto flex items-center justify-between gap-2 pt-4">
            <p className="text-xs text-muted-foreground">{s.detail}</p>
            {IS_DEMO && <DemoBadge />}
          </div>
        </div>
      ))}
    </dl>
  );
}

export function OverviewPanels({ documents }: { documents: FinDocument[] }) {
  const statuses = [
    {
      key: "ready",
      label: "Ready for review",
      icon: CheckCircle2,
      color: "bg-success",
      text: "text-success",
    },
    {
      key: "processing",
      label: "Processing",
      icon: Clock3,
      color: "bg-warning",
      text: "text-warning",
    },
    {
      key: "failed",
      label: "Failed",
      icon: CircleAlert,
      color: "bg-destructive",
      text: "text-destructive",
    },
  ].map((s) => ({ ...s, count: documents.filter((d) => d.status === s.key).length }));
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <section className="min-w-0 border-y py-5" aria-labelledby="processing-title">
        <div className="flex items-center justify-between gap-3">
          <h2 id="processing-title" className="text-base font-semibold">
            Document Processing
          </h2>
          {IS_DEMO && <DemoBadge />}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Current library status · {documents.length} reports
        </p>
        <div className="mt-6 flex h-2.5 overflow-hidden rounded-sm bg-muted" aria-hidden="true">
          {statuses.map((s) => (
            <span
              key={s.key}
              className={s.color}
              style={{ width: `${documents.length ? (s.count / documents.length) * 100 : 0}%` }}
            />
          ))}
        </div>
        <div className="mt-5 grid grid-cols-3 gap-3">
          {statuses.map((s) => (
            <div key={s.key} className="min-w-0">
              <s.icon className={`mb-2 size-4 ${s.text}`} />
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className="mt-1 text-2xl font-semibold tabular">{s.count}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="min-w-0 border-y py-5" aria-labelledby="actions-title">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 id="actions-title" className="text-base font-semibold">
            Quick Actions
          </h2>
          {IS_DEMO && <DemoBadge />}
        </div>
        <div className="grid gap-x-5 sm:grid-cols-2">
          {NAV_ITEMS.filter((n) =>
            ["/intelligence", "/documents", "/trends", "/audit"].includes(n.to),
          ).map((n) => (
            <Button
              key={n.to}
              asChild
              variant="ghost"
              className="h-auto min-h-16 justify-start rounded-none border-b px-0 py-3 hover:bg-transparent hover:text-primary"
            >
              <Link to={n.to}>
                <n.icon className="size-4 shrink-0 text-primary" />
                <span className="min-w-0 flex-1 whitespace-normal">
                  {n.title}
                  <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                    {n.to === "/audit"
                      ? IS_DEMO
                        ? "Available once a document service is connected"
                        : "Chart readings and table checks"
                      : n.to === "/trends"
                        ? IS_DEMO
                          ? "Sample financial series"
                          : "Parsed facts across reports"
                        : n.to === "/documents"
                          ? IS_DEMO
                            ? "Sample report library"
                            : "Drop a PDF to process"
                          : "Inspect report evidence"}
                  </span>
                </span>
                <ArrowUpRight className="shrink-0 text-muted-foreground" />
              </Link>
            </Button>
          ))}
        </div>
      </section>
    </div>
  );
}

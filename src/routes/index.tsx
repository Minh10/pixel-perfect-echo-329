import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { documentsQuery, evidenceQuery, DEFAULT_DOCUMENT_ID } from "@/lib/api/service";
import { DemoBadge, PageHeader, PageSkeleton } from "@/components/app/states";
import { DocumentsTable } from "@/components/app/documents-table";

export const Route = createFileRoute("/")({
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(documentsQuery()),
      context.queryClient.ensureQueryData(evidenceQuery(DEFAULT_DOCUMENT_ID)),
    ]),
  head: () => ({
    meta: [
      { title: "Overview — FINAUDIT AI" },
      { name: "description", content: "Workspace overview of financial documents, evidence and audit readiness." },
      { property: "og:title", content: "Overview — FINAUDIT AI" },
      { property: "og:description", content: "Workspace overview of financial documents, evidence and audit readiness." },
    ],
  }),
  pendingComponent: PageSkeleton,
  component: Overview,
});

function Overview() {
  const { data: docs } = useSuspenseQuery(documentsQuery());
  const { data: evidence } = useSuspenseQuery(evidenceQuery(DEFAULT_DOCUMENT_ID));
  const stats = [
    { label: "Documents", value: docs.length },
    { label: "Ready for review", value: docs.filter((d) => d.status === "ready").length },
    { label: "Pages indexed", value: docs.filter((d) => d.status === "ready").reduce((a, d) => a + d.pages, 0) },
    { label: "Evidence regions", value: evidence.length },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-8 p-6 md:p-8">
      <PageHeader
        eyebrow="Workspace"
        title="Overview"
        description="Financial reports under review, parsed into text, tables and charts with traceable evidence."
        actions={<Button asChild><Link to="/intelligence">Open workspace <ArrowRight /></Link></Button>}
      />
      <dl className="grid grid-cols-2 divide-x divide-y rounded-md border bg-card md:grid-cols-4 md:divide-y-0">
        {stats.map((s) => (
          <div key={s.label} className="p-5">
            <dt className="eyebrow">{s.label}</dt>
            <dd className="mt-2 font-serif text-3xl font-semibold tabular">{s.value}</dd>
          </div>
        ))}
      </dl>
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Recent documents</h2>
          <DemoBadge />
        </div>
        <DocumentsTable documents={docs} />
      </section>
    </div>
  );
}

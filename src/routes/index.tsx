import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { documentsQuery, evidenceQuery, DEFAULT_DOCUMENT_ID } from "@/lib/api/service";
import { DemoBadge, PageHeader, PageSkeleton } from "@/components/app/states";
import { DocumentsTable } from "@/components/app/documents-table";
import { OverviewMetrics, OverviewPanels } from "@/components/app/overview-panels";

export const Route = createFileRoute("/")({
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(documentsQuery()),
      context.queryClient.ensureQueryData(evidenceQuery(DEFAULT_DOCUMENT_ID)),
    ]),
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
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

  return (
    <div className="page-layout space-y-7">
      <PageHeader
        title="Overview"
        description="Your financial report library, processing status and source evidence — in one workspace."
        actions={<><Button asChild variant="ghost"><Link to="/documents">View Documents</Link></Button><Button asChild className="h-10"><Link to="/intelligence">Open Document Workspace <ArrowRight /></Link></Button></>}
      />
      <OverviewMetrics documents={docs} evidence={evidence} />
      <OverviewPanels documents={docs} />
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div><h2 className="text-base font-semibold">Recent Documents</h2><p className="mt-1 text-sm text-muted-foreground">Financial reports in your library</p></div>
          <div className="flex items-center gap-3"><DemoBadge /><Button asChild variant="link" size="sm"><Link to="/documents">View all <ArrowRight /></Link></Button></div>
        </div>
        <DocumentsTable documents={docs} />
      </section>
    </div>
  );
}

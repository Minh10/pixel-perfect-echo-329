import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useSuspenseQueries, useSuspenseQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/http-service";
import { documentsQuery, evidenceQuery, DEFAULT_DOCUMENT_ID, IS_DEMO } from "@/lib/api/service";
import type { Evidence } from "@/lib/api/types";
import { DemoBadge, ErrorState, PageHeader, PageSkeleton } from "@/components/app/states";
import { DocumentsTable } from "@/components/app/documents-table";
import { OverviewMetrics, OverviewPanels } from "@/components/app/overview-panels";

export const Route = createFileRoute("/")({
  loader: async ({ context }) => {
    const docs = await context.queryClient.ensureQueryData(documentsQuery());
    const ids =
      IS_DEMO && DEFAULT_DOCUMENT_ID
        ? [DEFAULT_DOCUMENT_ID]
        : docs.filter((doc) => doc.status === "ready").map((doc) => doc.id);
    await Promise.all(ids.map((id) => context.queryClient.ensureQueryData(evidenceQuery(id))));
  },
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Overview — FINAUDIT AI" },
      {
        name: "description",
        content: "Workspace overview of financial documents, evidence and audit readiness.",
      },
      { property: "og:title", content: "Overview — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Workspace overview of financial documents, evidence and audit readiness.",
      },
    ],
  }),
  pendingComponent: PageSkeleton,
  errorComponent: function OverviewError({ error }) {
    const router = useRouter();
    const unavailable =
      error instanceof ApiError &&
      (error.code === "backend_unavailable" || error.code === "timeout");
    return (
      <div className="p-8">
        <ErrorState
          title={unavailable ? "Document service unavailable" : "Couldn't load the overview"}
          message={error instanceof Error ? error.message : String(error)}
          onRetry={() => router.invalidate()}
        />
      </div>
    );
  },
  component: Overview,
});

function Overview() {
  const { data: docs } = useSuspenseQuery(documentsQuery());
  const evidenceIds =
    IS_DEMO && DEFAULT_DOCUMENT_ID
      ? [DEFAULT_DOCUMENT_ID]
      : docs.filter((doc) => doc.status === "ready").map((doc) => doc.id);
  const evidenceResults = useSuspenseQueries({
    queries:
      evidenceIds.length > 0
        ? evidenceIds.map((id) => evidenceQuery(id))
        : [
            {
              queryKey: ["evidence", "none"],
              queryFn: async () => [] as Evidence[],
            },
          ],
  });
  const evidence = evidenceResults.flatMap((result) => result.data);

  return (
    <div className="page-layout space-y-7">
      <PageHeader
        title="Overview"
        description="Your financial report library, processing status and source evidence — in one workspace."
        actions={
          <>
            <Button asChild variant="ghost">
              <Link to="/documents">View Documents</Link>
            </Button>
            <Button asChild className="h-10">
              <Link to="/intelligence">
                Open Document Workspace <ArrowRight />
              </Link>
            </Button>
          </>
        }
      />
      <OverviewMetrics documents={docs} evidence={evidence} />
      <OverviewPanels documents={docs} />
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">Recent Documents</h2>
            <p className="mt-1 text-sm text-muted-foreground">Financial reports in your library</p>
          </div>
          <div className="flex items-center gap-3">
            {IS_DEMO && <DemoBadge />}
            <Button asChild variant="link" size="sm">
              <Link to="/documents">
                View all <ArrowRight />
              </Link>
            </Button>
          </div>
        </div>
        <DocumentsTable documents={docs} />
      </section>
    </div>
  );
}

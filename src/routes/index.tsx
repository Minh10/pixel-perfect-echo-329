import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useQueries, useSuspenseQueries, useSuspenseQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/http-service";
import {
  api,
  documentsQuery,
  evidenceQuery,
  DEFAULT_DOCUMENT_ID,
  IS_DEMO,
} from "@/lib/api/service";
import type { Evidence } from "@/lib/api/types";
import { PdfIntake } from "@/components/app/pdf-intake";
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
  const latest = docs.find((doc) => doc.status === "ready");

  return (
    <div className="page-layout space-y-7">
      <PageHeader
        title="Overview"
        description={
          IS_DEMO
            ? "A sample financial library. Open the sample report to inspect pages, tables and charts."
            : "Drop a PDF to process it. Pages, tables, charts, discrepancies and trends follow from that report."
        }
        actions={
          !IS_DEMO && latest ? (
            <Button asChild variant="outline">
              <Link to="/intelligence" search={{ doc: latest.id }}>
                Continue latest report
              </Link>
            </Button>
          ) : null
        }
      />
      <PdfIntake />
      <details className="border-b pb-4">
        <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
          Library statistics · {docs.length} reports
        </summary>
        <div className="mt-4">
          <OverviewMetrics documents={docs} evidence={evidence} />
          {!IS_DEMO && api.getFigureInterpretation && (
            <StoredAnalyses
              figures={evidenceIds.flatMap((documentId, index) =>
                (evidenceResults[index]?.data ?? [])
                  .filter((item) => item.category === "figure")
                  .map((item) => ({ documentId, blockId: item.blockId })),
              )}
            />
          )}
          <OverviewPanels documents={docs} />
        </div>
      </details>
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

function StoredAnalyses({ figures }: { figures: { documentId: string; blockId: string }[] }) {
  const readings = useQueries({
    queries: figures.map((figure) => ({
      queryKey: ["interpretation", figure.documentId, figure.blockId],
      queryFn: () => api.getFigureInterpretation!(figure.documentId, figure.blockId),
      retry: false,
    })),
  });
  const pending = readings.some((query) => query.isPending);
  const stored = readings.flatMap((query) => (query.data ? [query.data] : []));
  const discrepancies = stored.reduce(
    (count, reading) =>
      count + reading.tableChecks.filter((check) => check.status === "conflict").length,
    0,
  );
  return (
    <section className="grid gap-px overflow-hidden rounded-md border bg-border sm:grid-cols-2">
      <div className="bg-card p-5">
        <p className="text-xs text-muted-foreground">Stored chart readings</p>
        <p className="mt-2 font-serif text-3xl tabular">{pending ? "…" : stored.length}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          Figures with a saved model reading. Unread figures are not counted.
        </p>
      </div>
      <div className="bg-card p-5">
        <p className="text-xs text-muted-foreground">Potential discrepancies</p>
        <p className="mt-2 font-serif text-3xl tabular">{pending ? "…" : discrepancies}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          Stored chart points that differ from one aligned reported fact. Not a verified finding.
        </p>
      </div>
    </section>
  );
}

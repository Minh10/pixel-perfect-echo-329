import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/http-service";
import { api, documentsQuery, DEFAULT_DOCUMENT_ID, IS_DEMO } from "@/lib/api/service";
import { DemoBadge, ErrorState, PageSkeleton } from "@/components/app/states";
import { DocumentsTable } from "@/components/app/documents-table";
import { OverviewMetrics, OverviewPanels } from "@/components/app/overview-panels";
import { loadLibraryIntelligence, recentReports } from "@/lib/library-intelligence";

export const Route = createFileRoute("/")({
  loader: ({ context }) => context.queryClient.ensureQueryData(documentsQuery()),
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
  const latest = recentReports(docs).find((doc) => doc.status === "ready");
  const intelligence = useQuery({
    queryKey: [
      "library-intelligence",
      IS_DEMO ? "sample" : "live",
      docs
        .filter((doc) => doc.status === "ready")
        .map((doc) => doc.id)
        .join(","),
    ],
    queryFn: () => loadLibraryIntelligence(api, docs, IS_DEMO, DEFAULT_DOCUMENT_ID),
    staleTime: 300_000,
    retry: false,
  });
  return (
    <div className="page-layout space-y-7">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow mb-2">FINANCIAL DOCUMENT INTELLIGENCE</p>
          <h1 className="text-3xl font-semibold">
            FINAUDIT <span className="text-primary">AI</span>
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
            Understand financial reports, verify visual evidence, and discover source-grounded
            trends.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {latest && (
            <Button asChild variant="outline">
              <Link to="/intelligence" search={{ doc: latest.id }}>
                Open report <ArrowRight className="size-4" />
              </Link>
            </Button>
          )}
          <Button asChild>
            <Link to="/documents">{IS_DEMO ? "Document library" : "Upload PDF"}</Link>
          </Button>
        </div>
      </header>
      <OverviewMetrics
        documents={docs}
        intelligence={intelligence.data}
        pending={intelligence.isPending}
      />
      <OverviewPanels
        intelligence={intelligence.data}
        pending={intelligence.isPending}
        error={intelligence.isError}
      />
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold">
            Recent reports{" "}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {docs.length} in library
            </span>
          </h2>
          <div className="flex items-center gap-3">
            {IS_DEMO && <DemoBadge />}
            <Button asChild variant="link" size="sm">
              <Link to="/documents">
                View all <ArrowRight />
              </Link>
            </Button>
          </div>
        </div>
        <DocumentsTable documents={recentReports(docs).slice(0, 4)} />
      </section>
      <footer
        className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t pt-4 text-[11px] text-muted-foreground"
        aria-label="Processing architecture"
      >
        <span className="font-medium text-foreground">Evidence pipeline</span>
        {["PDF", "Layout detection", "Financial facts", "Evidence index", "AI analysis"].map(
          (stage, index) => (
            <span key={stage} className="inline-flex items-center gap-3">
              {index > 0 && <ArrowRight className="size-3" />}
              {stage}
            </span>
          ),
        )}
      </footer>
    </div>
  );
}

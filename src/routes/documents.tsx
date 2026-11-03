import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/http-service";
import { IS_DEMO, documentsQuery } from "@/lib/api/service";
import { PdfIntake } from "@/components/app/pdf-intake";
import { EmptyState, ErrorState, PageHeader, PageSkeleton } from "@/components/app/states";
import { DocumentsTable } from "@/components/app/documents-table";

export const Route = createFileRoute("/documents")({
  loader: ({ context }) => context.queryClient.ensureQueryData(documentsQuery()),
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Documents — FINAUDIT AI" },
      {
        name: "description",
        content: "Library of uploaded financial reports and their processing status.",
      },
      { property: "og:title", content: "Documents — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Library of uploaded financial reports and their processing status.",
      },
    ],
  }),
  pendingComponent: PageSkeleton,
  errorComponent: function DocumentsError({ error }) {
    const router = useRouter();
    const unavailable =
      error instanceof ApiError &&
      (error.code === "backend_unavailable" || error.code === "timeout");
    return (
      <div className="p-8">
        <ErrorState
          title={unavailable ? "Document service unavailable" : "Couldn't load documents"}
          message={error instanceof Error ? error.message : String(error)}
          onRetry={() => router.invalidate()}
        />
      </div>
    );
  },
  component: Documents,
});

function Documents() {
  const { data } = useSuspenseQuery(documentsQuery());
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");

  const filtered = data.filter(
    (d) =>
      (status === "all" || d.status === status) &&
      `${d.title} ${d.issuer ?? ""} ${d.period ?? ""}`.toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <div className="page-layout space-y-6">
      <PageHeader
        eyebrow="Library"
        title="Documents"
        description={
          IS_DEMO
            ? "Sample annual reports, interims and prospectuses."
            : "Financial reports and processing activity."
        }
      />
      <PdfIntake />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={status} onValueChange={setStatus}>
          <TabsList aria-label="Document status">
            {[
              ["all", "All"],
              ["ready", "Ready"],
              ["processing", "Processing"],
              ["failed", "Failed"],
            ].map(([value, label]) => (
              <TabsTrigger key={value} value={value}>
                {label}{" "}
                <span className="ml-1 text-xs text-muted-foreground">
                  {value === "all"
                    ? data.length
                    : data.filter((doc) => doc.status === value).length}
                </span>
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="Filter documents"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by title, issuer or period"
            className="pl-8"
          />
        </div>
      </div>
      {data.length === 0 ? (
        <EmptyState
          title="No documents yet"
          description={
            IS_DEMO
              ? "The sample library is empty."
              : "Drop a financial PDF above to process its pages, tables, figures and evidence."
          }
        />
      ) : filtered.length ? (
        <DocumentsTable documents={filtered} />
      ) : (
        <EmptyState
          title="No matching documents"
          description="Try a different issuer name or reporting period."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setQ("");
                setStatus("all");
              }}
            >
              Clear filter
            </Button>
          }
        />
      )}
    </div>
  );
}

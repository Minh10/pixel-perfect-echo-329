import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Search, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { documentsQuery } from "@/lib/api/service";
import { EmptyState, PageHeader, PageSkeleton } from "@/components/app/states";
import { DocumentsTable } from "@/components/app/documents-table";

export const Route = createFileRoute("/documents")({
  loader: ({ context }) => context.queryClient.ensureQueryData(documentsQuery()),
  head: () => ({
    meta: [
      { title: "Documents — FINAUDIT AI" },
      { name: "description", content: "Library of uploaded financial reports and their processing status." },
      { property: "og:title", content: "Documents — FINAUDIT AI" },
      { property: "og:description", content: "Library of uploaded financial reports and their processing status." },
    ],
  }),
  pendingComponent: PageSkeleton,
  component: Documents,
});

function Documents() {
  const { data } = useSuspenseQuery(documentsQuery());
  const [q, setQ] = useState("");
  const filtered = data.filter((d) => `${d.title} ${d.issuer} ${d.period}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 md:p-8">
      <PageHeader
        eyebrow="Library"
        title="Documents"
        description="Annual reports, interims and prospectuses available for analysis."
        actions={<Button disabled title="Upload requires the backend API"><Upload /> Upload report</Button>}
      />
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by title, issuer or period" className="pl-8" />
      </div>
      {filtered.length ? (
        <DocumentsTable documents={filtered} />
      ) : (
        <EmptyState title="No matching documents" description="Try a different issuer name or reporting period." action={<Button variant="outline" size="sm" onClick={() => setQ("")}>Clear filter</Button>} />
      )}
    </div>
  );
}

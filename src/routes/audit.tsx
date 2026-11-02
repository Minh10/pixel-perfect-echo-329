import { createFileRoute } from "@tanstack/react-router";
import { ChartChecksPanel } from "@/components/workspace/audit-panel";

export const Route = createFileRoute("/audit")({
  validateSearch: (search: Record<string, unknown>) => {
    const doc = search["doc"];
    return { doc: typeof doc === "string" && doc.length > 0 ? doc : undefined };
  },
  head: () => ({
    meta: [
      { title: "Check charts — FINAUDIT AI" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { property: "og:title", content: "Check charts — FINAUDIT AI" },
      {
        property: "og:description",
        content:
          "Inspect chart crops and compare them with reported table facts when a reading exists.",
      },
      {
        name: "description",
        content:
          "Inspect chart crops and compare them with reported table facts when a reading exists.",
      },
    ],
  }),
  component: AuditPage,
});

function AuditPage() { const { doc } = Route.useSearch(); return <ChartChecksPanel documentId={doc} />; }

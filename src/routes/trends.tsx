import { createFileRoute } from "@tanstack/react-router";
import { IS_DEMO, DEFAULT_DOCUMENT_ID, documentsQuery, trendsQuery } from "@/lib/api/service";
import { PageSkeleton } from "@/components/app/states";
import { ComparisonPanel } from "@/components/workspace/trends-panel";

export const Route = createFileRoute("/trends")({
  validateSearch: (search: Record<string, unknown>) => {
    const doc = search["doc"];
    return { doc: typeof doc === "string" && doc.length > 0 ? doc : undefined };
  },
  loader: ({ context }) =>
    IS_DEMO
      ? context.queryClient.ensureQueryData(trendsQuery(DEFAULT_DOCUMENT_ID))
      : context.queryClient.ensureQueryData(documentsQuery()),
  head: () => ({
    meta: [
      { title: "Compare reports — FINAUDIT AI" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { property: "og:title", content: "Compare reports — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Compare reported financial values across processed reports.",
      },
      {
        name: "description",
        content: "Compare reported financial values across processed reports.",
      },
    ],
  }),
  pendingComponent: PageSkeleton,
  component: ComparisonPage,
});

function ComparisonPage() {
  const { doc } = Route.useSearch();
  return <ComparisonPanel documentId={doc} />;
}

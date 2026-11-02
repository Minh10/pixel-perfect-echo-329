import { createFileRoute } from "@tanstack/react-router";
import { AnalysisPanel } from "@/components/workspace/analysis-panel";

export const Route = createFileRoute("/analysis")({
  validateSearch: (search: Record<string, unknown>) => {
    const doc = search["doc"];
    return { doc: typeof doc === "string" && doc.length > 0 ? doc : undefined };
  },
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Ask a question — FINAUDIT AI" },
      {
        name: "description",
        content: "Evidence-grounded questions and answers over financial reports.",
      },
      { property: "og:title", content: "Ask a question — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Evidence-grounded questions and answers over financial reports.",
      },
    ],
  }),
  component: AnalysisPage,
});

function AnalysisPage() { const { doc } = Route.useSearch(); return <AnalysisPanel documentId={doc} />; }

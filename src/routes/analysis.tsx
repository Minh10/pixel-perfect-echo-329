import { createFileRoute } from "@tanstack/react-router";
import { MessageSquareText } from "lucide-react";
import { PendingModule } from "@/components/app/pending-module";

export const Route = createFileRoute("/analysis")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "AI Analysis — FINAUDIT AI" },
      {
        name: "description",
        content: "Evidence-grounded questions and answers over financial reports.",
      },
      { property: "og:title", content: "AI Analysis — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Evidence-grounded questions and answers over financial reports.",
      },
    ],
  }),
  component: () => (
    <PendingModule
      eyebrow="Analysis"
      title="AI Analysis"
      description="Ask questions about a report and receive answers cited to specific pages, tables and charts."
      icon={<MessageSquareText className="size-5" />}
      planned={[
        "Question answering with page-level citations",
        "Cross-document comparison",
        "Answer refusal when evidence is insufficient",
        "Exportable analyst notes",
      ]}
    />
  ),
});

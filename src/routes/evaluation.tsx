import { createFileRoute } from "@tanstack/react-router";
import { Gauge } from "lucide-react";
import { PendingModule } from "@/components/app/pending-module";

export const Route = createFileRoute("/evaluation")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Evaluation — FINAUDIT AI" },
      { name: "description", content: "Measure extraction accuracy and answer grounding quality." },
      { property: "og:title", content: "Evaluation — FINAUDIT AI" },
      {
        property: "og:description",
        content: "Measure extraction accuracy and answer grounding quality.",
      },
    ],
  }),
  component: () => (
    <PendingModule
      eyebrow="Quality"
      title="Evaluation"
      description="Evaluate extracted values, citation support and detection of known discrepancies against labelled reference data."
      icon={<Gauge className="size-5" />}
    />
  ),
});

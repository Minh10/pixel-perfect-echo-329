import { createFileRoute } from "@tanstack/react-router";
import { Gauge } from "lucide-react";
import { PendingModule } from "@/components/app/pending-module";

export const Route = createFileRoute("/evaluation")({
  head: () => ({
    meta: [
      { title: "Evaluation — FINAUDIT AI" },
      { name: "description", content: "Measure extraction accuracy and answer grounding quality." },
      { property: "og:title", content: "Evaluation — FINAUDIT AI" },
      { property: "og:description", content: "Measure extraction accuracy and answer grounding quality." },
    ],
  }),
  component: () => (
    <PendingModule
      eyebrow="Quality"
      title="Evaluation"
      description="Benchmark extraction accuracy, citation faithfulness and audit recall against labelled datasets."
      icon={<Gauge className="size-5" />}
      planned={["Table extraction accuracy by document type", "Citation faithfulness scoring", "Audit finding precision / recall", "Regression tracking across model versions"]}
    />
  ),
});

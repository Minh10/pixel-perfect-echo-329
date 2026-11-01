import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { PendingModule } from "@/components/app/pending-module";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Consistency Audit — FINAUDIT AI" },
      { name: "description", content: "Detect potential inconsistencies between narrative, tables and charts." },
      { property: "og:title", content: "Consistency Audit — FINAUDIT AI" },
      { property: "og:description", content: "Detect potential inconsistencies between narrative, tables and charts." },
    ],
  }),
  component: () => (
    <PendingModule
      eyebrow="Analysis"
      title="Consistency Audit"
      description="Cross-check figures stated in narrative text against tables and charts to flag potential inconsistencies."
      icon={<ShieldCheck className="size-5" />}
      planned={["Narrative vs. table figure reconciliation", "Recomputation of derived ratios", "Period-over-period restatement detection", "Reviewer sign-off workflow"]}
    />
  ),
});

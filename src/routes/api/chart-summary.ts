import { createFileRoute } from "@tanstack/react-router";
import { handleChartSummary } from "@/lib/ai/chart-summary.server";

export const Route = createFileRoute("/api/chart-summary")({
  server: {
    handlers: {
      GET: ({ request }) => handleChartSummary(request),
      POST: ({ request }) => handleChartSummary(request),
    },
  },
});

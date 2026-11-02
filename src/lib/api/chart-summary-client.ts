import { ApiError } from "./http-service";
import type { ChartSummaryEvent } from "../ai/chart-summary";

export type GatewaySummary = { summary: string; model?: string; createdAt?: string };
export async function getChartSummaries(
  documentId: string,
): Promise<Record<string, GatewaySummary>> {
  const response = await fetch(`/api/chart-summary?${new URLSearchParams({ documentId })}`, {
    credentials: "same-origin",
  });
  await check(response);
  return response.json();
}
async function check(response: Response) {
  if (response.ok) return;
  const body = await response.json().catch(() => null);
  throw new ApiError(
    response.status,
    "chart_summary_error",
    body?.error?.message ?? "Chart summary failed. Batch stopped.",
  );
}
export async function getChartSummary(
  documentId: string,
  blockId: string,
): Promise<GatewaySummary | null> {
  const response = await fetch(
    `/api/chart-summary?${new URLSearchParams({ documentId, blockId })}`,
    { credentials: "same-origin" },
  );
  await check(response);
  return response.status === 204 ? null : response.json();
}
export async function summariseChart(
  documentId: string,
  blockId: string,
  signal: AbortSignal,
  onEvent: (event: ChartSummaryEvent) => void,
): Promise<GatewaySummary> {
  const response = await fetch("/api/chart-summary", {
    method: "POST",
    credentials: "same-origin",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ documentId, blockId }),
  });
  await check(response);
  if (response.headers.get("Content-Type")?.includes("application/json")) {
    const data: GatewaySummary = await response.json();
    onEvent({ type: "done", summary: data.summary });
    return data;
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Empty summary stream. Batch stopped.");
  const decoder = new TextDecoder();
  let buffer = "";
  let summary: string | undefined;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const event: ChartSummaryEvent = JSON.parse(buffer.slice(0, newline));
        buffer = buffer.slice(newline + 1);
        onEvent(event);
        if (event.type === "error")
          throw new ApiError(event.status, "chart_summary_error", event.message);
        if (event.type === "done") summary = event.summary;
        newline = buffer.indexOf("\n");
      }
    }
  } finally {
    await reader.cancel();
  }
  if (summary === undefined) throw new Error("Chart summary interrupted. Batch stopped.");
  return { summary };
}

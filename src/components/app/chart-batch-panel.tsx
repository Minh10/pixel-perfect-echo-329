import { useRef, useState } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/service";
import type { ChartInterpretation, Evidence } from "@/lib/api/types";
import { chartStatus, chartsToRead, summariseCharts, type ChartStatus } from "@/lib/chart-batch";
import { visualDiscrepancy } from "@/lib/fact-comparison";

type Facts = Parameters<typeof visualDiscrepancy>[1];

const LABEL: Record<ChartStatus, string> = {
  unread: "Not read",
  match: "Match",
  discrepancy: "Potential discrepancy",
  insufficient: "Insufficient evidence",
  "no-values": "No comparable values",
};

export function ChartBatchPanel({
  documentId,
  figures,
  facts,
  activeBlockId,
  onOpen,
}: {
  documentId: string;
  figures: Evidence[];
  facts: Facts;
  activeBlockId: string | undefined;
  onOpen: (evidenceId: string) => void;
}) {
  const queryClient = useQueryClient();
  const stored = useQueries({
    queries: figures.map((figure) => ({
      queryKey: ["interpretation", documentId, figure.blockId],
      queryFn: () => api.getFigureInterpretation!(documentId, figure.blockId),
      enabled: Boolean(api.getFigureInterpretation),
      retry: false,
    })),
  });
  const readings: Record<string, ChartInterpretation | undefined> = {};
  figures.forEach((figure, index) => {
    readings[figure.blockId] = stored[index]?.data as ChartInterpretation | undefined;
  });
  const statuses = figures.map((figure) => chartStatus(readings[figure.blockId], facts));
  const counts = summariseCharts(statuses);
  const loading = stored.some((query) => query.isLoading);
  const todo = chartsToRead(
    figures.map((figure) => figure.blockId),
    readings,
  );

  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stop = useRef(false);

  async function readAll() {
    if (!api.interpretFigure || todo.length === 0) return;
    stop.current = false;
    setError(null);
    setProgress({ done: 0, total: todo.length });
    for (let index = 0; index < todo.length; index += 1) {
      if (stop.current) break;
      const blockId = todo[index]!;
      try {
        const data = await api.interpretFigure(documentId, blockId);
        queryClient.setQueryData(["interpretation", documentId, blockId], data);
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : "Chart reading stopped. Try again later.",
        );
        break;
      }
      setProgress({ done: index + 1, total: todo.length });
    }
    setProgress(null);
  }

  if (figures.length === 0) return null;
  const running = progress !== null;

  return (
    <section className="rounded-md border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Whole document</p>
          <h2 className="mt-1 text-lg font-semibold">All charts in this report</h2>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            {loading
              ? "Checking stored chart readings…"
              : `${figures.length - counts.unread} of ${figures.length} charts have a text summary. Each new reading uses one AI call from the demo allowance.`}
          </p>
        </div>
        {api.interpretFigure &&
          (running ? (
            <Button type="button" variant="outline" onClick={() => (stop.current = true)}>
              Stop ({progress.done}/{progress.total})
            </Button>
          ) : (
            <Button type="button" disabled={loading || todo.length === 0} onClick={readAll}>
              {todo.length === 0 ? "All charts summarised" : `Summarise ${todo.length} charts`}
            </Button>
          ))}
      </div>
      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
      <dl className="mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-md border bg-border md:grid-cols-4">
        {(["match", "discrepancy", "insufficient", "unread"] as const).map((key) => (
          <div key={key} className="bg-card px-4 py-3">
            <dt className="text-xs text-muted-foreground">{LABEL[key]}</dt>
            <dd className="mt-1 text-2xl tabular">{counts[key]}</dd>
          </div>
        ))}
      </dl>
      <ul className="mt-4 divide-y rounded-md border">
        {figures.map((figure, index) => (
          <li key={figure.id}>
            <button
              type="button"
              onClick={() => onOpen(figure.id)}
              aria-current={figure.blockId === activeBlockId}
              className="flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm hover:bg-muted aria-[current=true]:bg-accent"
            >
              <span className="truncate">
                {readings[figure.blockId]?.title ?? figure.label} · Page {figure.page}
              </span>
              <span
                className={
                  statuses[index] === "discrepancy"
                    ? "shrink-0 text-xs font-medium text-warning"
                    : "shrink-0 text-xs text-muted-foreground"
                }
              >
                {LABEL[statuses[index]!]}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

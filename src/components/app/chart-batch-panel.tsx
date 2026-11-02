import { useEffect, useRef, useState } from "react";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/service";
import type { ChartInterpretation, Evidence } from "@/lib/api/types";
import { chartStatus, summariseCharts, type ChartStatus } from "@/lib/chart-batch";
import { runChartSummaries } from "@/lib/ai/chart-summary";
import type { GatewaySummary } from "@/lib/api/chart-summary-client";
import { Progress } from "@/components/ui/progress";
import { Square, Sparkles } from "lucide-react";
import { visualDiscrepancy } from "@/lib/fact-comparison";

type Facts = Parameters<typeof visualDiscrepancy>[1];

const LABEL: Record<ChartStatus, string> = {
  unread: "Not checked against tables",
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
  // Stored readings load one at a time (not a burst of parallel requests) so the
  // demo's per-minute request allowance is not exhausted; results stay cached.
  const stored = useQuery({
    queryKey: ["interpretations", documentId, figures.map((f) => f.blockId).join(",")],
    queryFn: async () => {
      const out: Record<string, ChartInterpretation | undefined> = {};
      for (const figure of figures) {
        const cached = queryClient.getQueryData<ChartInterpretation>([
          "interpretation",
          documentId,
          figure.blockId,
        ]);
        if (cached) {
          out[figure.blockId] = cached;
          continue;
        }
        try {
          const reading = await api.getFigureInterpretation!(documentId, figure.blockId);
          out[figure.blockId] = reading;
          queryClient.setQueryData(["interpretation", documentId, figure.blockId], reading);
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 404)) throw err;
        }
      }
      return out;
    },
    enabled: Boolean(api.getFigureInterpretation) && figures.length > 0,
    staleTime: 5 * 60_000,
    retry: false,
  });
  const readings: Record<string, ChartInterpretation | undefined> = stored.data ?? {};
  const statuses = figures.map((figure) => chartStatus(readings[figure.blockId], facts));
  const counts = summariseCharts(statuses);
  const summaryQuery = useQuery({
    queryKey: ["gateway-summaries", documentId],
    queryFn: (): Promise<Record<string, GatewaySummary>> =>
      api.getChartSummaries?.(documentId) ?? Promise.resolve({}),
    enabled: Boolean(api.getChartSummaries),
    retry: false,
  });
  const summaries = figures.map((figure) => ({ data: summaryQuery.data?.[figure.blockId] }));
  const loading = summaryQuery.isLoading;
  const loadError = summaryQuery.error;
  const todo = figures
    .filter((_, index) => !summaries[index]?.data?.summary)
    .map((figure) => figure.blockId);

  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [partial, setPartial] = useState<Record<string, string>>({});
  const [thinking, setThinking] = useState("");
  const [active, setActive] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function readAll() {
    const summarise = api.summariseChart;
    if (!summarise || todo.length === 0 || controller.current) return;
    const abort = new AbortController();
    controller.current = abort;
    setRunning(true);
    setError(null);
    setProgress({ done: 0, total: todo.length });
    try {
      await runChartSummaries(
        todo,
        abort.signal,
        async (blockId) => {
          setActive(blockId);
          setThinking("");
          setPartial((value) => ({ ...value, [blockId]: "" }));
          const data = await summarise(documentId, blockId, abort.signal, (event) => {
            if (event.type === "text")
              setPartial((value) => ({ ...value, [blockId]: (value[blockId] ?? "") + event.text }));
            if (event.type === "reasoning") setThinking((value) => value + event.text);
          });
          queryClient.setQueryData<Record<string, GatewaySummary>>(
            ["gateway-summaries", documentId],
            (value) => ({ ...value, [blockId]: data }),
          );
        },
        (done) => setProgress({ done, total: todo.length }),
      );
    } catch (cause) {
      setError(
        abort.signal.aborted
          ? "Stopped. Completed summaries are saved; unfinished charts remain unread."
          : cause instanceof Error
            ? cause.message
            : "Chart summaries stopped.",
      );
    } finally {
      controller.current = null;
      setRunning(false);
      setActive(null);
      setThinking("");
    }
  }

  if (figures.length === 0) return null;

  return (
    <section className="border-y py-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Whole document</p>
          <h2 className="mt-1 text-lg font-semibold">All charts in this report</h2>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            {loading
              ? "Loading saved summaries…"
              : `${figures.length - todo.length} of ${figures.length} Lovable AI summaries saved · separate from table checks.`}
          </p>
        </div>
        {api.summariseChart &&
          (running ? (
            <Button type="button" variant="outline" onClick={() => controller.current?.abort()}>
              <Square className="size-4" /> Stop ({progress?.done ?? 0}/{progress?.total ?? 0})
            </Button>
          ) : (
            <Button
              type="button"
              disabled={loading || Boolean(loadError) || todo.length === 0}
              onClick={readAll}
            >
              <Sparkles className="size-4" />
              {todo.length === 0 ? "All charts summarised" : `Summarise ${todo.length} charts`}
            </Button>
          ))}
      </div>
      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
      {loadError && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {loadError instanceof Error ? loadError.message : "Saved summaries could not be loaded."}
        </p>
      )}
      {progress && (
        <div className="mt-4 space-y-2" aria-live="polite">
          <p className="text-sm">
            {running ? "Summarising" : "Completed"} · {progress.done}/{progress.total}
          </p>
          <Progress
            value={progress.total ? (progress.done / progress.total) * 100 : 0}
            aria-label="Chart summary progress"
          />
        </div>
      )}
      {running && (
        <p role="status" className="mt-3 text-sm text-muted-foreground">
          {thinking || "Reading chart…"}
        </p>
      )}
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
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpen(figure.id)}
              aria-current={figure.blockId === activeBlockId}
              className="flex h-auto w-full items-center justify-between gap-3 rounded-none px-4 py-2 text-left text-sm aria-[current=true]:bg-accent"
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
                {LABEL[statuses[index] ?? "unread"]}
              </span>
            </Button>
            {(summaries[index]?.data?.summary || partial[figure.blockId]) && (
              <div className="px-4 pb-4 text-sm leading-6">
                <p className="whitespace-pre-wrap">
                  {summaries[index]?.data?.summary ?? partial[figure.blockId]}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {summaries[index]?.data
                    ? "Lovable AI · visual summary, not verified table facts"
                    : active === figure.blockId
                      ? "Generating…"
                      : "Incomplete · not saved"}
                </p>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

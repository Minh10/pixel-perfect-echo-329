export const MAX_GATEWAY_CHART_CALLS = 40;
export type ChartSummaryEvent =
  | { type: "text"; text: string }
  | { type: "reasoning"; text: string }
  | { type: "done"; summary: string }
  | { type: "error"; message: string; status: number };

export async function runChartSummaries(
  ids: string[],
  signal: AbortSignal,
  read: (id: string) => Promise<void>,
  completed: (done: number) => void,
) {
  let done = 0;
  for (const id of ids) {
    signal.throwIfAborted();
    await read(id);
    signal.throwIfAborted();
    completed(++done);
  }
  return done;
}

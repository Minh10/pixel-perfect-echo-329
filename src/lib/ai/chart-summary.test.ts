import { describe, expect, it, vi } from "vitest";
import { MAX_GATEWAY_CHART_CALLS, runChartSummaries } from "./chart-summary";

describe("Gateway chart batch", () => {
  it("stops on a quota error without calling remaining charts", async () => {
    const read = vi.fn().mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error("quota"));
    const completed = vi.fn();
    await expect(
      runChartSummaries(["a", "b", "c"], new AbortController().signal, read, completed),
    ).rejects.toThrow("quota");
    expect(read.mock.calls.map((call) => call[0])).toEqual(["a", "b"]);
    expect(completed).toHaveBeenCalledExactlyOnceWith(1);
  });
  it("stops on any error without retrying", async () => {
    const read = vi.fn().mockRejectedValue(new Error("denied"));
    await expect(
      runChartSummaries(["a", "b"], new AbortController().signal, read, vi.fn()),
    ).rejects.toThrow("denied");
    expect(read).toHaveBeenCalledTimes(1);
  });
  it("does not start the next chart after Stop", async () => {
    const controller = new AbortController();
    const read = vi.fn(async () => {
      controller.abort();
    });
    await expect(runChartSummaries(["a", "b"], controller.signal, read, vi.fn())).rejects.toThrow();
    expect(read).toHaveBeenCalledTimes(1);
  });
  it("runs all charts sequentially and reports concrete progress", async () => {
    const completed = vi.fn();
    const read = vi.fn().mockResolvedValue(undefined);
    expect(
      await runChartSummaries(["a", "b", "c"], new AbortController().signal, read, completed),
    ).toBe(3);
    expect(completed.mock.calls).toEqual([[1], [2], [3]]);
  });
  it("bounds the additional gateway allowance to 200 per UTC day", () => {
    expect(MAX_GATEWAY_CHART_CALLS).toBe(200);
  });
});

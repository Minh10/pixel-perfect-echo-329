import { afterEach, expect, it, vi } from "vitest";
import { summariseChart } from "./chart-summary-client";
afterEach(() => vi.restoreAllMocks());
it("surfaces a 503 as a caught batch error without emitting success or retrying", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      Response.json({ error: { message: "Summary storage unavailable" } }, { status: 503 }),
    );
  const onEvent = vi.fn();
  await expect(
    summariseChart("report", "chart", new AbortController().signal, onEvent),
  ).rejects.toMatchObject({ status: 503, message: "Summary storage unavailable" });
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(onEvent).not.toHaveBeenCalled();
});

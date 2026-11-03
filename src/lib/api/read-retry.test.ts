import { describe, expect, it } from "vitest";
import { ApiError } from "./http-service";
import { retryDocumentRead } from "./read-retry";

describe("Document outage recovery", () => {
  it.each([401, 429, 502, 503])("does not retry known HTTP %s errors automatically", (status) => {
    expect(retryDocumentRead(0, new ApiError(status, "backend_unavailable", "Unavailable"))).toBe(
      false,
    );
  });
  it("allows only one retry for an unexpected read failure", () => {
    expect(retryDocumentRead(0, new Error("Unexpected"))).toBe(true);
    expect(retryDocumentRead(1, new Error("Unexpected"))).toBe(false);
  });
});

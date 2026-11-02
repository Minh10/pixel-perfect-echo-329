import { expect, it } from "vitest";
import { selectWorkspaceDocument } from "./workspace-selection";
const documents = [{ id: "sample", status: "ready" }];
it("defers a live PDF deep link until server-verified service selection", () => {
  expect(selectWorkspaceDocument("doc_310204fac7894dd38555d39a4656b68c", true, "sample", documents)).toEqual({ docId: null, awaitingLiveSession: true });
});
it("retains the requested live PDF once the live service is selected", () => {
  expect(selectWorkspaceDocument("live", false, null, [{ id: "live", status: "ready" }])).toEqual({ docId: "live", awaitingLiveSession: false });
});
it("keeps public sample links readable without live entry", () => {
  expect(selectWorkspaceDocument("sample", true, "sample", documents)).toEqual({ docId: "sample", awaitingLiveSession: false });
});
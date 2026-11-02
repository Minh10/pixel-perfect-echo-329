/** A public sample service must never attempt to read an unknown live document. */
export function selectWorkspaceDocument(
  requested: string | undefined,
  sample: boolean,
  defaultId: string | null,
  documents: { id: string; status: string }[],
): { docId: string | null; awaitingLiveSession: boolean } {
  if (sample && requested && !documents.some((document) => document.id === requested))
    return { docId: null, awaitingLiveSession: true };
  return {
    docId:
      requested ??
      defaultId ??
      documents.find((document) => document.status === "ready")?.id ??
      null,
    awaitingLiveSession: false,
  };
}

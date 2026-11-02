import { useSyncExternalStore } from "react";

// Browser-only mirror of GET /api/public/demo-session. It only drives UI
// labels; every live request is still authorised by the signed server cookie.
export interface LiveStatus {
  checked: boolean;
  enabled: boolean;
  entered: boolean;
}

export type EntryState = "live" | "activate" | "sample-entered" | "sample";

/**
 * Which entry control to show. A tab-local sample entry never counts as live:
 * when the live demo is switched on, only a server-verified signed session does.
 */
export function entryState(status: LiveStatus, sampleEntered: boolean): EntryState {
  if (status.enabled && status.entered) return "live";
  if (status.enabled) return "activate";
  return sampleEntered ? "sample-entered" : "sample";
}

const SERVER: LiveStatus = { checked: false, enabled: false, entered: false };
let current: LiveStatus = SERVER;
const listeners = new Set<() => void>();

export function setLiveStatus(next: Omit<LiveStatus, "checked">): void {
  if (current.checked && current.enabled === next.enabled && current.entered === next.entered)
    return;
  current = { checked: true, ...next };
  listeners.forEach((listener) => listener());
}

export function useLiveStatus(): LiveStatus {
  return useSyncExternalStore(
    (callback) => {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    () => current,
    () => SERVER,
  );
}

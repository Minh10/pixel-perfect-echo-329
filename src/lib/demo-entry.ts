import { useSyncExternalStore } from "react";

// PUBLIC SAMPLE UX ONLY: admin/admin is intentionally guessable, not a secret
// or secure authentication. Never read this state from any real auth/proxy code.
const STORAGE_KEY = "finaudit-sample-entry";
const CHANGE_EVENT = "finaudit-sample-entry-change";

export function acceptsDemoEntry(username: string, password: string): boolean {
  return username === "admin" && password === "admin";
}

export function setDemoEntry(entered: boolean): void {
  try {
    if (entered) window.sessionStorage.setItem(STORAGE_KEY, "sample-only");
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Blocked browser storage must not prevent public sample navigation.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function readDemoEntry(): boolean {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) === "sample-only";
  } catch {
    return false;
  }
}

function subscribe(callback: () => void) {
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

export function useDemoEntry(): boolean {
  return useSyncExternalStore(subscribe, readDemoEntry, () => false);
}

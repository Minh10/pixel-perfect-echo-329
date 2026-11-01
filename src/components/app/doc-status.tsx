import type { DocumentStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const MAP: Record<DocumentStatus, { label: string; cls: string }> = {
  ready: { label: "Ready", cls: "bg-success" },
  processing: { label: "Processing", cls: "bg-warning animate-pulse" },
  failed: { label: "Failed", cls: "bg-destructive" },
};

export function DocStatus({ status }: { status: DocumentStatus }) {
  const m = MAP[status];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className={cn("size-1.5 rounded-full", m.cls)} />
      {m.label}
    </span>
  );
}

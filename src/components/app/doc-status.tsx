import type { DocumentStatus } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const MAP: Record<DocumentStatus, { label: string; cls: string }> = {
  ready: { label: "Ready", cls: "bg-success-soft text-success" },
  processing: { label: "Processing", cls: "bg-warning-soft text-warning" },
  failed: { label: "Failed", cls: "bg-error-soft text-destructive" },
};

export function DocStatus({ status }: { status: DocumentStatus }) {
  const m = MAP[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-2 py-1 text-xs font-medium",
        m.cls,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {m.label}
    </span>
  );
}

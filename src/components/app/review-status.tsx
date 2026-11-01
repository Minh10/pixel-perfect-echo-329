import { cn } from "@/lib/utils";
import type { ComparisonStatus } from "@/lib/fact-comparison";

const COPY: Record<ComparisonStatus, string> = {
  MATCH: "Match",
  POTENTIAL_DISCREPANCY: "Potential discrepancy",
  INSUFFICIENT_EVIDENCE: "Insufficient evidence",
};

const TONE: Record<ComparisonStatus, string> = {
  MATCH: "bg-success-soft text-success",
  POTENTIAL_DISCREPANCY: "bg-warning-soft text-warning",
  INSUFFICIENT_EVIDENCE: "bg-muted text-muted-foreground",
};

export function ReviewStatus({ status }: { status: ComparisonStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-2 py-0.5 text-[11px] font-medium tracking-normal",
        TONE[status],
      )}
    >
      {COPY[status]}
    </span>
  );
}

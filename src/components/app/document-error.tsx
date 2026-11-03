import { useRouter, type ErrorComponentProps } from "@tanstack/react-router";
import { ApiError } from "@/lib/api/http-service";
import { ErrorState } from "./states";

export function DocumentError({ error, reset }: ErrorComponentProps) {
  const router = useRouter();
  const unavailable =
    error instanceof ApiError && (error.code === "backend_unavailable" || error.code === "timeout");
  return (
    <section className="page-layout space-y-3" aria-label="Document loading error">
      <ErrorState
        title={unavailable ? "Document service unavailable" : "Couldn't load this view"}
        message={error instanceof Error ? error.message : "No report could be loaded."}
        onRetry={() => {
          void router.invalidate();
          reset();
        }}
      />
      {unavailable && (
        <p className="text-sm text-muted-foreground">
          Live reports cannot be loaded right now. No processing or AI result was generated. Retry
          once the document service is reachable, or exit the demo to view the synthetic sample.
        </p>
      )}
    </section>
  );
}

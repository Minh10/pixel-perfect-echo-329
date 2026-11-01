import type { ReactNode } from "react";
import { AlertTriangle, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function DemoBadge({ className }: { className?: string }) {
  return (
    <span
      title="Values shown are fictional demo data, not verified financial results."
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm bg-demo px-2 py-0.5 text-[10px] font-semibold text-demo-foreground",
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-demo-foreground" />
      DEMO data
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="grid min-w-0 grid-cols-1 items-end gap-5 border-b pb-6 xl:grid-cols-[minmax(0,1fr)_auto]">
      <div className="min-w-0 space-y-2">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold leading-tight md:text-[2rem]">{title}</h1>
        {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex min-w-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-dashed bg-card px-6 py-16 text-center">
      <div className="mb-4 grid size-10 place-items-center rounded-md bg-muted text-muted-foreground">
        {icon ?? <Inbox className="size-5" />}
      </div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Couldn't load this view",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-4"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
      <div className="flex-1">
        <p className="text-sm font-semibold text-destructive">{title}</p>
        {message && <p className="mt-0.5 text-sm text-muted-foreground">{message}</p>}
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function WorkspaceSkeleton() {
  return (
    <div className="grid h-[calc(100svh-3.5rem)] grid-cols-1 lg:grid-cols-[200px_1fr_340px]">
      <div className="hidden space-y-3 border-r p-3 lg:block">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[3/4] w-full" />
        ))}
      </div>
      <div className="bg-canvas p-8">
        <Skeleton className="mx-auto aspect-[1/1.3] max-w-2xl" />
      </div>
      <div className="hidden space-y-3 border-l p-4 lg:block">
        <Skeleton className="h-5 w-1/2" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 p-6 md:p-8">
      <Skeleton className="h-8 w-64" />
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

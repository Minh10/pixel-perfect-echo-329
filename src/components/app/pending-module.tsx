import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader } from "./states";

/** Honest placeholder for modules that depend on backend capabilities not yet connected. */
export function PendingModule({ eyebrow, title, description, planned, icon }: { eyebrow: string; title: string; description: string; planned: string[]; icon: ReactNode }) {
  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6 md:p-8">
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <EmptyState
        icon={icon}
        title="Awaiting backend integration"
        description="This module will produce results once the analysis API is connected. No results are simulated here."
        action={<Button asChild variant="outline" size="sm"><Link to="/intelligence">Inspect source evidence</Link></Button>}
      />
      <section className="rounded-md border bg-card p-5">
        <p className="eyebrow mb-3">Planned capabilities</p>
        <ul className="grid gap-2 text-sm md:grid-cols-2">
          {planned.map((p) => (
            <li key={p} className="flex gap-2"><span className="mt-2 size-1 shrink-0 rounded-full bg-evidence" />{p}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader } from "./states";

/** Honest placeholder for modules that depend on backend capabilities not yet connected. */
export function PendingModule({
  eyebrow,
  title,
  description,
  icon,
}: {
  eyebrow: string;
  title: string;
  description: string;
  icon: ReactNode;
}) {
  return (
    <div className="page-layout space-y-6">
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <EmptyState
        icon={icon}
        title="Document service not connected"
        description="This published preview cannot run this step. No result is invented here. The sample report can still be inspected."
        action={
          <Button asChild size="sm">
            <Link to="/intelligence">Open sample report</Link>
          </Button>
        }
      />
    </div>
  );
}

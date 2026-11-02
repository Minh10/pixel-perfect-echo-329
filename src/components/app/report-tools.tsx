import { Link, useRouterState } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { NAV_ITEMS } from "./nav";

/** Navigation only: retains the report context, never selects a service or runs analysis. */
export function ReportTools({
  documentId,
  sample = false,
}: {
  documentId?: string | undefined;
  sample?: boolean;
}) {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const items = NAV_ITEMS.filter((item) =>
    (sample
      ? ["/intelligence", "/trends"]
      : ["/intelligence", "/audit", "/trends", "/analysis"]
    ).includes(item.to),
  );
  return (
    <nav aria-label="Report tools" className="flex flex-wrap gap-2 border-b pb-3">
      {items.map((item) => (
        <Button
          key={item.to}
          asChild
          size="sm"
          variant={pathname === item.to ? "secondary" : "ghost"}
        >
          <Link
            to={item.to}
            search={{ doc: documentId }}
            aria-current={pathname === item.to ? "page" : undefined}
          >
            <item.icon className="size-4" />
            {item.title}
          </Link>
        </Button>
      ))}
    </nav>
  );
}

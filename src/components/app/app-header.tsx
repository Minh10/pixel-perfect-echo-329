import { Link, useRouterState } from "@tanstack/react-router";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { NAV_ITEMS } from "./nav";
import { IS_DEMO } from "@/lib/api/service";
import { DemoBadge } from "./states";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import { setDemoEntry, useDemoEntry } from "@/lib/demo-entry";

export function AppHeader() {
  const demoEntered = useDemoEntry();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const current = NAV_ITEMS.find((i) =>
    i.to === "/" ? pathname === "/" : pathname.startsWith(i.to),
  );

  return (
    <header className="sticky top-0 z-20 grid h-14 shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b bg-card px-4 md:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="h-5" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden sm:block">
              <BreadcrumbLink asChild>
                <Link to="/">FINAUDIT</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem>
              <BreadcrumbPage className="truncate font-medium">
                {current?.title ?? (pathname === "/login" ? "Demo entry" : "Not found")}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {IS_DEMO && <DemoBadge />}
        {IS_DEMO &&
          (demoEntered ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                setDemoEntry(false);
                await navigate({ to: "/", replace: true, reloadDocument: true });
              }}
            >
              <LogOut />
              Exit demo
            </Button>
          ) : (
            <Button asChild variant="ghost" size="sm">
              <Link to="/login">
                <LogIn />
                Demo entry
              </Link>
            </Button>
          ))}
      </div>
    </header>
  );
}

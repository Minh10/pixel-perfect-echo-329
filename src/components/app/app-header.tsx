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
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { ownerSession, refreshOwnerSession, signOut } from "@/lib/auth.functions";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

export function AppHeader() {
  const getSession = useServerFn(ownerSession);
  const refresh = useServerFn(refreshOwnerSession);
  const logout = useServerFn(signOut);
  const queries = useQueryClient();
  const navigate = useNavigate();
  const { data: session } = useQuery({
    queryKey: ["owner-session"],
    queryFn: () => getSession(),
    retry: false,
  });
  useEffect(() => {
    const renew = async () => {
      try {
        const result = await refresh();
        queries.setQueryData(["owner-session"], result);
      } catch {
        queries.setQueryData(["owner-session"], { signedIn: false, email: "" });
      }
    };
    void renew();
    const timer = window.setInterval(() => void renew(), 60_000);
    return () => window.clearInterval(timer);
  }, [refresh, queries]);
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
                {current?.title ??
                  (pathname === "/login"
                    ? "Private sign-in"
                    : pathname === "/reset-password"
                      ? "Reset password"
                      : "Not found")}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {IS_DEMO && <DemoBadge />}
        {session?.signedIn ? (
          <Button
            variant="ghost"
            size="sm"
            title={session.email}
            onClick={async () => {
              await queries.cancelQueries();
              queries.clear();
              await logout();
              await navigate({ to: "/login", replace: true });
            }}
          >
            <LogOut />
            Sign out
          </Button>
        ) : (
          <Button asChild variant="ghost" size="sm">
            <Link to="/login">
              <LogIn />
              Sign in
            </Link>
          </Button>
        )}
      </div>
    </header>
  );
}

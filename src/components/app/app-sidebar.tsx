import { Link, useRouterState } from "@tanstack/react-router";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel,
  SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
} from "@/components/ui/sidebar";
import { NAV_ITEMS } from "./nav";

const GROUPS = ["Workspace", "Analysis", "Quality"] as const;

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isActive = (to: string) => (to === "/" ? pathname === "/" : pathname.startsWith(to));

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 justify-center border-b border-sidebar-border px-3">
        <Link to="/" className="flex items-center gap-2.5 overflow-hidden">
          <span className="grid size-7 shrink-0 place-items-center rounded-sm bg-sidebar-primary font-mono text-xs font-semibold text-sidebar-primary-foreground">
            FA
          </span>
          <span className="truncate text-sm font-semibold tracking-tight text-sidebar-accent-foreground group-data-[collapsible=icon]:hidden">
            FINAUDIT <span className="font-normal text-sidebar-foreground">AI</span>
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent className="pt-2">
        {GROUPS.map((group) => (
          <SidebarGroup key={group}>
            <SidebarGroupLabel className="font-mono text-[10px] uppercase tracking-widest text-sidebar-foreground/50">
              {group}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV_ITEMS.filter((i) => i.group === group).map((item) => (
                  <SidebarMenuItem key={item.to}>
                    <SidebarMenuButton asChild isActive={isActive(item.to)} tooltip={item.title}>
                      <Link to={item.to}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border p-3 group-data-[collapsible=icon]:hidden">
        <p className="font-mono text-[10px] uppercase tracking-widest text-sidebar-foreground/50">Environment</p>
        <p className="text-xs text-sidebar-foreground">Demo data · backend not connected</p>
      </SidebarFooter>
    </Sidebar>
  );
}

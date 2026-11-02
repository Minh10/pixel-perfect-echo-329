import { Link, useRouterState } from "@tanstack/react-router";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { IS_DEMO } from "@/lib/api/service";
import { NAV_ITEMS } from "./nav";

const GROUPS = ["Workspace", "Analysis", "Quality"] as const;

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isActive = (to: string) => (to === "/" ? pathname === "/" : pathname.startsWith(to));

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 justify-center border-b border-sidebar-border px-4">
        <Link to="/" className="flex items-center gap-2.5 overflow-hidden">
          <span className="grid size-8 shrink-0 place-items-center rounded-sm bg-sidebar-primary text-xs font-semibold text-sidebar-primary-foreground">
            FA
          </span>
          <span className="truncate text-sm font-semibold text-foreground group-data-[collapsible=icon]:hidden">
            FINAUDIT <span className="font-normal text-sidebar-foreground">AI</span>
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent className="pt-2">
        {GROUPS.map((group) => (
          <SidebarGroup key={group}>
            <SidebarGroupLabel className="text-xs font-medium text-muted-foreground">
              {group}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV_ITEMS.filter((i) => i.group === group).map((item) => (
                  <SidebarMenuItem key={item.to}>
                    <SidebarMenuButton
                      className="h-10 border-l-2 border-transparent data-[active=true]:border-primary data-[active=true]:font-semibold"
                      asChild
                      isActive={isActive(item.to)}
                      tooltip={item.title}
                    >
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
        <p className="text-xs font-medium text-muted-foreground">Environment</p>
        <p className="text-xs text-sidebar-foreground">
          {IS_DEMO ? "Sample library" : "Document service"}
        </p>
      </SidebarFooter>
    </Sidebar>
  );
}

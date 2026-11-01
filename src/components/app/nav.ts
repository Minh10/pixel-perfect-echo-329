import {
  LayoutGrid,
  FileText,
  ScanSearch,
  MessageSquareText,
  ShieldCheck,
  TrendingUp,
  Gauge,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  to: "/" | "/documents" | "/intelligence" | "/analysis" | "/audit" | "/trends" | "/evaluation";
  icon: LucideIcon;
  group: "Workspace" | "Analysis" | "Quality";
}

export const NAV_ITEMS: NavItem[] = [
  { title: "Overview", to: "/", icon: LayoutGrid, group: "Workspace" },
  { title: "Documents", to: "/documents", icon: FileText, group: "Workspace" },
  { title: "Document Intelligence", to: "/intelligence", icon: ScanSearch, group: "Workspace" },
  { title: "AI Analysis", to: "/analysis", icon: MessageSquareText, group: "Analysis" },
  { title: "Consistency Audit", to: "/audit", icon: ShieldCheck, group: "Analysis" },
  { title: "Trends", to: "/trends", icon: TrendingUp, group: "Analysis" },
  { title: "Evaluation", to: "/evaluation", icon: Gauge, group: "Quality" },
];

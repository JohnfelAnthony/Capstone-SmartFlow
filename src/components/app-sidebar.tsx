import * as React from "react"

import { type CurrentUser } from "@/api/auth"
import { NavDocuments } from "@/components/nav-documents"
import { NavMain } from "@/components/nav-main"
import { NavSecondary } from "@/components/nav-secondary"
import { NavUser } from "@/components/nav-user"
import { canViewPage } from "@/lib/page-access"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import {
  CircleHelpIcon,
  ClipboardListIcon,
  DatabaseIcon,
  FileTextIcon,
  GaugeIcon,
  GraduationCapIcon,
  MapPinnedIcon,
  NetworkIcon,
  RouteIcon,
  Settings2Icon,
  ShieldIcon,
  UsersIcon,
} from "lucide-react"

const data = {
  navMain: [
    {
      title: "Dashboard",
      url: "#",
      icon: <GaugeIcon />,
      page: "dashboard",
    },
    {
      title: "Scenarios",
      url: "#",
      icon: <MapPinnedIcon />,
      page: "scenarios",
    },
    {
      title: "Route Planner",
      url: "#",
      icon: <RouteIcon />,
      page: "route-planner",
    },
    {
      title: "Runs & Reports",
      url: "#",
      icon: <FileTextIcon />,
      page: "runs-reports",
    },
    {
      title: "Compare Runs",
      url: "#",
      icon: <NetworkIcon />,
      page: "compare",
    },
  ],
  navResearch: [
    {
      title: "RL Training",
      url: "#",
      icon: <GraduationCapIcon />,
      page: "rl-training",
    },
  ],
  navSecondary: [
    {
      title: "Settings",
      url: "#",
      icon: <Settings2Icon />,
      page: "profile",
    },
    {
      title: "Help",
      url: "#",
      icon: <CircleHelpIcon />,
      page: "help",
    },
  ],
  admin: [
    {
      name: "User Management",
      url: "#",
      icon: <UsersIcon />,
      page: "admin-users",
    },
    {
      name: "Role & Access Control",
      url: "#",
      icon: <ShieldIcon />,
      page: "admin-roles",
    },
    {
      name: "Audit Logs",
      url: "#",
      icon: <ClipboardListIcon />,
      page: "admin-audit",
    },
    {
      name: "Backup & Restore",
      url: "#",
      icon: <DatabaseIcon />,
      page: "admin-backups",
    },
  ],
}

export function AppSidebar({
  activeItem,
  currentUser,
  onOpenAccount,
  onLogout,
  onSelectItem,
  ...props
}: React.ComponentProps<typeof Sidebar> & {
  activeItem: string
  currentUser: CurrentUser | null
  onOpenAccount: () => void
  onLogout: () => void
  onSelectItem: (item: string) => void
}) {
  const sidebarUser = {
    name: currentUser?.full_name || currentUser?.username || "SMARTFLOW User",
    email: currentUser?.email || currentUser?.role || "smartflow.local",
  }
  const visibleMainItems = data.navMain.filter((item) => canViewPage(currentUser, item.page))
  const visibleResearchItems = data.navResearch.filter((item) => canViewPage(currentUser, item.page))
  const visibleSecondaryItems = data.navSecondary.filter((item) => canViewPage(currentUser, item.page))
  const visibleAdminItems = data.admin.filter((item) => canViewPage(currentUser, item.page))

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              className="data-[slot=sidebar-menu-button]:p-1.5!"
              render={<a href="#" />}
            >
              <img src="/logo.svg" alt="" className="smartflow-brand-logo size-7!" />
              <span className="smartflow-brand-copy">
                <span className="smartflow-brand-name">SmartFlow</span>
                <span className="smartflow-brand-sub">Traffic</span>
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain
          activeItem={activeItem}
          label="Operate"
          items={visibleMainItems}
          onSelectItem={onSelectItem}
        />
        {visibleResearchItems.length > 0 ? (
          <NavMain
            activeItem={activeItem}
            label="Research"
            items={visibleResearchItems}
            onSelectItem={onSelectItem}
          />
        ) : null}
        {visibleAdminItems.length > 0 ? (
          <NavDocuments
            activeItem={activeItem}
            label="Admin"
            items={visibleAdminItems}
            onSelectItem={onSelectItem}
          />
        ) : null}
        <NavSecondary
          activeItem={activeItem}
          items={visibleSecondaryItems}
          onSelectItem={onSelectItem}
          className="mt-auto"
        />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={sidebarUser} onOpenAccount={onOpenAccount} onLogout={onLogout} />
      </SidebarFooter>
    </Sidebar>
  )
}

"use client"

import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

export function NavDocuments({
  activeItem,
  label = "Documents",
  items,
  onSelectItem,
}: {
  activeItem: string
  label?: string
  items: {
    name: string
    url: string
    icon: React.ReactNode
  }[]
  onSelectItem: (item: string) => void
}) {
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => (
          <SidebarMenuItem key={item.name}>
            <SidebarMenuButton
              className={item.name === activeItem ? "smartflow-nav-active" : ""}
              onClick={() => onSelectItem(item.name)}
              render={<a href={item.url} />}
            >
              {item.icon}
              <span>{item.name}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}

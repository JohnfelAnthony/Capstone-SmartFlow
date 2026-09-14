import * as React from "react"

import { Button } from "@/components/ui/button"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

const trafficLightStates = ["red", "yellow", "green"] as const

function useSidebarClock() {
  const [now, setNow] = React.useState(() => new Date())

  React.useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)

    return () => window.clearInterval(timer)
  }, [])

  return {
    dateLabel: new Intl.DateTimeFormat(undefined, {
      month: "long",
      day: "numeric",
    }).format(now),
    timeLabel: new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(now),
    trafficState: trafficLightStates[Math.floor(now.getTime() / 4000) % trafficLightStates.length],
  }
}

export function NavMain({
  activeItem,
  items,
  onSelectItem,
}: {
  activeItem: string
  items: {
    title: string
    url: string
    icon?: React.ReactNode
  }[]
  onSelectItem: (item: string) => void
}) {
  const { dateLabel, timeLabel, trafficState } = useSidebarClock()

  return (
    <SidebarGroup>
      <SidebarGroupContent className="flex flex-col gap-2">
        <SidebarMenu>
          <SidebarMenuItem className="flex items-center gap-2">
            <SidebarMenuButton
              tooltip="Current date and time"
              className="min-w-8 bg-transparent text-primary duration-200 ease-linear hover:bg-transparent hover:text-primary active:bg-transparent active:text-primary"
            >
              <span className={`sidebar-clock sidebar-clock-${trafficState}`}>
                <span className="sidebar-clock-date">{dateLabel}</span>
                <span className="sidebar-clock-time">
                  {timeLabel}
                </span>
              </span>
            </SidebarMenuButton>
            <Button
              size="icon"
              className="traffic-light-button group-data-[collapsible=icon]:opacity-0"
              variant="ghost"
              aria-label={`Traffic light status: ${trafficState}`}
            >
              <span className={`traffic-light-dot traffic-light-${trafficState}`} />
            </Button>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                tooltip={item.title}
                className={item.title === activeItem ? "smartflow-nav-active" : ""}
                onClick={() => onSelectItem(item.title)}
              >
                {item.icon}
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

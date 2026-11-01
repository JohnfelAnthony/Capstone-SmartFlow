import { MapIcon, PanelsTopLeftIcon } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

export type DashboardView = "simulation" | "map"

export function SiteHeader({ title = "Live Simulation View", dashboardView, onDashboardViewChange }: {
  title?: string; dashboardView?: DashboardView; onDashboardViewChange?: (view: DashboardView) => void
}) {
  return <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
    <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mx-2 h-4 data-vertical:self-auto" />
      <h1 className="text-base font-medium">{title}</h1>
      {onDashboardViewChange && <ToggleGroup variant="outline" size="sm" className="ml-auto" aria-label="Dashboard view" value={[dashboardView ?? "simulation"]}
        onValueChange={(values) => values[0] && onDashboardViewChange(values[0] as DashboardView)}>
        <ToggleGroupItem value="simulation"><PanelsTopLeftIcon />Simulation</ToggleGroupItem>
        <ToggleGroupItem value="map"><MapIcon />Map</ToggleGroupItem>
      </ToggleGroup>}
    </div>
  </header>
}

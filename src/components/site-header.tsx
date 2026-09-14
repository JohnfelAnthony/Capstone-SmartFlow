import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { BoxIcon, PanelsTopLeftIcon } from "lucide-react"
import type { VisualizationMode } from "@/simulation/visualization-mode"

export function SiteHeader({
  title = "Live Simulation View",
  showVizToggle = true,
  visualizationMode = "2d",
  onVisualizationModeChange,
}: {
  title?: string
  showVizToggle?: boolean
  visualizationMode?: VisualizationMode
  onVisualizationModeChange?: (mode: VisualizationMode) => void
}) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator
          orientation="vertical"
          className="mx-2 h-4 data-vertical:self-auto"
        />
        <h1 className="text-base font-medium">{title}</h1>
        {showVizToggle && (
          <div className="sf-header-viz-toggle ml-auto" aria-label="Simulation visualization mode">
            <button
              className={visualizationMode === "2d" ? "active" : undefined}
              type="button"
              aria-pressed={visualizationMode === "2d"}
              onClick={() => onVisualizationModeChange?.("2d")}
            >
              <PanelsTopLeftIcon />
              2D
            </button>
            <button
              className={visualizationMode === "3d" ? "active" : undefined}
              type="button"
              aria-pressed={visualizationMode === "3d"}
              onClick={() => onVisualizationModeChange?.("3d")}
            >
              <BoxIcon />
              3D
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

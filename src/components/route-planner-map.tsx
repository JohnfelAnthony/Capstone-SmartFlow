import { useMemo } from "react"
import type { VisualNetwork } from "@/api/visual-network"
import { SimulationCanvas2D } from "@/components/simulation-canvas-2d"
import { createPresentationState, type PresentationState } from "@/simulation/presentation-state"
import type { PlannerFitRequest, PlannerOverlay } from "@/simulation/route-planner-overlay"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"

const ignoreSelection = () => undefined

export function RoutePlannerMap({ network, overlay, onRoadDirectionSelect, onRoadEndSelect, fitRequest }: {
  network: VisualNetwork
  overlay: PlannerOverlay
  onRoadDirectionSelect: (laneId: string) => void
  onRoadEndSelect: (endKey: string) => void
  fitRequest?: PlannerFitRequest
}) {
  const geometry = useMemo(() => normalizeSceneGeometry(network), [network])
  const presentation = useMemo<PresentationState>(() => {
    const base = createPresentationState(geometry)
    return { ...base, focus: "network", junctionId: null, overlays: { ...base.overlays, signals: false } }
  }, [geometry])
  return <div className="relative h-[clamp(18rem,45vh,40rem)] sm:h-[clamp(22rem,60vh,40rem)] overflow-hidden rounded-xl border">
    <SimulationCanvas2D frame={null} geometry={geometry} presentation={presentation} onSelect={ignoreSelection}
      staticMode plannerOverlay={overlay} onRoadDirectionSelect={onRoadDirectionSelect} onRoadEndSelect={onRoadEndSelect} fitRequest={fitRequest} />
  </div>
}

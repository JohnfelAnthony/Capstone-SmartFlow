import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { Popover } from "@base-ui/react/popover"
import { XIcon } from "lucide-react"
import type { VisualNetwork, VisualPoint } from "@/api/visual-network"
import { SimulationCanvas2D } from "@/components/simulation-canvas-2d"
import { Button } from "@/components/ui/button"
import type { EndStep } from "@/lib/route-ends"
import { mapToScreen, type MapCamera } from "@/simulation/map-navigation"
import { createPresentationState, type PresentationState } from "@/simulation/presentation-state"
import { plannerRemovePosition, type PlannerFitRequest, type PlannerMapAction, type PlannerOverlay } from "@/simulation/route-planner-overlay"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"

const ignoreSelection = () => undefined

export function RoutePlannerMap({ network, overlay, onAction, onRemoveEnd, popup, onDismiss, fitRequest }: {
  network: VisualNetwork
  overlay: PlannerOverlay
  onAction: (action: PlannerMapAction) => void
  onRemoveEnd: (step: EndStep) => void
  popup: { anchor: VisualPoint | null; title: string; content: ReactNode } | null
  onDismiss: () => void
  fitRequest?: PlannerFitRequest
}) {
  const [camera, setCamera] = useState<MapCamera>()
  const [mapElement, setMapElement] = useState<HTMLDivElement | null>(null)
  const popupAnchor = useRef<HTMLSpanElement>(null)
  const geometry = useMemo(() => normalizeSceneGeometry(network), [network])
  const presentation = useMemo<PresentationState>(() => {
    const base = createPresentationState(geometry)
    return { ...base, focus: "network", junctionId: null, overlays: { ...base.overlays, signals: false } }
  }, [geometry])
  const selectedFromList = popup !== null && popup.anchor === null
  useEffect(() => {
    if (selectedFromList) mapElement?.scrollIntoView({ block: "nearest" })
  }, [selectedFromList, mapElement])

  const anchor = camera && (popup?.anchor ? mapToScreen(popup.anchor, camera) : { x: camera.width / 2, y: camera.height / 2 })
  return <div className="route-planner-canvas" ref={setMapElement}>
    <SimulationCanvas2D frame={null} geometry={geometry} presentation={presentation} onSelect={ignoreSelection}
      staticMode plannerOverlay={overlay} onPlannerAction={onAction} onPlannerCamera={setCamera} fitRequest={fitRequest} />
    {camera && overlay.interactive ? overlay.ends.map(end => {
      const step = end.role
      if (step !== "start" && step !== "destination") return null
      const point = mapToScreen(end, camera)
      if (point.x < 0 || point.y < 0 || point.x > camera.width || point.y > camera.height) return null
      const position = plannerRemovePosition(point, camera)
      const label = `Remove ${step}`
      return <Button key={end.key} size="icon-sm" variant="outline" className="route-planner-remove-pin"
        aria-label={label} title={label} style={{ left: position.x, top: position.y }} onClick={() => onRemoveEnd(step)}>
        <XIcon />
      </Button>
    }) : null}
    {anchor ? <span ref={popupAnchor} className="route-planner-popup-anchor" style={{ left: anchor.x, top: anchor.y }} aria-hidden="true" /> : null}
    <Popover.Root open={Boolean(popup && anchor)} onOpenChange={(open, details) => {
      if (open) return
      // Map clicks manage their own dismissal. The click following pointerup
      // must not count as an outside press for the popup it just opened.
      const target = details.event.target
      if (details.reason === "outside-press" && target instanceof HTMLCanvasElement && mapElement?.contains(target)) {
        details.cancel()
        return
      }
      onDismiss()
    }}>
      <Popover.Portal>
        <Popover.Positioner anchor={popupAnchor} side="right" sideOffset={12} collisionPadding={10} className="z-50">
          <Popover.Popup className="route-planner-popup">
            <div className="flex items-start justify-between gap-2">
              <Popover.Title className="min-w-0 font-semibold leading-snug">{popup?.title}</Popover.Title>
              <Popover.Close render={<Button variant="ghost" size="icon-xs" aria-label="Dismiss map actions" />}><XIcon /></Popover.Close>
            </div>
            {popup?.content}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  </div>
}

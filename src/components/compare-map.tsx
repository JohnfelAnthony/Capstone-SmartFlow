import * as React from "react"
import { SimulationCanvas2D } from "@/components/simulation-canvas-2d"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EMPTY_VALUE } from "@/lib/display-format"
import { createPresentationState } from "@/simulation/presentation-state"
import type { SceneGeometry } from "@/simulation/scene-geometry"
import type { RenderFrame } from "@/simulation/frame-types"

const ignoreSelection = () => undefined

function phaseText(frame: RenderFrame, junctionId: string | null) {
  const control = (junctionId && frame.junction_controls?.[junctionId]) || Object.values(frame.junction_controls ?? {}).find((item) => item.selected_for_rl)
  if (!control) return EMPTY_VALUE
  if (control.mode === "first_come") return "No signal"
  if (control.mode === "all_way_stop") return "All-way stop"
  const text = control.phase.replaceAll("_", " ").toLowerCase()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** One recorded run drawn on the existing 2D map. Each map keeps its own camera; pan and zoom are not linked. */
export function CompareMap({ geometry, frame, title, runKey, junctionId = null, queue = null }: {
  geometry: SceneGeometry
  frame: RenderFrame | null
  title: string
  runKey: string
  junctionId?: string | null
  /** Sum of the four approach queues at the study junction for this time, from the condensed frames. */
  queue?: number | null
}) {
  const presentation = React.useMemo(() => createPresentationState(geometry, junctionId), [geometry, junctionId])
  return <Card className="compare-map-card">
    <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
    <CardContent className="compare-map-content">
      <div className="compare-map-viewport">
        <SimulationCanvas2D frame={frame} geometry={geometry} presentation={presentation} runKey={runKey} onSelect={ignoreSelection} />
        <dl className="compare-map-overlay" aria-label={`${title} at this time`}>
          {frame ? <>
            <div><dt>Phase</dt><dd>{phaseText(frame, junctionId)}</dd></div>
            <div><dt>Vehicles</dt><dd>{frame.vehicle_count}</dd></div>
            <div><dt>Queue</dt><dd>{queue === null ? EMPTY_VALUE : queue}</dd></div>
          </> : <div><dd>Loading…</dd></div>}
        </dl>
      </div>
    </CardContent>
  </Card>
}

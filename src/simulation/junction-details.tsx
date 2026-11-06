import type { CSSProperties } from "react"
import type * as React from "react"
import { ImageOffIcon } from "lucide-react"

import type { VisualPoint } from "@/api/visual-network"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress, ProgressLabel } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { sitePhoto } from "@/lib/study-sites"
import { cn } from "@/lib/utils"
import type { JunctionMetrics, RenderFrame } from "@/simulation/frame-types"
import { boundsOfPoints, walkSignalState, type SceneGeometry } from "@/simulation/scene-geometry"
import { approachDirection, closedLaneIds, departureDirection, junctionClosures, junctionShortLabel, laneDisplayLabel, phaseService, sharedStripsFromFrame, signalMovements, type SharedStrip } from "@/simulation/scene-summary"
import { timingLabel } from "@/simulation/render-frame-adapter"

// Same bands as the map: 0 clear · 1–4 low · 5–9 moderate · 10+ high.
const queueBand = (queue: number) => queue >= 10 ? "High" : queue >= 5 ? "Moderate" : queue >= 1 ? "Low" : "Clear"
const readable = (text: string | null | undefined) => text ? text.replaceAll("_", " ").toLowerCase().replace(/^\w/, letter => letter.toUpperCase()) : "Unavailable"
const seconds = (value: number | undefined) => value === undefined ? "—" : `${Math.round(value)} s`
const svgPoints = (points: readonly VisualPoint[]) => points.map(point => `${point.x},${point.y}`).join(" ")

function JunctionPhoto({ networkId, shortLabel }: { networkId: string; shortLabel: string }) {
  const photo = sitePhoto(networkId)
  if (!photo) return <div className="sf-junction-photo sf-junction-photo-empty"><ImageOffIcon className="size-5" />No photo yet</div>
  return <figure className="sf-junction-photo">
    <img src={photo} alt={`${shortLabel} intersection`} />
    <figcaption><strong>Enhanced site photo</strong></figcaption>
  </figure>
}

export function JunctionCard({ frame, geometry, junctionId, laneStreets }: {
  frame: RenderFrame | null; geometry: SceneGeometry; junctionId: string | null; laneStreets: Record<string, string>
}) {
  const junction = junctionId ? geometry.junctionById.get(junctionId) : undefined
  if (!junction || !junctionId) return null
  const shortLabel = junctionShortLabel(geometry, junctionId)
  const running = Boolean(frame && frame.status !== "stopped")
  const control = running ? frame?.junction_controls[junctionId] : undefined
  const metric = running ? frame?.junction_metrics?.[junctionId] : undefined
  const streets = junction.label.replace(/^J\d+:\s*/, "").split(" / ")
  const approaches = [...new Set(geometry.signalGroups.filter(group => group.kind === "vehicle" && group.junctionId === junctionId).map(group => group.lane_id))]
  const approachName = (laneId: string) => [approachDirection(geometry, laneId)?.replace("From ", "").replace(/^\w/, letter => letter.toUpperCase()), laneStreets[laneId]].filter(Boolean).join(" · ") || laneDisplayLabel(geometry, laneId)
  const roadName = (laneId: string) => laneStreets[laneId] ?? laneDisplayLabel(geometry, laneId)
  return <Card size="sm">
    <CardHeader><CardTitle>{streets.join(" × ")}</CardTitle></CardHeader>
    <CardContent className="flex flex-col gap-3">
      <JunctionPhoto networkId={geometry.networkId} shortLabel={shortLabel} />
      <Tabs defaultValue="phases">
        <TabsList className="w-full">
          <TabsTrigger value="phases">Signal phases</TabsTrigger>
          <TabsTrigger value="queues">Queue info</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
        </TabsList>
        <TabsContent value="phases"><SignalPhases control={control} frame={running ? frame ?? null : null} geometry={geometry} junctionId={junctionId} approachName={approachName} roadName={roadName} /></TabsContent>
        <TabsContent value="queues"><QueueInfo frame={running ? frame : null} geometry={geometry} junctionId={junctionId} approaches={approaches} approachName={approachName} laneStreets={laneStreets} /></TabsContent>
        <TabsContent value="performance"><Performance frame={running ? frame : null} approaches={approaches} metric={metric} /></TabsContent>
      </Tabs>
    </CardContent>
  </Card>
}

/** The junction's real roads and crossings; a served approach and its allowed turns light up with that lane's own engine state. */
function JunctionSignalMap({ frame, geometry, junctionId, approachName }: {
  frame: RenderFrame | null; geometry: SceneGeometry; junctionId: string; approachName: (laneId: string) => string
}) {
  if (!geometry.junctionById.get(junctionId)) return null
  const movements = signalMovements(geometry, junctionId, frame)
  const walkLit = walkSignalState(junctionId, frame) === "walk"
  const servedMovements = movements.filter(movement => movement.color === "green" || movement.color === "yellow")
  const summary = servedMovements.length ? `Served: ${servedMovements.map(movement => approachName(movement.laneId)).join(", ")}` : walkLit ? "Pedestrians crossing" : "No approach is being served"
  const closed = closedLaneIds(frame)
  const strips = sharedStripsFromFrame(frame).filter(strip => !closed.has(strip.sharedLane) && !closed.has(strip.keptLane))
  return <JunctionMiniMap geometry={geometry} junctionId={junctionId} movements={movements} closed={closed} walkLit={walkLit} summary={summary}
    strips={strips} shared={new Set(strips.map(strip => strip.sharedLane))} />
}

/**
 * The mini-intersection drawing, shared by the dashboard's Signal phases and the closure picker. Closed directions turn red and the turns
 * they remove are dashed. With `onToggleLane` every road direction is a button (Enter or Space as well as a click) that closes or reopens it.
 */
export function JunctionMiniMap({ geometry, junctionId, movements, closed, summary, walkLit = false, laneLabel, onToggleLane, shared, strips = [] }: {
  geometry: SceneGeometry; junctionId: string; movements: ReturnType<typeof signalMovements>; closed: ReadonlySet<string>; summary: string
  walkLit?: boolean; laneLabel?: (laneId: string) => string; onToggleLane?: (laneId: string) => void
  /** Pavements whose traffic uses half of the opposite pavement (hypothetical), drawn amber. */
  shared?: ReadonlySet<string>; strips?: SharedStrip[]
}) {
  const junction = geometry.junctionById.get(junctionId)
  if (!junction) return null
  const unavailable = new Set(junctionClosures(geometry, junctionId, closed).unavailableTurns.map(turn => `${turn.from}->${turn.to}`))
  const colorByLane = new Map(movements.map(movement => [movement.laneId, movement.color]))
  const roads = geometry.lanes.filter(lane => lane.kind === "road" && lane.junctionIds.includes(junctionId))
  // Frame what the arrows need, not the whole pavement, so a large junction zooms in as far as a small one.
  const arrowPoints = movements.flatMap(movement => movement.turns.flat())
  const bounds = boundsOfPoints(arrowPoints.length ? arrowPoints : junction.kerb, 0.12)
  const lineWidth = Math.max(bounds.max_x - bounds.min_x, bounds.max_y - bounds.min_y) / 70
  const flowStyle = { "--sf-turn-period": `${lineWidth * 4}px` } as CSSProperties
  const servedMovements = movements.filter(movement => movement.color === "green" || movement.color === "yellow")
  const pickProps = (laneId: string) => !onToggleLane ? {} : {
    role: "button", tabIndex: 0, "aria-pressed": closed.has(laneId) || Boolean(shared?.has(laneId)), "data-pickable": true,
    "aria-label": `${laneLabel?.(laneId) ?? laneId}: ${shared?.has(laneId) ? "closed, traffic shares the other side — press to reopen" : closed.has(laneId) ? "closed — press to reopen" : "open — press to close"}`,
    onClick: () => onToggleLane(laneId),
    onKeyDown: (event: React.KeyboardEvent) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onToggleLane(laneId) } },
  }
  return <svg className="sf-mini-intersection" viewBox={`${bounds.min_x} ${-bounds.max_y} ${bounds.max_x - bounds.min_x} ${bounds.max_y - bounds.min_y}`} role={onToggleLane ? "group" : "img"} aria-label={summary}>
    <defs>
      {["green", "yellow"].map(color => <marker key={color} id={`sf-turn-arrow-${color}`} viewBox="0 0 4 4" refX="1.5" refY="2" markerWidth="3.6" markerHeight="3.6" orient="auto">
        <path className="sf-mini-arrow" data-color={color} d="M0 0 L4 2 L0 4 Z" />
      </marker>)}
    </defs>
    <g transform="scale(1 -1)">
      <polygon className="sf-mini-road" points={svgPoints(junction.kerb)} />
      {roads.map(road => <polygon key={road.id} className="sf-mini-road" data-color={colorByLane.get(road.id)} data-closed={closed.has(road.id) || undefined} data-shared={shared?.has(road.id) || undefined} points={svgPoints(road.polygon)} {...pickProps(road.id)}>
        {onToggleLane ? <title>{laneLabel?.(road.id) ?? road.id}</title> : null}
      </polygon>)}
      {strips.flatMap(strip => Object.entries(strip.lanes).filter(([, points]) => points.length > 1).map(([laneId, points]) =>
        <polyline key={`strip-${laneId}`} className="sf-mini-share" data-shared-lane={laneId === strip.sharedLane || undefined} points={svgPoints(points)} strokeWidth={strip.width * 0.9}>
          <title>{laneId === strip.sharedLane ? "Closed direction, driving on half of the other pavement (hypothetical)" : "Open direction, narrowed to half of its pavement (hypothetical)"}</title>
        </polyline>))}
      {junction.crosswalks.flatMap(crosswalk => crosswalk.stripes.map((stripe, index) =>
        <polygon key={`${crosswalk.laneId}-${index}`} className="sf-mini-zebra" data-lit={walkLit} points={svgPoints(stripe)} />))}
      {movements.flatMap(movement => movement.turns.map((turn, index) => unavailable.has(`${movement.laneId}->${movement.turnTargets[index]}`)
        ? <polyline key={`${movement.laneId}-x${index}`} className="sf-mini-turn-unavailable" points={svgPoints(turn)} strokeWidth={lineWidth * 0.8}><title>Unavailable: closed</title></polyline> : null))}
      {servedMovements.flatMap(movement => movement.turns.map((turn, index) => {
        if (unavailable.has(`${movement.laneId}->${movement.turnTargets[index]}`)) return null
        const points = svgPoints(turn)
        return <g key={`${movement.laneId}-${index}`}>
          <polyline className="sf-mini-turn-casing" points={points} strokeWidth={lineWidth * 1.9} />
          <polyline className="sf-mini-turn" data-color={movement.color} points={points} strokeWidth={lineWidth} markerEnd={`url(#sf-turn-arrow-${movement.color})`} />
          <polyline className="sf-mini-turn-flow" points={points} strokeWidth={lineWidth * 0.5} strokeDasharray={`${lineWidth * 0.6} ${lineWidth * 3.4}`} style={flowStyle} />
        </g>
      }))}
    </g>
  </svg>
}

/** Closed roads at this junction in words: entries that stop, exits that are shut, and the turns lost with them. */
function ClosureNotes({ control, frame, geometry, junctionId, approachName, roadName }: {
  control: RenderFrame["junction_controls"][string] | undefined; frame: RenderFrame | null; geometry: SceneGeometry; junctionId: string
  approachName: (laneId: string) => string; roadName: (laneId: string) => string
}) {
  const { closedApproaches, closedExits, unavailableTurns } = junctionClosures(geometry, junctionId, closedLaneIds(frame))
  if (!unavailableTurns.length && !closedApproaches.length && !closedExits.length) return null
  const skipped = control?.mode === "signalized" && closedApproaches.length > 0
  const exitName = (laneId: string) => [roadName(laneId), departureDirection(geometry, laneId)?.toLowerCase()].filter(Boolean).join(" ")
  return <ul className="sf-closure-list" aria-label="Closed roads">
    {closedApproaches.map(laneId => <li key={`in-${laneId}`}>Closed to entry: {approachName(laneId)}{skipped ? " — the signal skips it once the vehicles already on it have left" : ""}</li>)}
    {closedExits.map(laneId => <li key={`out-${laneId}`}>Closed exit: {exitName(laneId)}</li>)}
    {unavailableTurns.length ? <li>{unavailableTurns.length} turn{unavailableTurns.length === 1 ? " is" : "s are"} unavailable: {unavailableTurns.map(turn => `${approachName(turn.from)} → ${exitName(turn.to)}`).join("; ")}</li> : null}
  </ul>
}

function SignalPhases({ control, frame, geometry, junctionId, approachName, roadName }: {
  control: RenderFrame["junction_controls"][string] | undefined; frame: RenderFrame | null; geometry: SceneGeometry; junctionId: string
  approachName: (laneId: string) => string; roadName: (laneId: string) => string
}) {
  const signalMap = <><JunctionSignalMap frame={frame} geometry={geometry} junctionId={junctionId} approachName={approachName} />
    <ClosureNotes control={control} frame={frame} geometry={geometry} junctionId={junctionId} approachName={approachName} roadName={roadName} /></>
  const unsignalledNote = !control ? "Start a simulation to see the signal phases."
    : control.mode === "first_come" ? "No signal — first come, first served."
    : control.mode === "all_way_stop" ? "All-way stop: this junction has no signal phases." : null
  if (!control || unsignalledNote) return <div className="flex flex-col gap-3">{signalMap}<p className="sf-junction-note">{unsignalledNote}</p></div>
  const current = phaseService(control.phase)
  const stageLength = (control.elapsed_seconds ?? 0) + (control.remaining_seconds ?? 0)
  const isRlControlled = Boolean(control.external_control)
  return <div className="flex flex-col gap-3">
    <Progress value={stageLength > 0 ? (control.elapsed_seconds ?? 0) / stageLength * 100 : 0}>
      <ProgressLabel>Current: {current ? `${readable(current)} ${control.stage ?? ""}` : "All red (clearance)"}</ProgressLabel>
      <span className="ml-auto text-sm tabular-nums">{seconds(control.elapsed_seconds)} / {seconds(stageLength)}</span>
    </Progress>
    {signalMap}
    <p className="sf-junction-note">
      {isRlControlled ? `RL-timed green: ${seconds(control.minimum_green)}–${seconds(control.maximum_green)}` : `Plan green: ${seconds(control.green_seconds)}`}
      {` · yellow ${seconds(control.yellow_seconds)} · all-red ${seconds(control.all_red_seconds)}`}
    </p>
    <p className="sf-junction-note">{timingLabel(control)}</p>
  </div>
}

function QueueInfo({ frame, geometry, junctionId, approaches, approachName, laneStreets }: {
  frame: RenderFrame | null; geometry: SceneGeometry; junctionId: string; approaches: string[]
  approachName: (laneId: string) => string; laneStreets: Record<string, string>
}) {
  const queues = approaches.map(laneId => ({ laneId, queue: frame?.lane_metrics?.[laneId]?.queue }))
  const barScale = Math.max(10, ...queues.map(item => item.queue ?? 0))
  const junctionLanes = geometry.lanes.filter(lane => lane.kind === "road" && lane.junctionIds.includes(junctionId))
  const restrictions = frame ? junctionLanes.flatMap(lane => {
    const closed = frame.visual.closed_lanes.includes(lane.id) || frame.lane_metrics?.[lane.id]?.closed
    const factor = frame.visual.slow_lanes[lane.id] ?? frame.lane_metrics?.[lane.id]?.speed_factor
    const name = laneStreets[lane.id] ?? laneDisplayLabel(geometry, lane.id)
    return closed ? [`${name}: closed to new entry`] : factor !== undefined && factor < 1 ? [`${name}: ${Math.round(factor * 100)}% speed`] : []
  }) : []
  if (!approaches.length) return <p className="sf-junction-note">No approaches available.</p>
  return <div className="flex flex-col gap-3">
    <p className="sf-junction-note">Waiting vehicles per approach</p>
    {queues.map(({ laneId, queue }) =>
      <Progress key={laneId} value={queue === undefined ? 0 : queue / barScale * 100} className="sf-queue-bar" data-band={queue === undefined ? undefined : queueBand(queue)}>
        <ProgressLabel title={laneId}>{approachName(laneId)}</ProgressLabel>
        <span className="ml-auto text-sm tabular-nums">{queue === undefined ? "—" : `${queue} · ${queueBand(queue)}`}</span>
      </Progress>)}
    {restrictions.length ? <div className="flex flex-col gap-1">{restrictions.map(text => <Badge key={text} variant="destructive">{text}</Badge>)}</div> : null}
    {!frame ? <p className="sf-junction-note">Start a simulation to see live queues.</p> : null}
  </div>
}

function Performance({ frame, approaches, metric }: { frame: RenderFrame | null; approaches: string[]; metric: JunctionMetrics | undefined }) {
  const lanes = approaches.map(id => frame?.lane_metrics?.[id]).filter((lane): lane is NonNullable<typeof lane> => Boolean(lane))
  const movingVehicles = lanes.reduce((sum, lane) => sum + lane.vehicles, 0)
  // Vehicle-weighted mean of measured lane speeds; unavailable when no vehicle is on the incoming lanes.
  const meanSpeed = movingVehicles > 0 ? lanes.reduce((sum, lane) => sum + lane.mean_speed_mps * lane.vehicles, 0) / movingVehicles * 3.6 : undefined
  const values = [
    { label: "Queue now", value: metric ? `${metric.queue} veh` : "—" },
    { label: "Vehicles passed since start", value: metric ? `${metric.vehicle_passages}` : "—" },
    { label: "Waiting pedestrians", value: metric ? `${metric.waiting_pedestrians}` : "—" },
    { label: "Mean incoming speed", value: meanSpeed === undefined ? "—" : `${meanSpeed.toFixed(1)} km/h` },
  ]
  return <div className="flex flex-col gap-3">
    <dl className="sf-performance-grid">
      {values.map(item => <div key={item.label} className={cn(!frame && "opacity-70")}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
    </dl>
    <p className="sf-junction-note">Network-wide wait, throughput and travel time are in the KPI row.</p>
  </div>
}

import * as React from "react"
import { ArrowDownIcon, ArrowLeftIcon, ArrowRightIcon, ArrowUpIcon, ImageOffIcon, PersonStandingIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress, ProgressLabel } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import type { JunctionMetrics, RenderFrame } from "@/simulation/frame-types"
import type { SceneGeometry } from "@/simulation/scene-geometry"
import { approachDirection, junctionShortLabel, laneDisplayLabel, phaseService } from "@/simulation/scene-summary"
import { timingLabel } from "@/simulation/render-frame-adapter"

// shortcut: placeholder until field photos exist; drop J1.jpg / J2.jpg into public/assets/junctions to replace it per junction.
const PLACEHOLDER_PHOTO = "/assets/junctions/placeholder.jpg"
const PLACEHOLDER_CREDIT = "Placeholder photo — not the study site"
// CC BY 3.0 requires author, source and licence: Tulip Drive–Quimpo Blvd, Davao City (2012), Wikimedia Commons.
const PLACEHOLDER_ATTRIBUTION = { author: "Kenneth Rangas", source: "https://commons.wikimedia.org/wiki/File:Tulip_Drive_-_Quimpo_Blvd_Intersection_-_panoramio.jpg", license: "CC BY 3.0", licenseUrl: "https://creativecommons.org/licenses/by/3.0" }

const SERVICE_DISPLAY: Record<string, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  north: { label: "North", icon: ArrowDownIcon },
  east: { label: "East", icon: ArrowLeftIcon },
  south: { label: "South", icon: ArrowUpIcon },
  west: { label: "West", icon: ArrowRightIcon },
  pedestrian: { label: "Pedestrians", icon: PersonStandingIcon },
}

// Same bands as the map: 0 clear · 1–4 low · 5–9 moderate · 10+ high.
const queueBand = (queue: number) => queue >= 10 ? "High" : queue >= 5 ? "Moderate" : queue >= 1 ? "Low" : "Clear"
const readable = (text: string | null | undefined) => text ? text.replaceAll("_", " ").toLowerCase().replace(/^\w/, letter => letter.toUpperCase()) : "Unavailable"
const seconds = (value: number | undefined) => value === undefined ? "—" : `${Math.round(value)} s`

export function NetworkMapCard({ geometry, junctionId, onFocus }: { geometry: SceneGeometry; junctionId: string | null; onFocus: (id: string) => void }) {
  const bounds = geometry.bounds
  const width = bounds.max_x - bounds.min_x, height = bounds.max_y - bounds.min_y
  const span = Math.max(width, height), padding = span * .08
  const point = (position: { x: number; y: number }) => `${position.x - bounds.min_x},${bounds.max_y - position.y}`
  return <Card size="sm">
    <CardHeader>
      <CardTitle>Network map</CardTitle>
      <CardDescription>{geometry.junctions.length} signalized junctions · click one to select it</CardDescription>
    </CardHeader>
    <CardContent>
      <svg viewBox={`${-padding} ${-padding} ${width + padding * 2} ${height + padding * 2}`} className="sf-network-map" aria-label="Network map">
        {geometry.lanes.filter(lane => lane.kind === "road").map(lane => <polyline key={lane.id} points={lane.centerline.map(point).join(" ")} fill="none" className="sf-network-map-road" strokeWidth={Math.max(lane.width, span * .012)} />)}
        {geometry.junctions.map(junction => {
          const active = junction.id === junctionId
          return <g key={junction.id} role="button" tabIndex={0} aria-label={`Select ${junction.label}`} aria-pressed={active} className="sf-network-map-junction" data-active={active}
            onClick={() => onFocus(junction.id)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onFocus(junction.id) } }}>
            <title>{junction.label}</title>
            <circle cx={junction.center.x - bounds.min_x} cy={bounds.max_y - junction.center.y} r={span * .06} />
            <text x={junction.center.x - bounds.min_x} y={bounds.max_y - junction.center.y} textAnchor="middle" dominantBaseline="central" fontSize={span * .06}>{junctionShortLabel(geometry, junction.id)}</text>
          </g>
        })}
      </svg>
    </CardContent>
  </Card>
}

function JunctionPhoto({ shortLabel }: { shortLabel: string }) {
  const sources = React.useMemo(() => [`/assets/junctions/${shortLabel}.jpg`, PLACEHOLDER_PHOTO], [shortLabel])
  const [sourceIndex, setSourceIndex] = React.useState(0)
  const source = sources[sourceIndex]
  if (!source) return <div className="sf-junction-photo sf-junction-photo-empty"><ImageOffIcon className="size-5" />No photo yet</div>
  return <figure className="sf-junction-photo">
    <img src={source} alt={source === PLACEHOLDER_PHOTO ? "Placeholder intersection photo" : `${shortLabel} junction`} onError={() => setSourceIndex(index => index + 1)} />
    {source === PLACEHOLDER_PHOTO ? <figcaption>
      <strong>{PLACEHOLDER_CREDIT}</strong>
      <span>Photo: <a href={PLACEHOLDER_ATTRIBUTION.source} target="_blank" rel="noreferrer">{PLACEHOLDER_ATTRIBUTION.author}</a>, <a href={PLACEHOLDER_ATTRIBUTION.licenseUrl} target="_blank" rel="noreferrer">{PLACEHOLDER_ATTRIBUTION.license}</a></span>
    </figcaption> : null}
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
  return <Card size="sm">
    <CardHeader className="grid-cols-[auto_1fr] items-center gap-x-3">
      <span className="sf-junction-badge">{shortLabel}</span>
      <div className="min-w-0">
        <CardTitle className="truncate">{streets.join(" × ")}</CardTitle>
        <CardDescription>{control ? readable(control.controller) : "Not running"}</CardDescription>
      </div>
    </CardHeader>
    <CardContent className="flex flex-col gap-3">
      <JunctionPhoto key={shortLabel} shortLabel={shortLabel} />
      <Tabs defaultValue="phases">
        <TabsList className="w-full">
          <TabsTrigger value="phases">Signal phases</TabsTrigger>
          <TabsTrigger value="queues">Queue info</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
        </TabsList>
        <TabsContent value="phases"><SignalPhases control={control} /></TabsContent>
        <TabsContent value="queues"><QueueInfo frame={running ? frame : null} geometry={geometry} junctionId={junctionId} approaches={approaches} approachName={approachName} laneStreets={laneStreets} /></TabsContent>
        <TabsContent value="performance"><Performance frame={running ? frame : null} approaches={approaches} metric={metric} /></TabsContent>
      </Tabs>
    </CardContent>
  </Card>
}

function SignalPhases({ control }: { control: RenderFrame["junction_controls"][string] | undefined }) {
  if (!control) return <p className="sf-junction-note">Start a simulation to see the signal phases.</p>
  if (control.mode === "all_way_stop") return <p className="sf-junction-note">All-way stop: this junction has no signal phases.</p>
  const current = phaseService(control.phase)
  const stageLength = (control.elapsed_seconds ?? 0) + (control.remaining_seconds ?? 0)
  const isRlControlled = Boolean(control.external_control)
  return <div className="flex flex-col gap-3">
    <Progress value={stageLength > 0 ? (control.elapsed_seconds ?? 0) / stageLength * 100 : 0}>
      <ProgressLabel>Current: {current ? `${SERVICE_DISPLAY[current]?.label ?? current} ${control.stage ?? ""}` : "All red (clearance)"}</ProgressLabel>
      <span className="ml-auto text-sm tabular-nums">{seconds(control.elapsed_seconds)} / {seconds(stageLength)}</span>
    </Progress>
    <div className="sf-phase-grid">
      {(control.phase_order ?? []).map((service, index) => {
        const display = SERVICE_DISPLAY[service] ?? { label: service, icon: ArrowUpIcon }
        const Icon = display.icon
        return <div key={service} className="sf-phase-card" data-active={service === current} data-stage={service === current ? control.stage : undefined}>
          <span className="sf-phase-number">{index + 1}</span>
          <Icon className="size-5" />
          <span>{display.label}</span>
        </div>
      })}
    </div>
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
  if (!approaches.length) return <p className="sf-junction-note">No signalized approaches.</p>
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

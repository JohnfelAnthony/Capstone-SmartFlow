import * as React from "react"
import { CarFrontIcon, CrosshairIcon, LayersIcon, MapIcon, MaximizeIcon, MinimizeIcon, PanelRightIcon, PersonStandingIcon, RotateCcwIcon, XIcon } from "lucide-react"
import { getVisualNetwork } from "@/api/visual-network"
import { SimulationCanvas2D } from "@/components/simulation-canvas-2d"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldLabel, FieldSet, FieldLegend } from "@/components/ui/field"
import { Progress, ProgressLabel } from "@/components/ui/progress"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { RenderFrame } from "@/simulation/frame-types"
import { normalizeSceneGeometry, selectionKey, type SceneGeometry, type Selection } from "@/simulation/scene-geometry"
import { createPresentationState, presentationReducer, type PresentationState, type OverlaySettings } from "@/simulation/presentation-state"
import { timingLabel } from "@/simulation/render-frame-adapter"
import { approachDirection, junctionShortLabel, laneDisplayLabel } from "@/simulation/scene-summary"
import { SimulationScene3D } from "@/simulation/SimulationScene3D"

type PerformanceSample = { fps: number; p95FrameMs: number; drawCalls: number }
const value = (number: number | undefined, unit = "") => number === undefined ? "Unavailable" : `${number.toFixed(1)}${unit}`
const OVERLAY_LABELS: Record<keyof OverlaySettings, string> = { signals: "Signals", labels: "Labels", queues: "Queue counts", heatmap: "Queue heatmap", arrows: "Flow direction", connectors: "Turn paths", context: "Street context" }

const readable = (text: string | null | undefined) => text ? text.replaceAll("_", " ").toLowerCase().replace(/^\w/, letter => letter.toUpperCase()) : "Unavailable"
const clock = (seconds: number | undefined) => seconds === undefined ? "--:--" : `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`
// Same bands as the map legend: 0 clear · 1–4 low · 5–9 moderate · 10+ high.
const queueBand = (queue: number) => queue >= 10 ? "High" : queue >= 5 ? "Moderate" : queue >= 1 ? "Low" : "Clear"

function ChoiceSelect({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: Array<{ value: string; label: string }>; onChange: (value: string) => void }) {
  return <Field className="sf-scene-field"><FieldLabel htmlFor={id} className="sr-only">{label}</FieldLabel>
    <Select items={options} value={value} onValueChange={next => next !== null && onChange(next)}>
      <SelectTrigger id={id} size="sm" className="w-full"><SelectValue /></SelectTrigger>
      <SelectContent><SelectGroup>{options.map(option => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectGroup></SelectContent>
    </Select>
  </Field>
}

export function JunctionPanel({ frame, geometry, presentation, onClose, children }: { frame: RenderFrame | null; geometry: SceneGeometry; presentation: PresentationState; onClose?: () => void; children?: React.ReactNode }) {
  const id = presentation.selection?.kind === "junction" ? presentation.selection.id : presentation.junctionId
  const control = id ? frame?.junction_controls[id] : undefined
  const metric = id ? frame?.junction_metrics?.[id] : undefined
  const label = id ? geometry.junctionById.get(id)?.label ?? id : "No junction"
  const selection = presentation.selection
  const lane = selection?.kind === "lane" ? frame?.lane_metrics?.[selection.id] : undefined
  const entity = selection?.kind === "vehicle" ? frame?.vehicles.find(vehicle => vehicle.id === selection.id) : selection?.kind === "pedestrian" ? frame?.pedestrians.find(person => person.id === selection.id) : undefined
  const stopped = !frame || frame.status === "stopped"
  const allWayStop = control?.mode === "all_way_stop"
  const approaches = id ? [...new Set(geometry.signalGroups.filter(group => group.kind === "vehicle" && group.junctionId === id).map(group => group.lane_id))]
    .map(laneId => ({ laneId, queue: stopped ? undefined : frame?.lane_metrics?.[laneId]?.queue })) : []
  const barScale = Math.max(10, ...approaches.map(approach => approach.queue ?? 0))
  return <aside id="scene-inspector" className="sf-scene-inspector" aria-label="Junction details">
    <div className="sf-scene-inspector-heading"><strong>{id ? `${junctionShortLabel(geometry, id)} junction` : "Junction"}</strong>{onClose ? <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close junction panel"><XIcon /></Button> : null}</div>
    <section className="sf-scene-controller-detail">
      <h3>{label}</h3>
      <Badge variant="secondary">{stopped ? "Not running" : readable(control?.controller)}</Badge>
      <div className="sf-scene-section-label">Now serving</div>
      <p className="sf-scene-service">{stopped ? "—" : allWayStop ? "All-way stop (no signal)" : readable(control?.phase)}</p>
      <p>{stopped ? "Start the simulation to see signal timing." : timingLabel(control)}</p>
    </section>
    <section className="sf-scene-queues">
      <div className="sf-scene-section-label">Waiting vehicles per approach</div>
      {approaches.length ? approaches.map(({ laneId, queue }) =>
        <Progress key={laneId} value={queue === undefined ? 0 : queue / barScale * 100} className="sf-queue-bar" data-band={queue === undefined ? undefined : queueBand(queue)}>
          <ProgressLabel title={laneDisplayLabel(geometry, laneId)}>{approachDirection(geometry, laneId) ?? laneDisplayLabel(geometry, laneId)}</ProgressLabel>
          <span className="ml-auto text-sm tabular-nums">{queue === undefined ? "—" : `${queue} · ${queueBand(queue)}`}</span>
        </Progress>) : <p>No signalized approaches.</p>}
      <dl className="sf-scene-measurements"><div><dt>Total queue</dt><dd>{stopped ? "—" : metric?.queue ?? "—"}</dd></div><div><dt>Waiting pedestrians</dt><dd>{stopped ? "—" : metric?.waiting_pedestrians ?? "—"}</dd></div></dl>
    </section>
    {selection && selection.kind !== "junction" ? <section className="sf-selected-detail">
      <div className="sf-scene-section-label">Selected {selection.kind}</div>
      <h4>{selection.kind === "lane" ? laneDisplayLabel(geometry, selection.id) : selection.id}</h4>
      {selection.kind === "lane" ? <><dl className="sf-scene-measurements"><div><dt>Queue</dt><dd>{lane?.queue ?? "—"}</dd></div><div><dt>Mean speed</dt><dd>{value(lane?.mean_speed_mps === undefined ? undefined : lane.mean_speed_mps * 3.6, " km/h")}</dd></div></dl><p>{lane ? lane.closed ? "Closed to new entry" : lane.speed_factor < 1 ? `Speed limited to ${Math.round(lane.speed_factor * 100)}%` : "Open to traffic" : "Restrictions unavailable"}</p></> : <><p>Class: {!entity ? "Unavailable" : "visual_type" in entity ? String(entity.visual_type) : "Pedestrian"}</p><dl className="sf-scene-measurements"><div><dt>Speed</dt><dd>{value(entity?.speed === undefined ? undefined : entity.speed * 3.6, " km/h")}</dd></div><div><dt>Waiting</dt><dd>{value(entity?.wait_time, " s")}</dd></div></dl><p>State: {entity ? entity.stopped ? "Waiting / stopped" : "Moving" : "Not in displayed population"}</p></>}
    </section> : null}
    <details className="sf-scene-technical"><summary>Technical details</summary>{children}<code>{id}</code><p>Elapsed stage: {stopped || allWayStop ? "Unavailable" : value(control?.elapsed_seconds, " s")}</p><p>Pending request: {stopped || control?.pending_service === undefined ? "Unavailable" : control.pending_service ?? "None recorded"}</p></details>
  </aside>
}

const Minimap = React.memo(function Minimap({ geometry, junctionId, onFocus }: { geometry: SceneGeometry; junctionId: string | null; onFocus: (id: string) => void }) {
  const bounds = geometry.bounds
  const width = bounds.max_x - bounds.min_x, height = bounds.max_y - bounds.min_y
  const padding = Math.max(width, height) * .07
  const point = (position: { x: number; y: number }) => `${position.x - bounds.min_x},${bounds.max_y - position.y}`
  return <div className="sf-scene-minimap"><span>NETWORK <small>{geometry.junctions.length} junctions</small></span><svg viewBox={`${-padding} ${-padding} ${width + padding * 2} ${height + padding * 2}`} aria-label="Network minimap">
    {geometry.lanes.map(lane => <polyline key={lane.id} points={lane.centerline.map(point).join(" ")} fill="none" className="sf-minimap-road" strokeWidth={Math.max(lane.width, 2)} />)}
    {geometry.junctions.map((junction, index) => <g key={junction.id} role="button" tabIndex={0} aria-label={`Focus ${junction.label}`} aria-pressed={junction.id === junctionId} onClick={() => onFocus(junction.id)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onFocus(junction.id) } }} className="sf-minimap-junction" data-active={junction.id === junctionId}>
      <title>{junction.label}</title><circle cx={junction.center.x - bounds.min_x} cy={bounds.max_y - junction.center.y} r={Math.max(width, height) * .075} /><text x={junction.center.x - bounds.min_x} y={bounds.max_y - junction.center.y} textAnchor="middle" dominantBaseline="central" fontSize={Math.max(width, height) * .10}>{`J${index + 1}`}</text>
    </g>)}
  </svg></div>
})

function Workspace({ geometry, frame, controlledJunction, mode, runKey, seekRevision = 0, title, onUnavailable, onPerformanceSample }: { geometry: SceneGeometry; frame: RenderFrame | null; controlledJunction?: string | null; mode: string; runKey: string; seekRevision?: number; title: string; onUnavailable: (message: string) => void; onPerformanceSample?: (sample: PerformanceSample) => void }) {
  const [presentation, dispatch] = React.useReducer(presentationReducer, geometry, network => createPresentationState(network, controlledJunction))
  const [expanded, setExpanded] = React.useState(false)
  const [failure, setFailure] = React.useState("")
  const [inspectorPreference, setInspectorPreference] = React.useState<boolean | null>(null)
  const [layersOpen, setLayersOpen] = React.useState(false)
  const is2D = mode === "2d" || Boolean(failure)
  const inspectorOpen = inspectorPreference ?? true
  const host = React.useRef<HTMLDivElement | null>(null)
  const inspectorToggle = React.useRef<HTMLButtonElement | null>(null)
  const previous = React.useRef({ runKey, seekRevision, time: frame?.time ?? 0, status: frame?.status, controlledJunction })
  const select = React.useCallback((selection: Selection | null) => { dispatch({ type: "select", selection }); if (selection) setInspectorPreference(true) }, [])
  const focus = React.useCallback((id: string) => { dispatch({ type: "focus", focus: "junction", junctionId: id }); dispatch({ type: "select", selection: { kind: "junction", id } }) }, [])
  const fallback = React.useCallback((message: string) => { setFailure(message); onUnavailable(message) }, [onUnavailable])
  React.useEffect(() => {
    const old = previous.current
    const newRun = runKey !== old.runKey, rewound = (frame?.time ?? 0) < old.time
    const hasStopped = frame?.status === "stopped" && old.status !== "stopped"
    if (newRun || controlledJunction !== old.controlledJunction || hasStopped) dispatch({ type: "reset", junctionId: controlledJunction })
    if (frame) {
      const coverage = frame.render_coverage
      const limited = presentation.selection?.kind === "pedestrian" ? Boolean(coverage && coverage.pedestrians.shown < coverage.pedestrians.total) : Boolean(coverage && coverage.vehicles.shown < coverage.vehicles.total)
      dispatch({ type: "entities", vehicleIds: frame.vehicles.map(vehicle => vehicle.id), pedestrianIds: frame.pedestrians.map(person => person.id), coverageLimited: limited })
    }
    if (rewound || seekRevision !== old.seekRevision) dispatch({ type: "seek" })
    previous.current = { runKey, seekRevision, time: frame?.time ?? 0, status: frame?.status, controlledJunction }
  }, [frame, runKey, seekRevision, controlledJunction, presentation.selection?.kind])
  React.useEffect(() => {
    const change = () => setExpanded(document.fullscreenElement === host.current)
    document.addEventListener("fullscreenchange", change)
    return () => document.removeEventListener("fullscreenchange", change)
  }, [])
  React.useEffect(() => {
    if (!expanded) return
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape" && !document.fullscreenElement) setExpanded(false) }
    document.addEventListener("keydown", escape)
    return () => document.removeEventListener("keydown", escape)
  }, [expanded])
  async function fullscreen() {
    if (document.fullscreenElement) { await document.exitFullscreen(); return }
    if (expanded) { setExpanded(false); return }
    try { if (host.current?.requestFullscreen) await host.current.requestFullscreen(); else setExpanded(true) } catch { setExpanded(true) }
  }
  const selectedKey = selectionKey(presentation.selection)
  const coverage = frame?.render_coverage
  const displayedPopulationComplete = coverage ? !coverage.limited : Boolean(frame && frame.vehicles.length >= frame.vehicle_count && frame.pedestrians.length >= frame.pedestrian_count)
  const entities = inspectorOpen ? [
    ...geometry.junctions.map(junction => ({ kind: "junction" as const, id: junction.id, label: junction.label })),
    ...geometry.lanes.map(lane => ({ kind: "lane" as const, id: lane.id, label: laneDisplayLabel(geometry, lane.id) })),
    ...(frame?.vehicles ?? []).map(vehicle => ({ kind: "vehicle" as const, id: vehicle.id, label: `${vehicle.visual_type} ${vehicle.id}` })),
    ...(frame?.pedestrians ?? []).map(person => ({ kind: "pedestrian" as const, id: person.id, label: person.id })),
  ] : []
  return <div ref={host} className={cn("sf-scene-workspace", expanded && "sf-scene-expanded")} data-mode={is2D ? "2d" : "3d"} data-focus={presentation.focus} data-junction={presentation.junctionId} data-selection={selectedKey}>
    <header className="sf-scene-heading">
      <div className="sf-scene-title"><strong>{title}</strong></div>
      <div className="sf-scene-heading-actions"><Badge variant={frame?.status === "running" ? "secondary" : "outline"}>{frame?.playback.active ? "Replay" : frame?.status ?? "idle"}</Badge><span className="sf-scene-clock" title="Simulation time">{clock(frame?.time)}</span><Button variant="outline" size="sm" onClick={() => void fullscreen()} aria-label={expanded ? "Exit fullscreen" : "Enter fullscreen"}>{expanded ? <MinimizeIcon data-icon="inline-start" /> : <MaximizeIcon data-icon="inline-start" />}{expanded ? "Exit" : "Expand"}</Button></div>
    </header>
    <div className="sf-scene-toolbar">
      <ToggleGroup value={[presentation.focus]} onValueChange={values => { const next = values[0]; if (next === "junction" || next === "network" || next === "follow") dispatch({ type: "focus", focus: next }) }} size="sm" variant="outline" aria-label="Camera focus">
        <ToggleGroupItem value="junction" aria-label="Junction focus"><CrosshairIcon data-icon="inline-start" />Junction</ToggleGroupItem><ToggleGroupItem value="network" aria-label="Network overview"><MapIcon data-icon="inline-start" />Network</ToggleGroupItem><ToggleGroupItem value="follow" disabled={presentation.selection?.kind !== "vehicle"} title="Select a vehicle on the map to follow it">Follow vehicle</ToggleGroupItem>
      </ToggleGroup>
      <ChoiceSelect id="scene-junction" label="Junction" value={presentation.junctionId ?? ""} onChange={focus} options={geometry.junctions.map(junction => ({ value: junction.id, label: /^J\d+:/.test(junction.label) ? junction.label : `${junctionShortLabel(geometry, junction.id)} · ${junction.label}` }))} />
      <div className="sf-scene-toolbar-actions"><Button variant="ghost" size="icon-sm" onClick={() => dispatch({ type: "reset", junctionId: controlledJunction })} aria-label="Reset view" title="Reset view"><RotateCcwIcon /></Button><Button variant={layersOpen ? "secondary" : "outline"} size="sm" aria-expanded={layersOpen} aria-controls="scene-layers" onClick={() => setLayersOpen(open => !open)}><LayersIcon data-icon="inline-start" />Layers</Button><Button ref={inspectorToggle} variant={inspectorOpen ? "secondary" : "outline"} size="sm" aria-expanded={inspectorOpen} aria-controls="scene-inspector" onClick={() => setInspectorPreference(!inspectorOpen)}><PanelRightIcon data-icon="inline-start" />Junction panel</Button></div>
    </div>
    {layersOpen ? <div id="scene-layers" className="sf-scene-layer-panel"><FieldSet><FieldLegend className="sr-only">Scene overlays</FieldLegend><div className="sf-scene-toggles">{Object.entries(presentation.overlays).map(([key, enabled]) => <Field key={key} orientation="horizontal"><Checkbox id={`overlay-${key}`} checked={enabled} onCheckedChange={checked => dispatch({ type: "overlay", overlay: key as keyof OverlaySettings, enabled: checked })} /><FieldLabel htmlFor={`overlay-${key}`}>{OVERLAY_LABELS[key as keyof OverlaySettings]}</FieldLabel></Field>)}</div></FieldSet>{!is2D ? <ChoiceSelect id="scene-quality" label="Quality" value={presentation.quality} onChange={next => dispatch({ type: "quality", quality: next === "enhanced" ? "enhanced" : "laptop" })} options={[{ value: "laptop", label: "Laptop quality" }, { value: "enhanced", label: "Enhanced shadows" }]} /> : null}</div> : null}
    {failure ? <Alert><AlertDescription>{failure}</AlertDescription></Alert> : null}
    {presentation.notice ? <p className="sf-scene-notice" role="status">{presentation.notice}</p> : null}
    <div className="sf-scene-layout" data-inspector={inspectorOpen}>
      <div className="sf-scene-viewport">
        {is2D ? <SimulationCanvas2D frame={frame} geometry={geometry} presentation={presentation} runKey={runKey} onSelect={select} onPerformanceSample={onPerformanceSample} /> : <SimulationScene3D frame={frame} geometry={geometry} presentation={presentation} runKey={runKey} onSelect={select} onUnavailable={fallback} onPerformanceSample={onPerformanceSample} />}
        <Minimap geometry={geometry} junctionId={presentation.junctionId} onFocus={focus} />
      </div>
      {inspectorOpen ? <JunctionPanel frame={frame} geometry={geometry} presentation={presentation} onClose={() => { setInspectorPreference(false); inspectorToggle.current?.focus() }}><Field className="sf-scene-object-field"><FieldLabel htmlFor="scene-object">Find a vehicle, lane or junction</FieldLabel><select id="scene-object" value={selectedKey} onChange={event => { const item = entities.find(entity => selectionKey(entity) === event.target.value); select(item ? { kind: item.kind, id: item.id } : null) }}><option value="">Choose an object or click the map</option>{entities.map(entity => <option key={selectionKey(entity)} value={selectionKey(entity)}>{entity.kind}: {entity.label}</option>)}</select></Field></JunctionPanel> : null}
    </div>
    <footer className="sf-scene-footer"><div className="sf-scene-population"><span><CarFrontIcon aria-hidden="true" /><b>{coverage?.vehicles.total ?? frame?.vehicle_count ?? 0}</b> vehicles</span><span><PersonStandingIcon aria-hidden="true" /><b>{coverage?.pedestrians.total ?? frame?.pedestrian_count ?? 0}</b> pedestrians</span>{coverage?.limited ? <span className="sf-scene-muted">Showing {coverage.vehicles.shown}/{coverage.vehicles.total} vehicles · {coverage.pedestrians.shown}/{coverage.pedestrians.total} pedestrians ({coverage.reason?.replaceAll("_", " ")})</span> : <span className="sf-scene-muted">{displayedPopulationComplete ? "All displayed" : "Display coverage unavailable"}</span>}</div><span className="sf-scene-source">Illustrative geometry · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a></span></footer>
    <details className="sf-scene-options"><summary>Map legend</summary><div className="sf-scene-legend"><span><i className="sf-legend-dot sf-legend-tricycle" />Green Tagum tricycle</span><span><i className="sf-legend-dot sf-legend-pedestrian" />Pedestrian</span><span><i className="sf-legend-dot sf-legend-selected" />Selected object</span><span><i className="sf-legend-dot sf-legend-closed" />Closed entry</span><span><i className="sf-legend-dot sf-legend-slow" />Reduced speed</span></div><p>Cars, motorcycles, tricycles, buses and trucks use distinct silhouettes. Signals: red / yellow / green; dark lamps are unlit.</p><p>Queue bands: 0 clear · 1–4 low · 5–9 moderate · 10+ high. Counts come from engine telemetry, including vehicles outside the visible map.</p><p>Buildings, greenery and dashed pedestrian paths are illustrative. No field geometry or calibration is implied.</p></details>
  </div>
}

/** The host loads once per network; a stale response never replaces another network. */
export function SimulationVisualization(props: { frame: RenderFrame | null; networkId: string | null; controlledJunction?: string | null; mode: string; runKey: string; seekRevision?: number; title: string; onUnavailable: (message: string) => void; onPerformanceSample?: (sample: PerformanceSample) => void }) {
  const [loaded, setLoaded] = React.useState<{ requested: string | null; geometry: SceneGeometry } | null>(null)
  const [error, setError] = React.useState<{ requested: string | null; message: string } | null>(null)
  React.useEffect(() => {
    let active = true
    getVisualNetwork(props.networkId).then(network => { if (active) { setLoaded({ requested: props.networkId, geometry: normalizeSceneGeometry(network) }); setError(null) } }).catch(reason => { if (active) setError({ requested: props.networkId, message: reason instanceof Error ? reason.message : "Unable to load network" }) })
    return () => { active = false }
  }, [props.networkId])
  if (error && error.requested === props.networkId) return <Alert><AlertDescription>{error.message}</AlertDescription></Alert>
  if (!loaded || loaded.requested !== props.networkId) return <p role="status">Loading native network…</p>
  return <Workspace key={loaded.geometry.networkId} {...props} geometry={loaded.geometry} />
}

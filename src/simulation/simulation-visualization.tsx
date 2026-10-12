import * as React from "react"
import { CarFrontIcon, CrosshairIcon, LayersIcon, MapIcon, MaximizeIcon, MinimizeIcon, PanelRightIcon, PersonStandingIcon, RotateCcwIcon, XIcon } from "lucide-react"
import { getVisualNetwork } from "@/api/visual-network"
import { SimulationCanvas2D } from "@/components/simulation-canvas-2d"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Field, FieldLabel, FieldSet, FieldLegend } from "@/components/ui/field"
import { cn } from "@/lib/utils"
import type { RenderFrame, ControllerEvent } from "@/simulation/frame-types"
import { normalizeSceneGeometry, selectionKey, type SceneGeometry, type Selection } from "@/simulation/scene-geometry"
import { createPresentationState, presentationReducer, type PresentationState, type OverlaySettings } from "@/simulation/presentation-state"
import { timingLabel } from "@/simulation/render-frame-adapter"
import { junctionShortLabel, laneDisplayLabel, longestQueuedApproach } from "@/simulation/scene-summary"
import { SimulationScene3D } from "@/simulation/SimulationScene3D"

type PerformanceSample = { fps: number; p95FrameMs: number; drawCalls: number }
const value = (number: number | undefined, unit = "") => number === undefined ? "Unavailable" : `${number.toFixed(1)}${unit}`
const OVERLAY_LABELS: Record<keyof OverlaySettings, string> = { signals: "Signals", labels: "Labels", queues: "Queue counts", heatmap: "Queue heatmap", arrows: "Flow direction", connectors: "Turn paths", context: "Street context" }

function EventDetail({ event, label, geometry }: { event: ControllerEvent | null | undefined; label: string; geometry: SceneGeometry }) {
  if (!event) return <p>{label}: Unavailable</p>
  const service = event.service ?? event.action ?? "Unavailable"
  const junction = event.junction_id ? geometry.junctionById.get(event.junction_id)?.label ?? event.junction_id : "Junction not recorded"
  return <p>{label}: {String(service)} at {value(event.time, " s")} · {String(event.result ?? event.reason ?? "Result unavailable")} · {junction}</p>
}

export function ControllerInspector({ frame, geometry, presentation, onClose, children }: { frame: RenderFrame | null; geometry: SceneGeometry; presentation: PresentationState; onClose?: () => void; children?: React.ReactNode }) {
  const id = presentation.selection?.kind === "junction" ? presentation.selection.id : presentation.junctionId
  const control = id ? frame?.junction_controls[id] : undefined
  const metric = id ? frame?.junction_metrics?.[id] : undefined
  const label = id ? geometry.junctionById.get(id)?.label ?? id : "No junction"
  const selection = presentation.selection
  const lane = selection?.kind === "lane" ? frame?.lane_metrics?.[selection.id] : undefined
  const entity = selection?.kind === "vehicle" ? frame?.vehicles.find(vehicle => vehicle.id === selection.id) : selection?.kind === "pedestrian" ? frame?.pedestrians.find(person => person.id === selection.id) : undefined
  const stopped = !frame || frame.status === "stopped"
  const allWayStop = control?.mode === "all_way_stop"
  const events = stopped ? undefined : frame.controller_events
  return <aside id="scene-inspector" className="sf-scene-inspector" aria-label="Simulation inspector">
    <div className="sf-scene-inspector-heading"><strong>Inspect simulation</strong>{onClose ? <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close inspector"><XIcon /></Button> : null}</div>
    {children}
    {selection && selection.kind !== "junction" ? <section className="sf-selected-detail">
      <div className="sf-scene-section-label">Selected {selection.kind}</div>
      <h4>{selection.kind === "lane" ? laneDisplayLabel(geometry, selection.id) : selection.id}</h4>
      {selection.kind === "lane" ? <><code>{selection.id}</code><dl className="sf-scene-measurements"><div><dt>Queue</dt><dd>{lane?.queue ?? "—"}</dd></div><div><dt>Mean speed</dt><dd>{value(lane?.mean_speed_mps === undefined ? undefined : lane.mean_speed_mps * 3.6, " km/h")}</dd></div></dl><p>Density: {value(lane?.density_vehicles_per_km, " vehicles/km")}</p><p>{lane ? lane.closed ? "Closed to new entry" : lane.speed_factor < 1 ? `Speed limited to ${Math.round(lane.speed_factor * 100)}%` : "Open to traffic" : "Restrictions unavailable"}</p></> : <><p>Class: {!entity ? "Unavailable" : "visual_type" in entity ? String(entity.visual_type) : "Pedestrian"}</p><dl className="sf-scene-measurements"><div><dt>Speed</dt><dd>{value(entity?.speed === undefined ? undefined : entity.speed * 3.6, " km/h")}</dd></div><div><dt>Waiting</dt><dd>{value(entity?.wait_time, " s")}</dd></div></dl><p>State: {entity ? entity.stopped ? "Waiting / stopped" : "Moving" : "Not in displayed population"}</p></>}
    </section> : null}
    <section className="sf-scene-controller-detail">
      <div className="sf-scene-section-label">{selection?.kind === "junction" ? "Selected junction" : "Focused junction"}</div>
      <h3>{label}</h3>
      <Badge variant="secondary">{stopped ? "Stopped" : control?.controller?.replaceAll("_", " ") ?? "Controller unavailable"}</Badge>
      <p className="sf-scene-service">{stopped ? "Service unavailable" : allWayStop ? "Unsignalized all-way stop" : control?.phase?.replaceAll("_", " ") ?? "Service unavailable"}</p>
      <p>{stopped ? "Timing unavailable" : timingLabel(control)}</p>
      <dl className="sf-scene-measurements"><div><dt>Junction queue</dt><dd>{stopped ? "—" : metric?.queue ?? "—"}</dd></div><div><dt>Waiting pedestrians</dt><dd>{stopped ? "—" : metric?.waiting_pedestrians ?? "—"}</dd></div></dl>
      <details className="sf-scene-technical"><summary>Controller details</summary><code>{id}</code><p>Elapsed stage: {stopped || allWayStop ? "Unavailable" : value(control?.elapsed_seconds, " s")}</p><p>Pending request: {stopped || control?.pending_service === undefined ? "Unavailable" : control.pending_service ?? "None recorded"}</p></details>
    </section>
    <details className="sf-scene-events"><summary>Latest network controller events</summary><p className="sf-scene-muted">These events may belong to a different junction.</p><EventDetail event={events?.last_policy_decision} label="Latest policy request" geometry={geometry} /><EventDetail event={events?.last_safety_override} label="Latest recorded safety event" geometry={geometry} /></details>
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
  const inspectorOpen = inspectorPreference ?? !is2D
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
  const networkFocus = presentation.focus === "network"
  const stopped = !frame || frame.status === "stopped"
  const longestQueue = longestQueuedApproach(geometry, stopped ? undefined : frame.lane_metrics, networkFocus ? null : presentation.junctionId)
  const focusedJunction = geometry.junctionById.get(presentation.junctionId ?? "")
  const focusedControl = frame?.junction_controls[presentation.junctionId ?? ""]
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
      <div className="sf-scene-title"><div className="sf-scene-eyebrow">{is2D ? "TRAFFIC EXPLORER" : "ARCHITECTURAL VIEW"}</div><strong>{title}</strong></div>
      <div className="sf-scene-heading-actions"><Badge variant={frame?.status === "running" ? "secondary" : "outline"}>{frame?.playback.active ? "Replay" : frame?.status ?? "idle"}</Badge><span className="sf-scene-clock">{value(frame?.time, " s")}</span><Button variant="outline" size="sm" onClick={() => void fullscreen()} aria-label={expanded ? "Exit fullscreen" : "Enter fullscreen"}>{expanded ? <MinimizeIcon data-icon="inline-start" /> : <MaximizeIcon data-icon="inline-start" />}{expanded ? "Exit" : "Expand"}</Button></div>
    </header>
    <div className="sf-scene-toolbar">
      <ToggleGroup value={[presentation.focus]} onValueChange={values => { const next = values[0]; if (next === "junction" || next === "network" || next === "follow") dispatch({ type: "focus", focus: next }) }} size="sm" variant="outline" aria-label="Camera focus">
        <ToggleGroupItem value="junction" aria-label="Junction focus"><CrosshairIcon data-icon="inline-start" />Junction</ToggleGroupItem><ToggleGroupItem value="network" aria-label="Network overview"><MapIcon data-icon="inline-start" />Network</ToggleGroupItem><ToggleGroupItem value="follow" disabled={presentation.selection?.kind !== "vehicle"} title="Select a vehicle on the map to follow it">Follow vehicle</ToggleGroupItem>
      </ToggleGroup>
      <Field className="sf-scene-field"><FieldLabel htmlFor="scene-junction" className="sr-only">Junction</FieldLabel><select id="scene-junction" value={presentation.junctionId ?? ""} onChange={event => focus(event.target.value)}>{geometry.junctions.map(junction => <option key={junction.id} value={junction.id}>{junctionShortLabel(geometry, junction.id)} · {junction.label}</option>)}</select></Field>
      <div className="sf-scene-toolbar-actions"><Button variant="ghost" size="icon-sm" onClick={() => dispatch({ type: "reset", junctionId: controlledJunction })} aria-label="Reset view" title="Reset view"><RotateCcwIcon /></Button><Button variant={layersOpen ? "secondary" : "outline"} size="sm" aria-expanded={layersOpen} aria-controls="scene-layers" onClick={() => setLayersOpen(open => !open)}><LayersIcon data-icon="inline-start" />Layers</Button><Button ref={inspectorToggle} variant={inspectorOpen ? "secondary" : "outline"} size="sm" aria-expanded={inspectorOpen} aria-controls="scene-inspector" onClick={() => setInspectorPreference(!inspectorOpen)}><PanelRightIcon data-icon="inline-start" />Inspect</Button></div>
    </div>
    {layersOpen ? <div id="scene-layers" className="sf-scene-layer-panel"><FieldSet><FieldLegend className="sr-only">Scene overlays</FieldLegend><div className="sf-scene-toggles">{Object.entries(presentation.overlays).map(([key, enabled]) => <label key={key}><input type="checkbox" checked={enabled} onChange={event => dispatch({ type: "overlay", overlay: key as keyof OverlaySettings, enabled: event.target.checked })} />{OVERLAY_LABELS[key as keyof OverlaySettings]}</label>)}</div></FieldSet>{!is2D ? <Field className="sf-scene-field"><FieldLabel htmlFor="scene-quality">Quality</FieldLabel><select id="scene-quality" value={presentation.quality} onChange={event => dispatch({ type: "quality", quality: event.target.value === "enhanced" ? "enhanced" : "laptop" })}><option value="laptop">Laptop</option><option value="enhanced">Enhanced shadows</option></select></Field> : null}</div> : null}
    {failure ? <Alert><AlertDescription>{failure}</AlertDescription></Alert> : null}
    {presentation.notice ? <p className="sf-scene-notice" role="status">{presentation.notice}</p> : null}
    <div className="sf-scene-layout" data-inspector={inspectorOpen}>
      <div className="sf-scene-viewport">
        {is2D ? <SimulationCanvas2D frame={frame} geometry={geometry} presentation={presentation} runKey={runKey} onSelect={select} onPerformanceSample={onPerformanceSample} /> : <SimulationScene3D frame={frame} geometry={geometry} presentation={presentation} runKey={runKey} onSelect={select} onUnavailable={fallback} onPerformanceSample={onPerformanceSample} />}
        <Minimap geometry={geometry} junctionId={presentation.junctionId} onFocus={focus} />
        {presentation.overlays.labels ? <div className="sf-scene-caption"><div className="sf-scene-caption-label">{networkFocus ? "NETWORK OVERVIEW" : presentation.focus === "follow" ? "FOLLOWING VEHICLE" : "JUNCTION FOCUS"}</div><strong>{networkFocus ? `${geometry.junctions.length} connected junctions` : presentation.focus === "follow" ? presentation.selection?.id : focusedJunction?.label ?? "Network"}</strong>{!networkFocus ? <span>{stopped ? "Service unavailable" : focusedControl?.mode === "all_way_stop" ? "All-way stop" : focusedControl?.phase?.replaceAll("_", " ") ?? "Service unavailable"}</span> : null}{presentation.overlays.queues ? <span className="sf-scene-caption-queue">{networkFocus ? "Longest network queue" : "Longest incoming queue"}: <b>{longestQueue?.queue ?? "—"}</b>{longestQueue ? <span title={longestQueue.id}>{laneDisplayLabel(geometry, longestQueue.id)}</span> : null}</span> : null}</div> : null}
      </div>
      {inspectorOpen ? <ControllerInspector frame={frame} geometry={geometry} presentation={presentation} onClose={() => { setInspectorPreference(false); inspectorToggle.current?.focus() }}><Field className="sf-scene-object-field"><FieldLabel htmlFor="scene-object">Inspect object</FieldLabel><select id="scene-object" value={selectedKey} onChange={event => { const item = entities.find(entity => selectionKey(entity) === event.target.value); select(item ? { kind: item.kind, id: item.id } : null) }}><option value="">Choose an object or click the map</option>{entities.map(entity => <option key={selectionKey(entity)} value={selectionKey(entity)}>{entity.kind}: {entity.label}</option>)}</select></Field></ControllerInspector> : null}
    </div>
    <footer className="sf-scene-footer"><div className="sf-scene-population"><span><CarFrontIcon aria-hidden="true" /><b>{coverage?.vehicles.total ?? frame?.vehicle_count ?? 0}</b> vehicles</span><span><PersonStandingIcon aria-hidden="true" /><b>{coverage?.pedestrians.total ?? frame?.pedestrian_count ?? 0}</b> pedestrians</span>{coverage?.limited ? <span className="sf-scene-muted">Showing {coverage.vehicles.shown}/{coverage.vehicles.total} vehicles · {coverage.pedestrians.shown}/{coverage.pedestrians.total} pedestrians ({coverage.reason?.replaceAll("_", " ")})</span> : <span className="sf-scene-muted">{displayedPopulationComplete ? "All displayed" : "Display coverage unavailable"}</span>}</div><span className="sf-scene-source">Illustrative geometry · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a></span></footer>
    <details className="sf-scene-options"><summary>Map legend and research notes</summary><div className="sf-scene-legend"><span><i className="sf-legend-dot sf-legend-tricycle" />Green Tagum tricycle</span><span><i className="sf-legend-dot sf-legend-pedestrian" />Pedestrian</span><span><i className="sf-legend-dot sf-legend-selected" />Selected object</span><span><i className="sf-legend-dot sf-legend-closed" />Closed entry</span><span><i className="sf-legend-dot sf-legend-slow" />Reduced speed</span></div><p>Cars, motorcycles, tricycles, buses, trucks and emergency vehicles use distinct silhouettes. Signals: red / yellow / green; dark lamps are unlit.</p><p>Queue bands: 0 clear · 1–4 low · 5–9 moderate · 10+ high. Counts come from engine telemetry, including vehicles outside the visible map.</p><p>Buildings, greenery and dashed pedestrian paths are illustrative. No field geometry or calibration is implied.</p></details>
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

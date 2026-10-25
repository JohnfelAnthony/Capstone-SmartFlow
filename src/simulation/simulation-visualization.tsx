import * as React from "react"
import { CameraIcon, LayersIcon, MaximizeIcon, MinimizeIcon } from "lucide-react"
import { getVisualNetwork } from "@/api/visual-network"
import { SimulationCanvas2D } from "@/components/simulation-canvas-2d"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuGroup, DropdownMenuLabel,
  DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import type { RenderFrame } from "@/simulation/frame-types"
import { normalizeSceneGeometry, selectionKey, type SceneGeometry, type Selection } from "@/simulation/scene-geometry"
import { createPresentationState, presentationReducer, type OverlaySettings } from "@/simulation/presentation-state"
import { phaseService } from "@/simulation/scene-summary"
import { SimulationScene3D } from "@/simulation/SimulationScene3D"
import { JunctionCard, NetworkMapCard } from "@/simulation/junction-details"

type PerformanceSample = { fps: number; p95FrameMs: number; drawCalls: number }
const OVERLAY_LABELS: Record<keyof OverlaySettings, string> = { signals: "Signals", labels: "Junction tags", queues: "Queue counts", heatmap: "Queue colours", arrows: "Flow direction", connectors: "Turn paths", context: "Buildings and trees" }
const readable = (text: string | null | undefined) => text ? text.replaceAll("_", " ").toLowerCase().replace(/^\w/, letter => letter.toUpperCase()) : "—"

type WorkspaceProps = {
  geometry: SceneGeometry; frame: RenderFrame | null; controlledJunction?: string | null; mode: string; runKey: string; seekRevision?: number
  laneStreets: Record<string, string>; controlBar?: React.ReactNode; overlay?: React.ReactNode; sidePanel?: React.ReactNode
  onUnavailable: (message: string) => void; onPerformanceSample?: (sample: PerformanceSample) => void
}

function Workspace({ geometry, frame, controlledJunction, mode, runKey, seekRevision = 0, laneStreets, controlBar, overlay, sidePanel, onUnavailable, onPerformanceSample }: WorkspaceProps) {
  const [presentation, dispatch] = React.useReducer(presentationReducer, geometry, network => createPresentationState(network, controlledJunction))
  const [expanded, setExpanded] = React.useState(false)
  const [failure, setFailure] = React.useState("")
  const is2D = mode === "2d" || Boolean(failure)
  const host = React.useRef<HTMLDivElement | null>(null)
  const previous = React.useRef({ runKey, seekRevision, time: frame?.time ?? 0, status: frame?.status, controlledJunction })
  const select = React.useCallback((selection: Selection | null) => dispatch({ type: "select", selection }), [])
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
  const junctionId = presentation.selection?.kind === "junction" ? presentation.selection.id : presentation.junctionId
  const junction = junctionId ? geometry.junctionById.get(junctionId) : undefined
  const running = Boolean(frame && frame.status !== "stopped")
  const control = running && junctionId ? frame?.junction_controls[junctionId] : undefined
  const service = phaseService(control?.phase)
  const phaseColor = !control ? "off" : control.mode === "all_way_stop" ? "off" : control.stage === "green" ? "green" : control.stage === "yellow" ? "yellow" : "red"
  return <div ref={host} className={cn("sf-scene-workspace sf-sim-layout", expanded && "sf-scene-expanded")} data-mode={is2D ? "2d" : "3d"} data-focus={presentation.focus} data-junction={presentation.junctionId} data-selection={selectionKey(presentation.selection)}>
    <div className="sf-sim-main">
      {failure ? <Alert><AlertDescription>{failure}</AlertDescription></Alert> : null}
      <div className="sf-scene-viewport">
        {is2D ? <SimulationCanvas2D frame={frame} geometry={geometry} presentation={presentation} runKey={runKey} onSelect={select} onPerformanceSample={onPerformanceSample} /> : <SimulationScene3D frame={frame} geometry={geometry} presentation={presentation} runKey={runKey} onSelect={select} onUnavailable={fallback} onPerformanceSample={onPerformanceSample} />}
        <div className="sf-sim-chip sf-sim-chip-top-left"><span>Intersection</span><strong>{junction?.label ?? "—"}</strong></div>
        <div className="sf-sim-chip sf-sim-chip-bottom-left"><span>Signal phase</span><strong><i className="sf-sim-chip-dot" data-color={phaseColor} />{!control ? "—" : control.mode === "all_way_stop" ? "All-way stop" : service === "pedestrian" ? "Pedestrian crossing" : service ? readable(control.phase) : "All red"}</strong></div>
        <div className="sf-sim-chip sf-sim-chip-bottom-right"><span>Phase timer</span><strong>{control?.remaining_seconds == null ? "—" : `${Math.ceil(control.remaining_seconds)}s`}</strong></div>
        {overlay ? <div className="sf-sim-overlay">{overlay}</div> : null}
      </div>
      {presentation.notice ? <p className="sf-scene-notice" role="status">{presentation.notice}</p> : null}
      <div className="sf-sim-bar">
        {controlBar}
        <div className="sf-sim-bar-actions">
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}><LayersIcon data-icon="inline-start" />Layers</DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuGroup>
                <DropdownMenuLabel>Show on map</DropdownMenuLabel>
                {(Object.keys(OVERLAY_LABELS) as Array<keyof OverlaySettings>).map(key =>
                  <DropdownMenuCheckboxItem key={key} checked={presentation.overlays[key]} onCheckedChange={checked => dispatch({ type: "overlay", overlay: key, enabled: checked })}>{OVERLAY_LABELS[key]}</DropdownMenuCheckboxItem>)}
              </DropdownMenuGroup>
              {!is2D ? <><DropdownMenuSeparator /><DropdownMenuGroup>
                <DropdownMenuCheckboxItem checked={presentation.quality === "enhanced"} onCheckedChange={checked => dispatch({ type: "quality", quality: checked ? "enhanced" : "laptop" })}>Enhanced shadows</DropdownMenuCheckboxItem>
              </DropdownMenuGroup></> : null}
            </DropdownMenuContent>
          </DropdownMenu>
          {!is2D ? <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}><CameraIcon data-icon="inline-start" />Camera</DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuRadioGroup value={presentation.focus} onValueChange={value => { if (value === "junction" || value === "network") dispatch({ type: "focus", focus: value }) }}>
                <DropdownMenuRadioItem value="junction">Selected junction</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="network">Whole network</DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu> : null}
          <Button variant="outline" size="icon-sm" onClick={() => void fullscreen()} aria-label={expanded ? "Exit fullscreen" : "Enter fullscreen"} title={expanded ? "Exit fullscreen" : "Expand"}>{expanded ? <MinimizeIcon /> : <MaximizeIcon />}</Button>
        </div>
      </div>
      <p className="sf-sim-credit">Illustrative geometry · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a></p>
    </div>
    <aside className="sf-sim-side" aria-label="Junction information">
      <NetworkMapCard geometry={geometry} junctionId={junctionId} onFocus={focus} />
      <JunctionCard frame={frame} geometry={geometry} junctionId={junctionId} laneStreets={laneStreets} />
      {sidePanel}
    </aside>
  </div>
}

/** The host loads once per network; a stale response never replaces another network. */
export function SimulationVisualization(props: Omit<WorkspaceProps, "geometry"> & { networkId: string | null }) {
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

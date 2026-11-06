import * as React from "react"

import { checkClosures, type ClosureReport, type NativeScenarioConfig, type NativeScenarioOptions } from "@/api/native-scenario"
import { getVisualNetwork } from "@/api/visual-network"
import { NativeSelect } from "@/components/native-scenario-controls"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  chooseResponse, describeRule, readClosures, recordedResponse, RESPONSE_HINTS, RESPONSE_LABELS, ruleProblem, settleResponses, sharedLaneIds, writeClosures,
  type ClosureRule, type LaneOption,
} from "@/lib/closures"
import { JunctionMiniMap } from "@/simulation/junction-details"
import { normalizeSceneGeometry, type SceneGeometry } from "@/simulation/scene-geometry"
import { junctionShortLabel, sharedStripsFromGeometry, signalMovements } from "@/simulation/scene-summary"

const CHECK_DELAY_MS = 250

const MEANING: Record<string, string> = {
  entry: "Nothing can enter here. The vehicles that would have entered wait outside until it reopens.",
  exit: "Vehicles cannot leave the area by this road. Drivers heading for it are sent elsewhere.",
  link: "No new vehicle enters it; those already on it finish. Drivers whose route used it take another way.",
}

function DetourBadge({ report, laneId }: { report: ClosureReport | null; laneId: string }) {
  const piece = report?.pieces[laneId]
  if (!piece) return <Badge variant="outline">checking…</Badge>
  if (piece.trips_using === 0) return <Badge variant="outline" title="No trip's usual route uses this piece, so closing it changes nothing unless traffic is detoured onto it.">not on a usual route</Badge>
  return piece.has_detour
    ? <Badge variant="secondary" title={`All ${piece.trips_using} trips that normally use this piece can still reach their destination.`}>has a detour</Badge>
    : <Badge variant="destructive" title={`${piece.trips_without_route} of ${piece.trips_using} trips that normally use this piece would have no route.`}>no detour</Badge>
}

/** Choose closed roads by clicking them on the real junction: a direction closes with one click and reopens with another. Each closed direction is described in words with its detour status, its times and how traffic should respond. */
export function ClosurePicker({ options, config, onChange, onProblem, disabled = false }: {
  options: NativeScenarioOptions; config: NativeScenarioConfig; onChange: (config: NativeScenarioConfig) => void
  onProblem: (message: string | null) => void; disabled?: boolean
}) {
  const { rules, locked } = React.useMemo(() => readClosures(config), [config])
  const [report, setReport] = React.useState<ClosureReport | null>(null)
  const [checkError, setCheckError] = React.useState("")
  const [loaded, setLoaded] = React.useState<{ networkId: string; geometry?: SceneGeometry; error?: string } | null>(null)
  const geometry = loaded?.networkId === options.network_id ? loaded.geometry ?? null : null
  const drawingError = loaded?.networkId === options.network_id ? loaded.error ?? "" : ""
  const [junctionId, setJunctionId] = React.useState<string | null>(null)
  const selection = JSON.stringify([config.closed_lanes ?? [], (config.events ?? []).filter(event => event.closed !== undefined)])
  const latest = React.useRef({ config, onChange })
  React.useEffect(() => { latest.current = { config, onChange } })

  React.useEffect(() => {
    let current = true
    getVisualNetwork(options.network_id)
      .then(network => { if (current) { const next = normalizeSceneGeometry(network); setLoaded({ networkId: options.network_id, geometry: next }); setJunctionId(next.junctions[0]?.id ?? null) } })
      .catch(error => { if (current) setLoaded({ networkId: options.network_id, error: error instanceof Error ? error.message : "The junction drawing could not be loaded." }) })
    return () => { current = false }
  }, [options.network_id])

  React.useEffect(() => {
    let current = true
    const timer = window.setTimeout(() => {
      const [closed, events] = JSON.parse(selection)
      checkClosures(options.network_id, closed, events)
        .then(result => { if (current) { setReport(result); setCheckError(""); onProblem(result.valid ? null : result.message) } })
        .catch(error => { if (current) { setCheckError(error instanceof Error ? error.message : "Unable to check these closures."); onProblem(null) } })
    }, CHECK_DELAY_MS)
    return () => { current = false; window.clearTimeout(timer) }
  }, [options.network_id, selection, onProblem])

  // What the routing check offers can change as closures are added, so the recorded responses are kept consistent with it.
  React.useEffect(() => {
    if (!report) return
    const settled = settleResponses(latest.current.config, report.pieces)
    if (settled !== latest.current.config) latest.current.onChange(settled)
  }, [report])

  const laneOf = (laneId: string): LaneOption | undefined => options.lanes.find(lane => lane.id === laneId)
  const laneName = (laneId: string) => { const lane = laneOf(laneId); return lane ? [lane.road_name, lane.where, lane.direction].filter(Boolean).join(" · ") : laneId }
  const closedIds = React.useMemo(() => new Set([...Object.keys(rules), ...locked]), [rules, locked])
  const sharedIds = React.useMemo(() => new Set(sharedLaneIds(config)), [config])
  const strips = React.useMemo(() => geometry ? sharedStripsFromGeometry(geometry, sharedIds) : [], [geometry, sharedIds])

  const update = (next: Record<string, ClosureRule>, withConfig: NativeScenarioConfig = config) => {
    const written = writeClosures(withConfig, next, locked)
    const stillClosed = new Set([...Object.keys(next), ...locked])
    const kept = Object.fromEntries(Object.entries(written.closure_responses ?? {}).filter(([lane]) => stillClosed.has(lane)))
    onChange({ ...written, closure_responses: kept })
  }
  const toggle = (laneId: string) => {
    if (disabled || locked.includes(laneId)) return
    if (rules[laneId]) { const next = { ...rules }; delete next[laneId]; update(next); return }
    const piece = report?.pieces[laneId]
    const avoiding = Object.values(config.closure_responses ?? {}).includes("side_street_adaptive")
    const response = piece ? (avoiding && piece.responses.includes("side_street_adaptive") ? "side_street_adaptive" : piece.default_response) : undefined
    const withResponse = response ? { ...config, closure_responses: { ...(config.closure_responses ?? {}), [laneId]: response } } : config
    update({ ...rules, [laneId]: { start: 0, end: null } }, withResponse)
  }
  const setTime = (laneId: string, key: keyof ClosureRule, text: string) => {
    const value = text.trim() === "" ? (key === "end" ? null : 0) : Number(text)
    update({ ...rules, [laneId]: { ...rules[laneId], [key]: value } as ClosureRule })
  }
  const respond = (laneId: string, response: string) => onChange(chooseResponse(config, laneId, response))

  const junctions = geometry?.junctions ?? []
  const movements = geometry && junctionId ? signalMovements(geometry, junctionId, null) : []
  const unavailableIds = new Set([...closedIds].filter(laneId => !sharedIds.has(laneId)))
  const closedHere = geometry && junctionId ? [...closedIds].filter(laneId => geometry.laneById.get(laneId)?.junctionIds.includes(junctionId)) : []
  const summary = closedHere.length ? `Closed here: ${closedHere.map(laneName).join("; ")}` : "No road is closed at this junction"

  return <Field>
    <FieldLabel>Closed roads</FieldLabel>
    <FieldDescription>Click a road on the junction to close it, and click it again to reopen it. Each direction is separate: click both to close the road both ways. Use the buttons to reach every junction.</FieldDescription>
    {checkError && <Alert variant="destructive"><AlertDescription>{checkError}</AlertDescription></Alert>}
    {report && !report.valid && report.message && <Alert variant="destructive" role="alert"><AlertDescription>{report.message}</AlertDescription></Alert>}
    {drawingError && <Alert variant="destructive"><AlertDescription>The junction drawing could not be loaded: {drawingError}</AlertDescription></Alert>}
    {geometry && junctionId ? <div className="flex flex-col gap-2" data-testid="closure-junction">
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Junction">
        {junctions.map(junction => <Button key={junction.id} type="button" size="sm" variant={junction.id === junctionId ? "secondary" : "outline"} aria-pressed={junction.id === junctionId}
          title={junction.label.replace(/^J\d+:\s*/, "")} onClick={() => setJunctionId(junction.id)}>
          {junctionShortLabel(geometry, junction.id)}
          {[...closedIds].some(laneId => geometry.laneById.get(laneId)?.junctionIds.includes(junction.id)) ? <span className="ml-1 size-1.5 rounded-full bg-destructive" aria-label="has a closed road" /> : null}
        </Button>)}
      </div>
      <p className="text-sm text-muted-foreground">{junctions.find(junction => junction.id === junctionId)?.label.replace(/^J\d+:\s*/, "")}</p>
      <JunctionMiniMap geometry={geometry} junctionId={junctionId} movements={movements} closed={unavailableIds} summary={summary}
        laneLabel={laneName} onToggleLane={disabled ? undefined : toggle} shared={sharedIds} strips={strips} />
      {sharedIds.size ? <p className="text-xs text-muted-foreground">Amber: the closed direction shares half of the opposite pavement, one lane each way. This is a hypothetical arrangement; it assumes cones, signs and usually an enforcer.</p> : null}
    </div> : !drawingError ? <p className="text-sm text-muted-foreground">Loading the junction…</p> : null}
    <div className="flex flex-col gap-2" role="group" aria-label="Closed roads in words">
      {closedIds.size === 0 ? <p className="text-sm text-muted-foreground">No road is closed.</p> : null}
      {[...closedIds].map(laneId => {
        const lane = laneOf(laneId)
        const rule = rules[laneId]
        const isLocked = locked.includes(laneId)
        const piece = report?.pieces[laneId]
        const problem = rule ? ruleProblem(rule) : null
        const offered = piece?.responses ?? []
        const chosen = recordedResponse(config, laneId) ?? piece?.default_response ?? ""
        return <div key={laneId} className="rounded-lg border p-2.5 flex flex-col gap-2" data-testid={`closure-${laneId}`}>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium">{laneName(laneId)}</p>
            <DetourBadge report={report} laneId={laneId} />
            {rule ? <Badge variant="outline">{describeRule(rule)}</Badge> : null}
            {isLocked ? <Badge variant="outline">several timed changes (kept as saved)</Badge> : null}
            {!disabled && rule ? <Button type="button" size="xs" variant="ghost" className="ml-auto" onClick={() => toggle(laneId)}>Reopen</Button> : null}
          </div>
          <p className="text-sm text-muted-foreground">{sharedIds.has(laneId)
            ? "This direction's traffic drives on half of the opposite pavement, one lane each way. Hypothetical: it assumes cones, signs and usually an enforcer."
            : piece && !piece.has_detour && lane?.kind !== "entry"
            ? "No new vehicle enters it; those already on it finish. Drivers whose route used it have no other way, so they are sent to the nearest open exit."
            : MEANING[lane?.kind ?? "link"]}</p>
          {rule ? <div className="grid max-w-sm grid-cols-2 gap-2">
            <Field data-invalid={Boolean(problem)}>
              <FieldLabel htmlFor={`start-${laneId}`}>Closes at (s)</FieldLabel>
              <Input id={`start-${laneId}`} type="number" min={0} step={1} value={rule.start} disabled={disabled} aria-invalid={Boolean(problem)}
                onChange={event => setTime(laneId, "start", event.target.value)} />
            </Field>
            <Field data-invalid={Boolean(problem)}>
              <FieldLabel htmlFor={`end-${laneId}`}>Reopens at (s)</FieldLabel>
              <Input id={`end-${laneId}`} type="number" min={0} step={1} value={rule.end ?? ""} placeholder="end of run" disabled={disabled} aria-invalid={Boolean(problem)}
                onChange={event => setTime(laneId, "end", event.target.value)} />
            </Field>
            {problem ? <FieldDescription className="col-span-2 text-destructive">{problem}</FieldDescription> : null}
          </div> : null}
          {offered.length ? <div className="flex flex-col gap-1">
            <NativeSelect label="How should traffic respond?" value={chosen} disabled={disabled}
              options={offered.map(value => ({ value, label: RESPONSE_LABELS[value] ?? value }))} onChange={value => respond(laneId, value)} />
            <p className="text-xs text-muted-foreground">{RESPONSE_HINTS[chosen] ?? ""}{recordedResponse(config, laneId) ? "" : " (This scenario was saved without a choice; traffic behaves as it always did until you pick one.)"}</p>
          </div> : null}
        </div>
      })}
    </div>
    {report && report.selection.trips_without_route > 0 && report.valid
      ? <p className="text-sm text-muted-foreground" role="status">{report.selection.trips_without_route} of {report.selection.trips} entry-to-exit trips would lose their usual destination under this selection; those vehicles go to an open exit.</p> : null}
  </Field>
}

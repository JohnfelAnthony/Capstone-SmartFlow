import { useEffect, useMemo, useState } from "react"
import { BusIcon, CarIcon, CarTaxiFrontIcon, MotorbikeIcon, RouteIcon, RulerIcon, TrafficConeIcon, TruckIcon } from "lucide-react"
import { ApiError, SESSION_RESTORED_EVENT } from "@/api/client"
import { listNetworks, type NetworkSummary } from "@/api/native-scenario"
import { listScenarios, type ApiScenario } from "@/api/scenarios"
import type { RouteSource, RouteVehicleClass } from "@/api/routes"
import { NativeSelect } from "@/components/native-scenario-controls"
import { RoutePlannerMap } from "@/components/route-planner-map"
import { ChosenEnd, ClosureStep, EndPills, Step } from "@/components/route-planner-steps"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { activeClosures, useRoutePlanner } from "@/lib/route-planner"
import { routeScenarioDraft, type RouteScenarioDraft } from "@/lib/route-scenario"
import { buildRouteEnds, describeRoad, describeRoute, endAction, endRoles, formatDistance, routeEndsComplete, routeLengthMeters, routeStatus, type EndStep } from "@/lib/route-ends"
import type { PlannerFitRequest, PlannerOverlay } from "@/simulation/route-planner-overlay"
import "@/styles/admin-user-management.css"
import "@/styles/route-planner.css"

const vehicles: Array<{ value: RouteVehicleClass; label: string; Icon: typeof CarIcon }> = [
  { value: "car", label: "Car", Icon: CarIcon }, { value: "motorcycle", label: "Motorcycle", Icon: MotorbikeIcon },
  { value: "tricycle", label: "Tricycle", Icon: CarTaxiFrontIcon }, { value: "bus", label: "Bus", Icon: BusIcon },
  { value: "truck", label: "Truck", Icon: TruckIcon },
]

export function RoutePlannerPage({ canCreateScenario = false, onSaveAsScenario }: {
  /** Needs the same permission as the New Scenario form. */
  canCreateScenario?: boolean
  onSaveAsScenario?: (draft: RouteScenarioDraft) => void
}) {
  const { state, dispatch } = useRoutePlanner()
  const [sources, setSources] = useState<{ networks: NetworkSummary[]; scenarios: ApiScenario[] } | null>(null)
  const [sourceError, setSourceError] = useState("")
  const [selectedLaneId, setSelectedLaneId] = useState<string | null>(null)
  const [fitRequest, setFitRequest] = useState<PlannerFitRequest>()
  const [moreOpen, setMoreOpen] = useState(false)
  const [chosenStep, setPicking] = useState<EndStep>("start")
  const { context, preview, source, entryId, destinationId } = state

  useEffect(() => {
    let current = true
    let awaitingAuthentication = false
    function loadSources() {
      void Promise.all([listNetworks(), listScenarios()]).then(([networks, result]) => {
        if (!current) return
        const sites = networks.filter(network => network.id === "tagum_site_a" || network.id === "tagum_site_b")
        setSources({ networks: sites, scenarios: result.scenarios.filter(scenario => scenario.network_id) })
        if (sites.length) dispatch({ type: "source", source: { kind: "network", network_id: sites[0].id } })
      }).catch(error => {
        if (!current) return
        awaitingAuthentication = error instanceof ApiError && error.status === 401
        setSourceError(error instanceof Error ? error.message : "Could not load route sources.")
      })
    }
    function restore() {
      if (!awaitingAuthentication) return
      awaitingAuthentication = false
      setSourceError("")
      loadSources()
    }
    window.addEventListener(SESSION_RESTORED_EVENT, restore)
    loadSources()
    return () => {
      current = false
      window.removeEventListener(SESSION_RESTORED_EVENT, restore)
    }
  }, [dispatch])

  function chooseSource(next: RouteSource) {
    setSelectedLaneId(null)
    setFitRequest(undefined)
    setPicking("start")
    dispatch({ type: "source", source: next })
  }

  function reloadContext() {
    setSelectedLaneId(null)
    setFitRequest(undefined)
    dispatch({ type: "reload" })
  }

  const ends = useMemo(() => context ? buildRouteEnds(context) : [], [context])
  const startLabel = ends.find(end => end.entryId === entryId)?.label
  const destinationLabel = ends.find(end => end.destinationId === destinationId)?.label
  // A start with no destination (for example after changing vehicle) always asks for the destination next.
  const picking: EndStep = startLabel && !destinationLabel ? "destination" : chosenStep
  const pairs = useMemo(() => context?.eligible_pairs ?? [], [context])
  const startRoles = useMemo(() => endRoles(ends, "start", pairs, entryId, destinationId), [ends, pairs, entryId, destinationId])
  const destinationRoles = useMemo(() => endRoles(ends, "destination", pairs, entryId, destinationId), [ends, pairs, entryId, destinationId])
  const closures = activeClosures(state)
  const overlay = useMemo<PlannerOverlay>(() => ({
    original: preview?.original ?? null, selected: preview?.selected ?? null,
    sharedRoads: preview?.shared_roads ?? [], closedLaneIds: closures?.closed_lanes ?? [], selectedLaneId,
    ends: (picking === "start" ? startRoles : destinationRoles).map(({ end, role }) => ({ key: end.key, label: end.label, x: end.x, y: end.y, role })),
  }), [preview, closures, selectedLaneId, picking, startRoles, destinationRoles])

  function chooseEnd(key: string, step: EndStep = picking) {
    const end = ends.find(item => item.key === key)
    if (!end) return
    const next = endAction(end, step, pairs, entryId)
    if (next.action) dispatch(next.action)
    setPicking(next.picking)
  }

  function fit(target: PlannerFitRequest["target"]) {
    setFitRequest(previous => ({ target, revision: (previous?.revision ?? 0) + 1 }))
  }

  const ready = state.contextStatus === "ready"
  const error = state.contextError ?? state.previewError
  const closedCount = closures?.closed_lanes.length ?? 0
  const siteId = source?.kind === "network" ? source.network_id : sources?.scenarios.find(scenario => scenario.id === source?.scenario_id)?.network_id
  const [, siteDetail] = (sources?.networks.find(network => network.id === siteId)?.name ?? "").split(" — ")
  const noHeavyOnSobrecarey = context?.network_id === "tagum_site_b" && (state.vehicleType === "bus" || state.vehicleType === "truck")
  const scenarioName = source?.kind === "scenario" ? sources?.scenarios.find(scenario => scenario.id === source.scenario_id)?.name : undefined
  const scenarioDraft = context ? routeScenarioDraft({ source, context, closures, scenarioName }) : null
  const sentence = preview && context
    ? describeRoute({ vehicle: state.vehicleType, preview, context, ends, entryId, destinationId, closedCount }) : ""
  const metrics = [
    { label: "Route length", value: preview?.selected ? formatDistance(routeLengthMeters(preview.selected)) : "—", hint: "Modelled, no traffic", Icon: RulerIcon },
    { label: "Roads closed", value: String(closedCount), hint: closedCount ? "Whole run" : "Click a road to close it", Icon: TrafficConeIcon },
    { label: "Route", value: routeStatus(preview), hint: preview ? "Under these conditions" : "Pick a start and destination", Icon: RouteIcon },
  ]

  return <main className="smartflow-page route-planner-page" aria-label="Route Planner">
    <section className="audit-hero">
      <div>
        <h1>Route Planner</h1>
      </div>
      {sources ? <div className="flex flex-col gap-1 sm:items-end">
        <ToggleGroup variant="outline" aria-label="Study site" value={siteId ? [siteId] : []}
          onValueChange={([id]) => { if (id && id !== siteId) chooseSource({ kind: "network", network_id: id }) }}>
          {sources.networks.map(network => <ToggleGroupItem key={network.id} value={network.id} className="px-4 aria-pressed:bg-primary aria-pressed:text-primary-foreground">{network.name.split(" — ")[0]}</ToggleGroupItem>)}
        </ToggleGroup>
        {siteDetail ? <p className="text-sm text-muted-foreground">{siteDetail}</p> : null}
      </div> : null}
    </section>
    <section className="audit-metric-strip" aria-label="Route summary">
      {metrics.map(({ label, value, hint, Icon }) => <div key={label} className="audit-strip-metric info">
        <Icon aria-hidden="true" />
        <div><div><strong>{value}</strong><span>{label}</span></div><small>{hint}</small></div>
      </div>)}
    </section>
    {source?.kind === "scenario" && scenarioName
      ? <p role="status" className="text-sm text-muted-foreground">Showing the saved scenario "{scenarioName}" and its closed roads. Changes here are temporary and do not alter the scenario.</p> : null}
    {sourceError ? <Alert variant="destructive"><AlertDescription>{sourceError}</AlertDescription></Alert> : null}
    {!sources && !sourceError ? <p role="status" className="text-sm">Loading sites and scenarios…</p> : null}
    {state.contextStatus === "loading" ? <p role="status" className="text-sm">Loading the map…</p> : null}
    {error ? <Alert variant="destructive">
      <AlertDescription>{error.message}</AlertDescription>
      {error.status === 409 ? <Button variant="outline" className="mt-2 w-fit" onClick={reloadContext}>Reload the map</Button> : null}
    </Alert> : null}
    {context && !routeEndsComplete(context, ends)
      ? <Alert variant="destructive"><AlertDescription>The server is out of date, so the road ends cannot be placed on the map. Restart the API, then refresh this page.</AlertDescription></Alert> : null}
    {context && routeEndsComplete(context, ends) ? <div className="grid min-w-0 items-start gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(18rem,1fr)]">
      <div className="flex min-w-0 flex-col gap-3">
        <RoutePlannerMap network={context.geometry} overlay={overlay} fitRequest={fitRequest}
          onRoadEndSelect={chooseEnd} onRoadDirectionSelect={setSelectedLaneId} />
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => fit("network")}>Show whole map</Button>
          <Button size="sm" variant="outline" disabled={!preview?.original && !preview?.selected} onClick={() => fit("routes")}>Zoom to route</Button>
          {scenarioDraft && canCreateScenario && onSaveAsScenario
            ? <Button size="sm" onClick={() => onSaveAsScenario(scenarioDraft)}>Save as new scenario</Button> : null}
        </div>
        {scenarioDraft && canCreateScenario && onSaveAsScenario
          ? <p className="text-sm text-muted-foreground">Opens the New Scenario form with the closed roads. Nothing is saved until you press Save Scenario there.</p> : null}
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground" aria-label="Map legend">
          <li><span aria-hidden="true" className="text-green-700 dark:text-green-400">➝ </span>Route under these conditions</li>
          <li><span aria-hidden="true">⇢ </span>Route without closures</li>
          <li><span aria-hidden="true" className="text-red-600 dark:text-red-400">▧ </span>Closed road</li>
          <li><span aria-hidden="true" className="text-amber-700 dark:text-amber-400">⇄ </span>Shared pavement (hypothetical)</li>
          <li><span aria-hidden="true" className="text-sky-600 dark:text-sky-300">○ </span>Road end you can choose</li>
        </ul>
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        <Alert variant={preview && (preview.outcome === "no_route" || preview.outcome === "invalid_arrangement") ? "destructive" : "default"} aria-label="Route result" aria-live="polite">
          <AlertTitle>{state.previewPending ? "Updating the route…" : routeStatus(preview)}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2">
            {sentence ? <p className="text-foreground">{sentence}</p> : <p>{state.previewPending ? "One moment." : "Choose a start and a destination to see the route."}</p>}
            {preview ? <details className="text-sm">
              <summary className="cursor-pointer">Why this route?</summary>
              <p className="mt-2">{preview.reason}</p>
              {preview.uses_shared_pavement ? <p className="mt-1">This trip uses hypothetical shared pavement.</p> : null}
              {preview.routing_mode === "adaptive" ? <p className="mt-1">Adaptive routing · no simulated queues in this preview.</p> : null}
            </details> : null}
          </AlertDescription>
        </Alert>
        <ol className="flex flex-col" aria-label="Plan a trip">
          <Step number={1} title="Where does the trip start?"
            active={picking === "start"} onActivate={() => setPicking("start")}>
            {picking === "start" || !startLabel ? <EndPills roles={startRoles} step="start" onPick={chooseEnd} />
              : <ChosenEnd label={startLabel} onChange={() => setPicking("start")} />}
          </Step>
          <Step number={2} title="Where is it going?" note={noHeavyOnSobrecarey ? "Buses and trucks are not allowed on Sobrecarey Street." : undefined}
            active={picking === "destination"} onActivate={() => setPicking("destination")}>
            {picking === "destination" || !destinationLabel ? <EndPills roles={destinationRoles} step="destination" onPick={chooseEnd} />
              : <ChosenEnd label={destinationLabel} onChange={() => setPicking("destination")} />}
          </Step>
          <Step number={3} title="Close a road? (optional)">
            <ClosureStep context={context} closures={closures} selectedLaneId={selectedLaneId} preview={preview} ready={ready}
              coordinationNotice={state.coordinationNotice} onSelect={setSelectedLaneId}
              onToggle={laneId => dispatch({ type: "toggle", laneId })}
              onRespond={(laneId, response) => dispatch({ type: "response", laneId, response })} />
          </Step>
        </ol>
        {context.notices.map(notice => <p key={notice.code} className="text-sm text-muted-foreground">{notice.message}</p>)}
        <details className="rounded-lg border px-3 py-2 text-sm" open={moreOpen} onToggle={event => setMoreOpen(event.currentTarget.open)}>
          <summary className="cursor-pointer py-1 font-medium">More options</summary>
          <div className="flex flex-col gap-4 py-3">
            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium">Vehicle</span>
              <ToggleGroup variant="outline" className="flex-wrap" aria-label="Vehicle" value={[state.vehicleType]}
                onValueChange={([vehicleType]) => { if (vehicleType) dispatch({ type: "class", vehicleType: vehicleType as RouteVehicleClass }) }}>
                {vehicles.map(({ value, label, Icon }) => <ToggleGroupItem key={value} value={value} aria-label={label} className="gap-1.5 px-3 aria-pressed:bg-primary aria-pressed:text-primary-foreground"><Icon />{label}</ToggleGroupItem>)}
              </ToggleGroup>
            </div>
            {sources?.scenarios.length ? <NativeSelect label="Start from a saved scenario" value={source?.kind === "scenario" ? String(source.scenario_id) : ""}
              options={[{ value: "", label: "None (temporary arrangement)" }, ...sources.scenarios.map(scenario => ({ value: String(scenario.id), label: scenario.name }))]}
              onChange={id => id ? chooseSource({ kind: "scenario", scenario_id: Number(id) })
                : sources.networks[0] && chooseSource({ kind: "network", network_id: siteId ?? sources.networks[0].id })} /> : null}
            <NativeSelect label="Pick a road from a list" value={selectedLaneId ?? ""} disabled={!ready}
              options={[{ value: "", label: "Select a road direction" }, ...context.roads.map(road => ({ value: road.lane_id, label: describeRoad(road) }))]}
              onChange={laneId => setSelectedLaneId(laneId || null)} />
            {source?.kind === "scenario"
              ? <Button size="sm" variant="outline" className="w-fit" disabled={!ready || state.override === undefined}
                  onClick={() => { setSelectedLaneId(null); dispatch({ type: "reset" }) }}>Reset to saved scenario</Button>
              : <Button size="sm" variant="outline" className="w-fit" disabled={!ready || !closedCount}
                  onClick={() => { setSelectedLaneId(null); dispatch({ type: "clear" }) }}>Reopen all roads</Button>}
            {source?.kind === "scenario" && state.override !== undefined
              ? <p className="text-muted-foreground">Temporary changes. The saved scenario is unchanged.</p> : null}
            <p className="text-muted-foreground">The planner uses the start of a run, with no simulated queues. Green arrows show the route, independent of signal phases. Both sites are provisional networks.</p>
          </div>
        </details>
      </div>
    </div> : null}
  </main>
}

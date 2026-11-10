import { useEffect, useMemo, useState } from "react"
import { listNetworks, type NetworkSummary } from "@/api/native-scenario"
import { listScenarios, type ApiScenario } from "@/api/scenarios"
import type { ClosureResponse, RouteSource, RouteVehicleClass } from "@/api/routes"
import { NativeSelect } from "@/components/native-scenario-controls"
import { RoutePlannerMap } from "@/components/route-planner-map"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { RESPONSE_HINTS, RESPONSE_LABELS } from "@/lib/closures"
import { activeClosures, useRoutePlanner } from "@/lib/route-planner"
import type { PlannerFitRequest, PlannerOverlay } from "@/simulation/route-planner-overlay"

const vehicleOptions: Array<{ value: RouteVehicleClass; label: string }> = [
  { value: "car", label: "Car" }, { value: "motorcycle", label: "Motorcycle" },
  { value: "tricycle", label: "Tricycle" }, { value: "bus", label: "Bus" }, { value: "truck", label: "Truck" },
]
const outcomeLabels = {
  unchanged: "Unchanged route", detour: "Detour available", alternative_exit: "Alternative exit",
  waiting_entry: "Waiting outside the network", no_route: "No route", invalid_arrangement: "Invalid arrangement",
}
const plannerHints = {
  side_street: RESPONSE_HINTS.side_street,
  side_street_adaptive: "This setting applies across the network. The preview shows the route with no simulated queues.",
  nearest_exit: "The engine chooses an open exit by routing cost, which can still be the intended destination.",
  share: "The map assumes sharing is established. In a live run, the engine clears the lanes first. This layout is hypothetical.",
  wait: "Arrivals stay outside the network while this direction is closed. A whole-run closure has no reopening.",
}

export function RoutePlannerPage() {
  const { state, dispatch } = useRoutePlanner()
  const [sources, setSources] = useState<{ networks: NetworkSummary[]; scenarios: ApiScenario[] } | null>(null)
  const [sourceError, setSourceError] = useState("")
  const [selectedLaneId, setSelectedLaneId] = useState<string | null>(null)
  const [fitRequest, setFitRequest] = useState<PlannerFitRequest>()
  const { context, preview, source, entryId, destinationId } = state

  useEffect(() => {
    let current = true
    void Promise.all([listNetworks(), listScenarios()]).then(([networks, result]) => {
      if (!current) return
      const sites = networks.filter(network => network.id === "tagum_site_a" || network.id === "tagum_site_b")
      setSources({ networks: sites, scenarios: result.scenarios.filter(scenario => scenario.network_id) })
      if (sites.length) dispatch({ type: "source", source: { kind: "network", network_id: sites[0].id } })
    }).catch(error => {
      if (current) setSourceError(error instanceof Error ? error.message : "Could not load route sources.")
    })
    return () => { current = false }
  }, [dispatch])

  function chooseSource(next: RouteSource) {
    setSelectedLaneId(null)
    setFitRequest(undefined)
    dispatch({ type: "source", source: next })
  }

  function reloadContext() {
    setSelectedLaneId(null)
    setFitRequest(undefined)
    dispatch({ type: "reload" })
  }

  const closures = activeClosures(state)
  const overlay = useMemo<PlannerOverlay>(() => ({
    original: preview?.original ?? null, selected: preview?.selected ?? null,
    sharedRoads: preview?.shared_roads ?? [], closedLaneIds: closures?.closed_lanes ?? [],
    selectedLaneId,
  }), [preview, closures, selectedLaneId])

  const selectedRoad = context?.roads.find(road => road.lane_id === selectedLaneId)
  const selectedClosed = !!selectedRoad && !!closures?.closed_lanes.includes(selectedRoad.lane_id)
  const response = selectedRoad ? closures?.closure_responses[selectedRoad.lane_id] : undefined
  const responseOptions = selectedRoad ? preview?.response_options[selectedRoad.lane_id] : undefined
  const permittedDestinations = new Set(context?.eligible_pairs.filter(pair => pair.entry_id === entryId).map(pair => pair.destination_id))
  const ready = state.contextStatus === "ready"
  const error = state.contextError ?? state.previewError

  function fit(target: PlannerFitRequest["target"]) {
    setFitRequest(previous => ({ target, revision: (previous?.revision ?? 0) + 1 }))
  }

  return <section className="flex min-w-0 flex-col gap-4 p-4 md:p-6" aria-label="Route Planner">
    <div>
      <h2 className="text-xl font-semibold">Explore road closures</h2>
      <p className="text-sm text-muted-foreground">Compare one trip with and without closures. The planner uses engine time zero with no simulated queues. Green arrows show the route, independent of signal phases.</p>
    </div>
    {sourceError ? <Alert variant="destructive"><AlertDescription>{sourceError}</AlertDescription></Alert> : null}
    {!sources && !sourceError ? <p role="status" className="text-sm">Loading sites and scenarios…</p> : null}
    {sources ? <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <NativeSelect label="Source" value={source?.kind ?? "network"} options={[
        { value: "network", label: "Temporary arrangement" },
        { value: "scenario", label: "Saved scenario", disabled: !sources.scenarios.length },
      ]} onChange={kind => {
        if (kind === "scenario" && sources.scenarios[0]) chooseSource({ kind, scenario_id: sources.scenarios[0].id })
        if (kind === "network" && sources.networks[0]) chooseSource({ kind, network_id: sources.networks[0].id })
      }} />
      {source?.kind === "scenario"
        ? <NativeSelect label="Saved scenario" value={String(source.scenario_id)}
            options={sources.scenarios.map(scenario => ({ value: String(scenario.id), label: scenario.name }))}
            onChange={id => chooseSource({ kind: "scenario", scenario_id: Number(id) })} />
        : <NativeSelect label="Study site" value={source?.network_id ?? ""}
            options={sources.networks.map(network => ({ value: network.id, label: network.name }))}
            onChange={network_id => chooseSource({ kind: "network", network_id })} />}
      <NativeSelect label="Vehicle class" value={state.vehicleType} options={vehicleOptions}
        onChange={vehicleType => dispatch({ type: "class", vehicleType: vehicleType as RouteVehicleClass })} />
      <NativeSelect label="Entry" value={entryId} disabled={!ready}
        options={[{ value: "", label: "Select an entry", disabled: true }, ...(context?.entries.map(item => ({ value: item.id, label: item.label })) ?? [])]}
        onChange={entryId => dispatch({ type: "entry", entryId })} />
      <NativeSelect label="Intended destination" value={destinationId} disabled={!ready || !entryId}
        options={[{ value: "", label: "Select a destination", disabled: true }, ...(context?.destinations
          .filter(item => permittedDestinations.has(item.id)).map(item => ({ value: item.id, label: item.label })) ?? [])]}
        onChange={destinationId => dispatch({ type: "destination", destinationId })} />
    </div> : null}
    {state.contextStatus === "loading" ? <p role="status" className="text-sm">Loading route choices…</p> : null}
    {context?.notices.map(notice => <p key={notice.code} className="text-sm text-muted-foreground">{notice.message}</p>)}
    {error ? <Alert variant="destructive">
      <AlertDescription>{error.message}</AlertDescription>
      {error.status === 409 ? <Button variant="outline" className="mt-2 w-fit" onClick={reloadContext}>Reload Route Planner context</Button> : null}
    </Alert> : null}
    {context ? <div className="grid min-w-0 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,22rem)]">
      <div className="flex min-w-0 flex-col gap-3">
        <RoutePlannerMap network={context.geometry} overlay={overlay} fitRequest={fitRequest}
          onRoadDirectionSelect={laneId => { setSelectedLaneId(laneId); dispatch({ type: "toggle", laneId }) }} />
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => fit("network")}>Fit network</Button>
          <Button size="sm" variant="outline" disabled={!preview?.original && !preview?.selected} onClick={() => fit("routes")}>Fit affected routes</Button>
          {source?.kind === "scenario"
            ? <Button size="sm" variant="outline" disabled={!ready || state.override === undefined}
                onClick={() => { setSelectedLaneId(null); dispatch({ type: "reset" }) }}>Reset to saved scenario</Button>
            : <Button size="sm" variant="outline" disabled={!ready || !closures?.closed_lanes.length}
                onClick={() => { setSelectedLaneId(null); dispatch({ type: "clear" }) }}>Clear temporary closures</Button>}
        </div>
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground" aria-label="Map legend">
          <li><span aria-hidden="true" className="text-red-600 dark:text-red-400">▧ </span>Closed pavement</li>
          <li><span aria-hidden="true">⇢ </span>Original route</li>
          <li><span aria-hidden="true" className="text-green-700 dark:text-green-400">➝ </span>Route under these conditions</li>
          <li><span aria-hidden="true" className="text-amber-700 dark:text-amber-400">⇄ </span>Shared pavement (hypothetical)</li>
        </ul>
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        <Card>
          <CardHeader><CardTitle>Road arrangement</CardTitle></CardHeader>
          <CardContent className="flex min-w-0 flex-col gap-3">
            <p className="text-sm text-muted-foreground">Click a direction on the map to close or reopen it, or use the road picker below.</p>
            {source?.kind === "scenario" && state.override !== undefined
              ? <Badge variant="secondary" className="w-fit whitespace-normal">Temporary changes — saved scenario unchanged</Badge>
              : source?.kind === "network" ? <Badge variant="secondary">Temporary arrangement</Badge> : null}
            <p className="text-sm">{closures?.closed_lanes.length ? `${closures.closed_lanes.length} closed road direction(s)` : "No roads are closed"}</p>
            <NativeSelect label="Road direction" value={selectedLaneId ?? ""} disabled={!ready}
              options={[{ value: "", label: "Select a road direction" }, ...context.roads.map(road => ({
                value: road.lane_id, label: `${road.label} · ${road.direction}`,
              }))]} onChange={laneId => setSelectedLaneId(laneId || null)} />
            {selectedRoad ? <Button size="sm" className="w-fit" variant={selectedClosed ? "outline" : "destructive"} disabled={!ready}
              onClick={() => dispatch({ type: "toggle", laneId: selectedRoad.lane_id })}>
              {selectedClosed ? "Reopen direction" : "Close direction"}
            </Button> : null}
            {selectedClosed && selectedRoad ? <>
              <NativeSelect label="Traffic response" value={response ?? ""} disabled={!ready || !responseOptions}
                options={[
                  { value: "", label: "Engine default", disabled: true },
                  ...(Object.keys(plannerHints) as ClosureResponse[]).map(value => ({
                    value, label: RESPONSE_LABELS[value], disabled: !responseOptions?.some(option => option.value === value && option.enabled),
                  })),
                ]}
                onChange={choice => {
                  const option = responseOptions?.find(option => option.value === choice && option.enabled)
                  if (option) dispatch({ type: "response", laneId: selectedRoad.lane_id, response: option.value })
                }} />
              {response ? <p className="text-sm text-muted-foreground">{plannerHints[response]}</p> : null}
              {state.coordinationNotice ? <p role="status" className="text-sm">{state.coordinationNotice}</p> : null}
              {responseOptions?.some(option => !option.enabled) ? <details className="text-sm text-muted-foreground">
                <summary className="cursor-pointer">Why some responses are unavailable</summary>
                <ul className="mt-2 flex flex-col gap-1">
                  {responseOptions.filter(option => !option.enabled).map(option =>
                    <li key={option.value}><strong>{RESPONSE_LABELS[option.value]}</strong> · {option.reason}</li>)}
                </ul>
              </details> : null}
            </> : null}
          </CardContent>
        </Card>
        <Card aria-label="Route comparison">
          <CardHeader><CardTitle>Route under these conditions</CardTitle></CardHeader>
          <CardContent aria-live="polite" className="flex min-w-0 flex-col gap-2">
            {state.previewPending ? <p role="status" className="text-sm text-muted-foreground">Updating route preview…</p> : null}
            {!state.previewPending && !preview && !error
              ? <p className="text-sm text-muted-foreground">Choose a valid entry and destination for this vehicle class.</p> : null}
            {preview ? <>
              <Badge variant={preview.arrangement_valid ? "secondary" : "destructive"} className="w-fit">{outcomeLabels[preview.outcome]}</Badge>
              <p className="text-sm">{preview.reason}</p>
              {preview.outcome === "alternative_exit" ? <dl className="grid gap-1 text-sm">
                <div><dt className="inline font-medium">Intended exit · </dt><dd className="inline">{preview.original?.destination_label}</dd></div>
                <div><dt className="inline font-medium">Selected exit · </dt><dd className="inline">{preview.selected?.destination_label}</dd></div>
              </dl> : null}
              {preview.uses_shared_pavement ? <p className="text-sm text-muted-foreground">This trip uses hypothetical shared pavement.</p> : null}
              {preview.routing_mode === "adaptive" ? <p className="text-sm text-muted-foreground">Adaptive routing · no simulated queues in this preview.</p> : null}
            </> : null}
          </CardContent>
        </Card>
      </div>
    </div> : null}
  </section>
}

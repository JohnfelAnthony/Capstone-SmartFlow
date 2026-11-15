import { useEffect, useMemo, useState } from "react"
import { FocusIcon, Undo2Icon } from "lucide-react"
import { ApiError, SESSION_RESTORED_EVENT } from "@/api/client"
import { listNetworks, type NetworkSummary } from "@/api/native-scenario"
import { listScenarios, type ApiScenario } from "@/api/scenarios"
import type { RouteSource } from "@/api/routes"
import type { VisualPoint } from "@/api/visual-network"
import { NativeSelect } from "@/components/native-scenario-controls"
import { RoutePlannerMap } from "@/components/route-planner-map"
import { EndpointList, RoadActions, TripEndpoint } from "@/components/route-planner-steps"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { activeClosures, useRoutePlanner } from "@/lib/route-planner"
import { routeScenarioDraft, type RouteScenarioDraft } from "@/lib/route-scenario"
import { buildRouteEnds, describeRoad, describeRoute, endAction, endRoles, formatDistance, routeEndsComplete, routeLengthMeters, routeStatus, type EndStep } from "@/lib/route-ends"
import type { PlannerFitRequest, PlannerMapAction, PlannerOverlay, PlannerTarget } from "@/simulation/route-planner-overlay"
import "@/styles/admin-user-management.css"
import "@/styles/route-planner.css"

type MapSelection = { target: PlannerTarget; anchor: VisualPoint | null }

export function RoutePlannerPage({ canCreateScenario = false, onSaveAsScenario }: {
  /** Needs the same permission as the New Scenario form. */
  canCreateScenario?: boolean
  onSaveAsScenario?: (draft: RouteScenarioDraft) => void
}) {
  const { state, dispatch } = useRoutePlanner()
  const [sources, setSources] = useState<{ networks: NetworkSummary[]; scenarios: ApiScenario[] } | null>(null)
  const [sourceError, setSourceError] = useState("")
  const [mapSelection, setMapSelection] = useState<MapSelection | null>(null)
  const [fitRequest, setFitRequest] = useState<PlannerFitRequest>()
  const [editingEnd, setEditingEnd] = useState<EndStep | null>(null)
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

  function resetMapControls() {
    setMapSelection(null)
    setFitRequest(undefined)
    setEditingEnd(null)
  }

  function chooseSource(next: RouteSource) {
    resetMapControls()
    dispatch({ type: "source", source: next })
  }

  function reloadContext() {
    resetMapControls()
    dispatch({ type: "reload" })
  }

  const ends = useMemo(() => context ? buildRouteEnds(context) : [], [context])
  const startLabel = ends.find(end => end.entryId === entryId)?.label
  const destinationLabel = ends.find(end => end.destinationId === destinationId)?.label
  const picking = editingEnd ?? (!startLabel ? "start" : !destinationLabel ? "destination" : null)
  const ready = state.contextStatus === "ready"
  const displayPreview = picking ? null : preview
  const pairs = useMemo(() => context?.eligible_pairs ?? [], [context])
  const alternateExit = displayPreview?.outcome === "alternative_exit" ? displayPreview.actual_destination_id : null
  const roles = useMemo(() => endRoles(ends, ready ? picking : null, pairs, entryId, destinationId, alternateExit),
    [ends, ready, picking, pairs, entryId, destinationId, alternateExit])
  const closures = activeClosures(state)
  const showBefore = Boolean(displayPreview?.original && (displayPreview.outcome !== "unchanged" || displayPreview.uses_shared_pavement))
  const target = mapSelection?.target
  const selectedRoad = target?.kind === "road" ? context?.roads.find(road => road.lane_id === target.laneId) : undefined
  const selectedPin = target?.kind === "end" ? roles.find(({ end }) => end.key === target.key) : undefined
  const selectedLaneId = selectedRoad?.lane_id ?? null
  const overlay: PlannerOverlay = {
    interactive: ready,
    original: showBefore ? displayPreview?.original ?? null : null,
    selected: displayPreview?.selected ?? null,
    sharedRoads: displayPreview?.shared_roads ?? [], closedLaneIds: closures?.closed_lanes ?? [],
    selectedLaneId,
    ends: roles.map(({ end, role, selectable }) => ({ ...end, role, selectable })),
  }

  function chooseEnd(key: string) {
    const end = ends.find(item => item.key === key)
    if (!ready || !picking || !end) return
    const action = endAction(end, picking, pairs, entryId)
    if (!action) return
    dispatch(action)
    setMapSelection(null)
    setEditingEnd(null)
  }

  function mapAction({ target, anchor, contextMenu }: PlannerMapAction) {
    const pin = target?.kind === "end" ? roles.find(({ end }) => end.key === target.key) : undefined
    if (pin?.role === "available" && !contextMenu) {
      chooseEnd(pin.end.key)
      return
    }
    setMapSelection(target ? { target, anchor } : null)
  }

  function editEndpoint(step: EndStep) {
    setMapSelection(null)
    setEditingEnd(step)
  }

  function removeEndpoint(step: EndStep) {
    setMapSelection(null)
    setEditingEnd(null)
    dispatch({ type: "remove-end", step })
  }

  function setClosure(laneIds: readonly string[], closed: boolean) {
    setMapSelection(null)
    dispatch({ type: "set-closure", laneIds, closed })
  }

  const error = state.contextError ?? state.previewError
  const closedCount = closures?.closed_lanes.length ?? 0
  const siteId = source?.kind === "network" ? source.network_id : sources?.scenarios.find(scenario => scenario.id === source?.scenario_id)?.network_id
  const [, siteDetail] = (sources?.networks.find(network => network.id === siteId)?.name ?? "").split(" — ")
  const scenarioName = source?.kind === "scenario" ? sources?.scenarios.find(scenario => scenario.id === source.scenario_id)?.name : undefined
  const scenarioDraft = context ? routeScenarioDraft({ source, context, closures, scenarioName }) : null
  const distance = displayPreview?.selected ? formatDistance(routeLengthMeters(displayPreview.selected)) : null
  const routeDescription = displayPreview && context && displayPreview.outcome !== "unchanged"
    ? describeRoute({ preview: displayPreview, context, ends, entryId, destinationId, closedCount }) : ""
  const choices = roles.filter(end => end.selectable).map(({ end }) => end)
  const mapPrompt = state.contextStatus === "error" ? "Map selection unavailable" : !ready ? "Updating the map…" :
    picking === "start" ? "Pick a start on the map" : picking === "destination" ? "Pick a destination on the map" :
    state.previewPending ? "Finding the route…" : error ? "Route preview unavailable" : "Explore the route"
  const lastClosureEdit = state.lastClosureEdit
  const pinStep = selectedPin?.role === "start" || selectedPin?.role === "destination" ? selectedPin.role : null
  const popup = ready && selectedRoad && context ? {
    anchor: mapSelection?.anchor ?? null,
    title: describeRoad(selectedRoad),
    content: <RoadActions key={selectedRoad.lane_id} laneId={selectedRoad.lane_id}
      segmentDirections={context.roads.filter(road => road.road_id === selectedRoad.road_id).map(road => road.lane_id)}
      closures={closures} preview={preview} coordinationNotice={state.coordinationNotice} onSetClosure={setClosure}
      onRespond={(laneId, response) => dispatch({ type: "response", laneId, response })} />,
  } : ready && selectedPin && (pinStep || selectedPin.selectable && picking) ? {
    anchor: mapSelection?.anchor ?? null,
    title: selectedPin.end.label,
    content: pinStep ? <div className="flex flex-col gap-2">
      <Button size="sm" variant="outline" onClick={() => editEndpoint(pinStep)}>Change {pinStep}</Button>
      <Button size="sm" variant="ghost" onClick={() => removeEndpoint(pinStep)}>Remove {pinStep}</Button>
    </div> : <Button size="sm" onClick={() => chooseEnd(selectedPin.end.key)}>Set {picking}</Button>,
  } : null

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
    {context && routeEndsComplete(context, ends) ? <div className="route-planner-workspace">
      <div className="flex min-w-0 flex-col gap-3">
        <div className="route-planner-map-bar">
          <h2 aria-live="polite" className="font-medium">{mapPrompt}</h2>
          <div className="flex flex-wrap gap-2">
            {lastClosureEdit ? <Button variant="outline" size="sm" disabled={!ready}
              onClick={() => { setMapSelection(null); dispatch({ type: "undo-closure" }) }}>
              <Undo2Icon data-icon="inline-start" />{lastClosureEdit.closed ? "Undo closure" : "Undo reopening"}
            </Button> : null}
            {editingEnd ? <Button size="sm" variant="ghost" onClick={() => setEditingEnd(null)}>Cancel selection</Button> : null}
            {overlay.original || overlay.selected ? <Button size="sm" variant="outline"
              onClick={() => setFitRequest(previous => ({ target: "routes", revision: (previous?.revision ?? 0) + 1 }))}>
              <FocusIcon data-icon="inline-start" />Fit route
            </Button> : null}
          </div>
        </div>
        <RoutePlannerMap network={context.geometry} overlay={overlay} fitRequest={fitRequest}
          onAction={mapAction} onRemoveEnd={removeEndpoint} popup={popup} onDismiss={() => setMapSelection(null)} />
        <p className="text-sm text-muted-foreground">Click or tap a road for closure options.</p>
        {overlay.original || overlay.selected || closedCount ? <ul className="route-planner-legend" aria-label="Map legend">
          {overlay.original ? <li><span aria-hidden="true" data-line="before" />Before closure</li> : null}
          {overlay.selected ? <li><span aria-hidden="true" data-line="route" />{overlay.original ? "After closure" : "Route"}</li> : null}
          {closedCount ? <li><span aria-hidden="true" data-line="closed" />Closed direction</li> : null}
          {overlay.sharedRoads.length ? <li><span aria-hidden="true" data-line="shared" />Shared pavement (hypothetical)</li> : null}
        </ul> : null}
      </div>
      <aside className="flex min-w-0 flex-col gap-3" aria-label="Trip controls">
        <Card>
          <CardHeader>
            <CardTitle><h2>Trip</h2></CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <ol className="flex flex-col gap-2" aria-label="Trip endpoints">
              <TripEndpoint step="start" label={startLabel} active={picking === "start"} disabled={!ready} onChange={() => editEndpoint("start")} />
              <TripEndpoint step="destination" label={destinationLabel} active={picking === "destination"} disabled={!ready} onChange={() => editEndpoint("destination")} />
            </ol>
            {ready && picking && choices.length ? <EndpointList key={picking} step={picking} ends={choices} onPick={chooseEnd} /> : null}
            {ready && picking && !choices.length ? <p className="text-sm text-muted-foreground">No eligible points for this trip.</p> : null}
            {!picking ? <>
              <Separator />
              <div className="flex flex-col gap-1" aria-label="Route result" aria-live="polite">
                {state.previewPending ? <p>Updating the route…</p> : null}
                {displayPreview ? <>
                  <p className="font-semibold">{routeStatus(displayPreview, closedCount)}</p>
                  {routeDescription ? <p>{routeDescription}</p> : distance ? <p>About {distance}</p> : null}
                  <p className="text-xs text-muted-foreground">Preview at the start of a run, with no queues.</p>
                  <details className="route-planner-details">
                    <summary>Why this route?</summary>
                    <p className="pt-2">{displayPreview.reason}</p>
                    {displayPreview.uses_shared_pavement ? <p>This trip uses hypothetical shared pavement.</p> : null}
                    {displayPreview.routing_mode === "adaptive" ? <p>Adaptive routing is enabled.</p> : null}
                  </details>
                </> : null}
              </div>
            </> : null}
          </CardContent>
        </Card>
        {context.notices.map(notice => <p key={notice.code} className="text-sm text-muted-foreground">{notice.message}</p>)}
        <details className="route-planner-details route-planner-options">
          <summary>More options</summary>
          <div className="flex flex-col gap-4 py-3">
            <NativeSelect label="Choose a road from a list" value={selectedLaneId ?? ""} disabled={!ready}
              options={[{ value: "", label: "Select a direction" }, ...context.roads.map(road => ({ value: road.lane_id, label: describeRoad(road) }))]}
              onChange={laneId => setMapSelection(laneId ? { target: { kind: "road", laneId }, anchor: null } : null)} />
            {sources?.scenarios.length ? <NativeSelect label="Start from a saved scenario" value={source?.kind === "scenario" ? String(source.scenario_id) : ""}
              options={[{ value: "", label: "None (temporary arrangement)" }, ...sources.scenarios.map(scenario => ({ value: String(scenario.id), label: scenario.name }))]}
              onChange={id => id ? chooseSource({ kind: "scenario", scenario_id: Number(id) })
                : sources.networks[0] && chooseSource({ kind: "network", network_id: siteId ?? sources.networks[0].id })} /> : null}
            {source?.kind === "scenario"
              ? <Button size="sm" variant="outline" className="w-fit" disabled={!ready || state.override === undefined}
                  onClick={() => { setMapSelection(null); dispatch({ type: "reset" }) }}>Reset to saved scenario</Button>
              : <Button size="sm" variant="outline" className="w-fit" disabled={!ready || !closedCount}
                  onClick={() => { setMapSelection(null); dispatch({ type: "clear" }) }}>Reopen all roads</Button>}
            {scenarioDraft && canCreateScenario && onSaveAsScenario
              ? <Button size="sm" variant="outline" className="w-fit" onClick={() => onSaveAsScenario(scenarioDraft)}>Save as new scenario</Button> : null}
          </div>
        </details>
      </aside>
    </div> : null}
  </main>
}

import { describe, expect, it } from "vitest"
import type { RouteContext, RoutePreview } from "@/api/routes"
import type { VisualNetwork } from "@/api/visual-network"
import { activeClosures, initialRoutePlannerState, makePreviewRequest, routePlannerReducer } from "./route-planner"

const context: RouteContext = {
  source: { kind: "scenario", scenario_id: 17 },
  source_label: "Saved site",
  network_id: "site-a",
  network_sha256: "a".repeat(64),
  network_binding: "saved_fingerprint",
  geometry: {} as VisualNetwork,
  entries: [{ id: "west", label: "West", lane_ids: ["entry"] }],
  destinations: [{ id: "north", label: "North", lane_ids: ["exit"] }],
  eligible_pairs: [{ entry_id: "west", destination_id: "north" }],
  initial_closures: { closed_lanes: ["a", "b"], closure_responses: { a: "side_street", b: "side_street" } },
  roads: ["a", "b", "entry"].map(lane_id => ({ lane_id, road_id: lane_id, label: lane_id, direction: "Eastbound" })),
  basis: "initial_arrangement_zero_queue",
  has_later_closure_changes: false,
  notices: [],
}

function readyWithoutTrip() {
  const loading = routePlannerReducer(initialRoutePlannerState, { type: "source", source: context.source })
  return routePlannerReducer(loading, { type: "context-ready", generation: loading.contextGeneration, context })
}

function ready() {
  const withStart = routePlannerReducer(readyWithoutTrip(), { type: "entry", entryId: "west" })
  return routePlannerReducer(withStart, { type: "destination", destinationId: "north" })
}

function refreshAfterSignIn(state: ReturnType<typeof ready>) {
  const expired = routePlannerReducer(state, { type: "context-error", generation: state.contextGeneration,
    error: { status: 401, message: "Sign in" } })
  return routePlannerReducer(expired, { type: "session-restored" })
}

describe("temporary route-planner state", () => {
  it("waits for both choices and clears an incompatible destination when the start changes", () => {
    const empty = readyWithoutTrip()
    expect(empty).toMatchObject({ entryId: "", destinationId: "" })
    const started = routePlannerReducer(empty, { type: "entry", entryId: "west" })
    expect(started.destinationId).toBe("")
    expect(makePreviewRequest(started)).toBeNull()
    const complete = routePlannerReducer(started, { type: "destination", destinationId: "north" })
    expect(makePreviewRequest(complete)).toMatchObject({ entry_id: "west", destination_id: "north" })
    const withAnotherStart = { ...complete, context: { ...context,
      eligible_pairs: [...context.eligible_pairs, { entry_id: "south", destination_id: "east" }] } }
    const changed = routePlannerReducer(withAnotherStart, { type: "entry", entryId: "south" })
    expect(changed).toMatchObject({ entryId: "south", destinationId: "" })
    expect(makePreviewRequest(changed)).toBeNull()
  })

  it("distinguishes saved closures, an explicit empty arrangement and reset", () => {
    const state = ready()
    expect(makePreviewRequest(state)).not.toHaveProperty("closure_override")
    const cleared = routePlannerReducer(state, { type: "clear" })
    expect(makePreviewRequest(cleared)?.closure_override).toEqual({ closed_lanes: [], closure_responses: {} })
    const reset = routePlannerReducer(cleared, { type: "reset" })
    expect(makePreviewRequest(reset)).not.toHaveProperty("closure_override")
    expect(activeClosures(reset)).toEqual(context.initial_closures)
  })

  it("changes side-street responses together and leaves the source untouched", () => {
    const before = structuredClone(context)
    const state = routePlannerReducer(ready(), { type: "response", laneId: "a", response: "side_street_adaptive" })
    expect(activeClosures(state)?.closure_responses).toEqual({ a: "side_street_adaptive", b: "side_street_adaptive" })
    expect(state.coordinationNotice).toMatch(/1 other/)
    expect(context).toEqual(before)
  })

  it("undos a temporary closure by restoring the saved arrangement without an override", () => {
    const state = ready()
    const closed = routePlannerReducer(state, { type: "set-closure", laneIds: ["entry"], closed: true })
    expect(makePreviewRequest(closed)?.closure_override?.closed_lanes).toContain("entry")
    const restored = routePlannerReducer(closed, { type: "undo-closure" })
    expect(makePreviewRequest(restored)).toEqual(makePreviewRequest(state))
    expect(activeClosures(restored)).toBe(context.initial_closures)
    expect(restored.lastClosureEdit).toBeNull()
  })

  it("applies two directions as one action and restores both responses when reopening is undone", () => {
    const state = ready()
    const opened = routePlannerReducer(state, { type: "set-closure", laneIds: ["a", "b"], closed: false })
    expect(activeClosures(opened)).toEqual({ closed_lanes: [], closure_responses: {} })
    const undone = routePlannerReducer(opened, { type: "undo-closure" })
    expect(activeClosures(undone)).toEqual(context.initial_closures)
    const closed = routePlannerReducer(opened, { type: "set-closure", laneIds: ["a", "b"], closed: true })
    expect(activeClosures(closed)?.closed_lanes).toEqual(["a", "b"])
    expect(activeClosures(routePlannerReducer(closed, { type: "undo-closure" }))).toEqual(activeClosures(opened))
  })

  it.each(["start", "destination"] as const)("removing the %s keeps the other pin and invalidates its route", step => {
    const before = routePlannerReducer(ready(), { type: "set-closure", laneIds: ["entry"], closed: true })
    const result = routePlannerReducer(before, { type: "remove-end", step })
    expect(result.entryId).toBe(step === "start" ? "" : "west")
    expect(result.destinationId).toBe(step === "destination" ? "" : "north")
    expect(makePreviewRequest(result)).toBeNull()
    expect(result.previewGeneration).toBeGreaterThan(before.previewGeneration)
    expect(activeClosures(result)).toEqual(activeClosures(before))
  })

  it("uses the latest saved closure snapshot for the next edit and reset", () => {
    const state = ready()
    const effective = { closed_lanes: ["entry"], closure_responses: { entry: "wait" as const } }
    const preview: RoutePreview = {
      network_id: context.network_id, network_sha256: context.network_sha256, basis: context.basis,
      routing_mode: "static", arrangement_valid: true, effective_closures: effective,
      effective_closed_lanes: effective.closed_lanes, response_options: {}, original: null, selected: null,
      outcome: "waiting_entry", reason: "Entry is closed", intended_destination_id: "north",
      actual_destination_id: null, shared_roads: [], uses_shared_pavement: false, notices: [],
    }
    const resolved = routePlannerReducer(state, { type: "preview-ready", generation: state.previewGeneration, preview })
    expect(activeClosures(resolved)).toEqual(effective)

    const pickingTrip = routePlannerReducer(resolved, { type: "destination", destinationId: "north" })
    expect(pickingTrip.preview).toBeNull()
    expect(activeClosures(pickingTrip)).toEqual(effective)
    const edited = routePlannerReducer(pickingTrip, { type: "set-closure", laneIds: ["b"], closed: true })
    expect(makePreviewRequest(edited)?.closure_override).toEqual({
      closed_lanes: ["b", "entry"], closure_responses: { entry: "wait" },
    })
    const reset = routePlannerReducer(edited, { type: "reset" })
    expect(activeClosures(reset)).toEqual(effective)
    expect(makePreviewRequest(reset)).not.toHaveProperty("closure_override")
    expect(context.initial_closures.closed_lanes).toEqual(["a", "b"])
  })

  it("clears invalid trips when the refreshed context changes eligible choices", () => {
    const refreshing = refreshAfterSignIn(ready())
    expect(refreshing.context?.geometry).toBe(context.geometry)
    expect(makePreviewRequest(refreshing)).toBeNull()
    const restricted = routePlannerReducer(refreshing, { type: "context-ready", generation: refreshing.contextGeneration,
      context: { ...context, destinations: [], eligible_pairs: [] } })
    expect(restricted.destinationId).toBe("")
    expect(makePreviewRequest(restricted)).toBeNull()
  })

  it("ignores stale source and preview responses, including an older arrangement on the same site", () => {
    const state = ready()
    const changed = routePlannerReducer(state, { type: "clear" })
    const oldPreview = { network_sha256: context.network_sha256 } as RoutePreview
    expect(routePlannerReducer(changed, { type: "preview-ready", generation: state.previewGeneration, preview: oldPreview })).toBe(changed)
    const otherSite = routePlannerReducer(state, { type: "source", source: { kind: "network", network_id: "site-b" } })
    expect(routePlannerReducer(otherSite, { type: "context-ready", generation: state.contextGeneration, context })).toBe(otherSite)
    expect(otherSite.context).toBeNull()
    expect(makePreviewRequest(otherSite)).toBeNull()
  })

  it("does not silently apply old temporary closures when a context refresh sees a new map revision", () => {
    const changed = routePlannerReducer(ready(), { type: "set-closure", laneIds: ["entry"], closed: true })
    const loading = refreshAfterSignIn(changed)
    const refreshed = routePlannerReducer(loading, { type: "context-ready", generation: loading.contextGeneration,
      context: { ...context, network_sha256: "b".repeat(64) } })
    expect(refreshed.contextError?.status).toBe(409)
    expect(makePreviewRequest(refreshed)).toBeNull()
    expect(refreshed.context?.network_sha256).toBe(context.network_sha256)
  })

  it("retries only session-blocked planner requests and preserves temporary closures", () => {
    const edited = routePlannerReducer(ready(), { type: "set-closure", laneIds: ["entry"], closed: true })
    const failed = routePlannerReducer(edited, { type: "preview-error", generation: edited.previewGeneration,
      error: { status: 401, message: "Sign in" } })
    const restored = routePlannerReducer(failed, { type: "session-restored" })
    expect(restored.previewPending).toBe(true)
    expect(restored.previewGeneration).toBeGreaterThan(failed.previewGeneration)
    expect(makePreviewRequest(restored)).toEqual(makePreviewRequest(edited))
    expect(routePlannerReducer(restored, { type: "session-restored" })).toBe(restored)

    const recovered = refreshAfterSignIn(edited)
    expect(recovered.contextStatus).toBe("loading")
    expect(recovered.contextGeneration).toBeGreaterThan(edited.contextGeneration)
    expect(activeClosures(recovered)).toEqual(activeClosures(edited))
  })

  it("requires a fresh fingerprint after reload and rejects mismatched preview geometry", () => {
    const state = ready()
    const mismatched = { network_sha256: "b".repeat(64) } as RoutePreview
    const rejected = routePlannerReducer(state, { type: "preview-ready", generation: state.previewGeneration, preview: mismatched })
    expect(rejected.preview).toBeNull()
    expect(rejected.previewError?.status).toBe(409)
    const reload = routePlannerReducer(rejected, { type: "reload" })
    expect(reload.context).toBeNull()
    expect(makePreviewRequest(reload)).toBeNull()
  })
})

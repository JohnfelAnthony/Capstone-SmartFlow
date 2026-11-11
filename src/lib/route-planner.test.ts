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

function ready() {
  const loading = routePlannerReducer(initialRoutePlannerState, { type: "source", source: context.source })
  return routePlannerReducer(loading, { type: "context-ready", generation: loading.contextGeneration, context })
}

describe("temporary route-planner state", () => {
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
    const edited = routePlannerReducer(pickingTrip, { type: "toggle", laneId: "b" })
    expect(makePreviewRequest(edited)?.closure_override).toEqual({
      closed_lanes: ["b", "entry"], closure_responses: { entry: "wait" },
    })
    const reset = routePlannerReducer(edited, { type: "reset" })
    expect(activeClosures(reset)).toEqual(effective)
    expect(makePreviewRequest(reset)).not.toHaveProperty("closure_override")
    expect(context.initial_closures.closed_lanes).toEqual(["a", "b"])
  })

  it("clears invalid trips on a class change and waits for new eligible choices", () => {
    const truck = routePlannerReducer(ready(), { type: "class", vehicleType: "truck" })
    expect(truck.context?.geometry).toBe(context.geometry)
    expect(makePreviewRequest(truck)).toBeNull()
    const restricted = routePlannerReducer(truck, { type: "context-ready", generation: truck.contextGeneration,
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

  it("does not silently apply old temporary closures when a class change sees a new map revision", () => {
    const changed = routePlannerReducer(ready(), { type: "toggle", laneId: "entry" })
    const loading = routePlannerReducer(changed, { type: "class", vehicleType: "truck" })
    const refreshed = routePlannerReducer(loading, { type: "context-ready", generation: loading.contextGeneration,
      context: { ...context, network_sha256: "b".repeat(64) } })
    expect(refreshed.contextError?.status).toBe(409)
    expect(makePreviewRequest(refreshed)).toBeNull()
    expect(refreshed.context?.network_sha256).toBe(context.network_sha256)
  })

  it("retries only session-blocked planner requests and preserves temporary closures", () => {
    const edited = routePlannerReducer(ready(), { type: "toggle", laneId: "entry" })
    const failed = routePlannerReducer(edited, { type: "preview-error", generation: edited.previewGeneration,
      error: { status: 401, message: "Sign in" } })
    const restored = routePlannerReducer(failed, { type: "session-restored" })
    expect(restored.previewPending).toBe(true)
    expect(restored.previewGeneration).toBeGreaterThan(failed.previewGeneration)
    expect(makePreviewRequest(restored)).toEqual(makePreviewRequest(edited))
    expect(routePlannerReducer(restored, { type: "session-restored" })).toBe(restored)

    const loading = routePlannerReducer(edited, { type: "class", vehicleType: "truck" })
    const unavailable = routePlannerReducer(loading, { type: "context-error", generation: loading.contextGeneration,
      error: { status: 401, message: "Sign in" } })
    const recovered = routePlannerReducer(unavailable, { type: "session-restored" })
    expect(recovered.contextStatus).toBe("loading")
    expect(recovered.contextGeneration).toBeGreaterThan(unavailable.contextGeneration)
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

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
  destinations: [{ id: "north", label: "North" }],
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

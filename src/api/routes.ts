import { apiRequest } from "@/api/client"
import type { VisualNetwork, VisualPoint } from "@/api/visual-network"
import type { SharedRoad } from "@/simulation/frame-types"

export type RouteSource =
  | { kind: "scenario"; scenario_id: number }
  | { kind: "network"; network_id: string }

export type RouteVehicleClass = "car" | "motorcycle" | "tricycle" | "bus" | "truck"
export type ClosureResponse = "side_street" | "side_street_adaptive" | "share" | "nearest_exit" | "wait"
export type ClosureOverride = {
  closed_lanes: string[]
  closure_responses: Record<string, ClosureResponse>
}

export type RouteContextRequest = { source: RouteSource; vehicle_type: RouteVehicleClass }
export type RoutePreviewRequest = RouteContextRequest & {
  expected_network_sha256: string
  entry_id: string
  destination_id: string
  closure_override?: ClosureOverride
}

type RouteNotice = { code: string; message: string }
type RouteBoundary = { id: string; label: string }
type RouteBasis = "initial_arrangement_zero_queue"

export type RouteContext = {
  source: RouteSource
  source_label: string
  network_id: string
  network_sha256: string
  network_binding: "saved_fingerprint" | "current_unpinned" | "current_network"
  geometry: VisualNetwork
  entries: Array<RouteBoundary & { lane_ids: string[] }>
  destinations: Array<RouteBoundary & { lane_ids: string[] }>
  eligible_pairs: Array<{ entry_id: string; destination_id: string }>
  initial_closures: ClosureOverride
  roads: Array<{ lane_id: string; road_id: string; label: string; direction: string }>
  basis: RouteBasis
  has_later_closure_changes: boolean
  notices: RouteNotice[]
}

export type RouteSegment =
  | { kind: "lane"; lane_id: string; points: VisualPoint[] }
  | { kind: "connector"; from_lane_id: string; to_lane_id: string; points: VisualPoint[] }

export type RoutePath = {
  lane_ids: string[]
  destination_id: string
  destination_label: string
  segments: RouteSegment[]
}

export type RoutePreview = {
  network_id: string
  network_sha256: string
  basis: RouteBasis
  routing_mode: "static" | "adaptive"
  arrangement_valid: boolean
  effective_closures: ClosureOverride
  effective_closed_lanes: string[]
  response_options: Record<string, Array<{ value: ClosureResponse; enabled: boolean; reason: string | null }>>
  original: RoutePath | null
  selected: RoutePath | null
  outcome: "unchanged" | "detour" | "alternative_exit" | "waiting_entry" | "no_route" | "invalid_arrangement"
  reason: string
  intended_destination_id: string
  actual_destination_id: string | null
  shared_roads: SharedRoad[]
  uses_shared_pavement: boolean
  notices: RouteNotice[]
}

export function getRouteContext(body: RouteContextRequest, signal?: AbortSignal) {
  return apiRequest<RouteContext>("/api/routes/context", { method: "POST", body, signal })
}

export function previewRoute(body: RoutePreviewRequest, signal?: AbortSignal) {
  return apiRequest<RoutePreview>("/api/routes/preview", { method: "POST", body, signal })
}

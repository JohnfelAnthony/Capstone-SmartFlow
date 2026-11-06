import { apiRequest } from "@/api/client"
import type { VehicleMixPreset } from "@/lib/vehicle-mix"

export type SignalPlan = {
  mode: "signalized" | "all_way_stop" | "first_come"
  /** Each item is an approach, "pedestrian", or a group of approaches that share a green. */
  phase_order: (string | string[])[]
  /** One green per phase_order item; absent means every phase uses green_seconds. */
  phase_greens?: number[]
  green_seconds: number
  minimum_green: number
  maximum_green: number
  yellow_seconds: number
  all_red_seconds: number
  offset_seconds: number
  /** Absent means automatic: 120 s, or the plan's own fixed-time red if longer. */
  maximum_red_seconds?: number
  /** Absent means on_call. */
  pedestrian_phase?: "on_call" | "every_cycle"
}

export type LaneEvent = {
  time: number
  lane_id: string
  closed?: boolean
  speed_factor?: number
  label?: string
}

/** Per-site physical calibration (design 0.15). Absent means the engine defaults; the complete object is kept through save and edit. */
export type SiteCalibration = {
  schema_version: 1
  network_id: string
  first_come_approach_speed_mps: number
  approach_zone_m: number
  turn_speed_mps: number
  class_speed_factors: Record<"car" | "motorcycle" | "tricycle" | "bus" | "truck", number>
}

export type NativeScenarioConfig = {
  traffic_density?: string
  pedestrian_density?: string
  controlled_junction?: string
  green_seconds?: number
  closed_lanes?: string[]
  /** How traffic responds to each closed lane (see src/lib/closures.ts); absent for a lane means the behaviour closures always had. */
  closure_responses?: Record<string, string>
  slow_lanes?: Record<string, number>
  events?: LaneEvent[]
  signal_plans?: Record<string, Partial<SignalPlan>>
  routing_mode?: "adaptive" | "static"
  reroute_interval?: number
  reroute_improvement?: number
  demand_source?: { kind: "synthetic" | "observed" | "field_counts"; description?: string }
  vehicle_mix?: Record<string, number>
  demand_windows?: unknown[]
  site_calibration?: SiteCalibration
  [setting: string]: unknown
}

export type NativeScenarioOptions = {
  network_id: string
  network_name: string
  network_sha256: string
  defaults: NativeScenarioConfig
  /** True at the study sites: traffic reroutes around closed roads only, unless a closure's response is "avoid jams". */
  routing_follows_closure_choice?: boolean
  junctions: Array<{ id: string; label: string; approaches: string[]; default_plan: SignalPlan }>
  boundaries: Array<{ id: string; label: string }>
  lanes: Array<{ id: string; label: string; road_name: string; source: string; target: string; speed_mps: number
    /** Road piece this lane belongs to (both directions share it), the compass direction of travel, entry/exit/link, and where the piece lies. */
    road_id: string; direction: string; kind: "entry" | "exit" | "link"; where: string }>
  vehicle_mix_presets: Record<string, VehicleMixPreset>
}

export type NetworkSummary = { id: string; name: string; sha256: string; junctions: number }

export function listNetworks() {
  return apiRequest<NetworkSummary[]>("/api/networks")
}

export function getNativeScenarioOptions(networkId?: string) {
  const query = networkId ? `?network_id=${encodeURIComponent(networkId)}` : ""
  return apiRequest<NativeScenarioOptions>(`/api/simulation/options${query}`)
}

export type ClosureReport = {
  network_id: string
  valid: boolean
  /** Plain-language reason when the closures leave no legal movement anywhere. */
  message: string | null
  pieces: Record<string, { has_detour: boolean; trips_using: number; trips_without_route: number
    /** Responses that really work for this piece given the whole selection, and the one to preselect. */
    responses: string[]; default_response: string }>
  selection: { trips: number; trips_without_route: number }
}

/** The real routing check: which road pieces have a detour, and whether these closures leave any legal movement. */
export function checkClosures(networkId: string, closedLanes: string[], events: LaneEvent[]) {
  return apiRequest<ClosureReport>(`/api/networks/${encodeURIComponent(networkId)}/closure-check`, { method: "POST", body: { closed_lanes: closedLanes, events } })
}

export function resolveNativeScenario(scenarioId: number) {
  return apiRequest<{ engine_config: NativeScenarioConfig }>(`/api/scenarios/${scenarioId}/native-config`)
}

export type FieldCountsSummary = {
  vehicles: number; bins: number; bin_seconds: number; span_seconds: number; vehicles_per_hour: number
  by_approach_class: Record<string, Record<string, number>>; turns: Record<string, number>
  class_mapping: Array<{ field_class: string; engine_class: string; vehicles: number; pending_team_decision: boolean; note: string }>
  not_simulated: Record<string, number>; not_counted_at_the_end: number; limits: string; rate_note: string
  source: { take_id: string; revision: string; manifest_sha256: string }
}

/** A reviewed Field Observer export (its five files, by name) as scenario demand. Nothing is saved until the scenario is. */
export function importFieldObserverCounts(payload: { network_id: string; engine_config: NativeScenarioConfig; files: Record<string, string> }) {
  return apiRequest<{ engine_config: NativeScenarioConfig; summary: FieldCountsSummary }>("/api/scenarios/field-observer-counts", { method: "POST", body: payload })
}

export function importMovementCounts(payload: { csv_text: string; network_id: string; engine_config: NativeScenarioConfig }) {
  return apiRequest<{ engine_config: NativeScenarioConfig; rows: number; vehicles_per_hour: number }>(
    "/api/scenarios/movement-counts", { method: "POST", body: payload })
}

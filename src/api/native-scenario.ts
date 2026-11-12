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
  /** Pedestrians per hour, present only with pedestrian_density "counted" (a peak-traffic video count). */
  pedestrian_rate_per_hour?: number
  controlled_junction?: string
  green_seconds?: number
  /** Hidden warm-up before a live run or recording; absent in an old saved scenario, which the server resolves to its default. */
  warmup_seconds?: number
  closed_lanes?: string[]
  /** How traffic responds to each closed lane (see src/lib/closures.ts); absent for a lane means the behaviour closures always had. */
  closure_responses?: Record<string, string>
  slow_lanes?: Record<string, number>
  events?: LaneEvent[]
  signal_plans?: Record<string, Partial<SignalPlan>>
  routing_mode?: "adaptive" | "static"
  reroute_interval?: number
  reroute_improvement?: number
  demand_source?: { kind: "synthetic" | "observed" | "field_counts"; description?: string; datasets?: Array<{ schema?: string; sha256?: string }> }
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

/** Mirrors the live and recording rules in scenario_config.py. */
export function effectiveWarmupSeconds(config: NativeScenarioConfig, defaultSeconds: number) {
  if ((config.trips as unknown[] | undefined)?.length || (config.pedestrian_trips as unknown[] | undefined)?.length) return 0
  const windows = config.demand_windows ?? []
  const steady = windows.length > 0
    ? windows.every((window) => {
      const bounds = window as { start?: number; end?: number } | null
      return bounds?.start === 0 && bounds.end === 86_400
    })
    : ["low", "medium", "high", "very high"].includes(String(config.traffic_density ?? "").toLowerCase())
  return steady ? (config.warmup_seconds ?? defaultSeconds) : 0
}

export type PeakRoad = { approach: string; name: string; arriving: number; leaving: number; arriving_assumed: boolean; leaving_assumed: boolean }

export type PeakCountsSummary = {
  label: string; traffic_label: string; video: { file: string; seconds: number; take_id: string; source_sha256: string }
  method: "manual" | "automatic_detector"; reviewed: boolean; count_direction: "leaving" | "arriving"
  counted_vehicles: number; assumed_vehicles: number; vehicles_per_hour: number; entering: Record<"5" | "10" | "15", number>
  by_type: Record<string, number>; roads: PeakRoad[]; pedestrians: { counted: number; per_hour: number } | null; notes: string[]; dataset_sha256: string
}

/** The site's peak-traffic video count as the draft's demand. Nothing is saved until the scenario is. */
export function getPeakCounts(payload: { network_id: string; engine_config: NativeScenarioConfig }) {
  return apiRequest<{ engine_config: NativeScenarioConfig; summary: PeakCountsSummary }>("/api/scenarios/peak-counts", { method: "POST", body: payload })
}

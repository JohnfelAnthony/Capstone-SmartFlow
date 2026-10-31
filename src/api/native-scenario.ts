import { API_BASE_URL, apiRequest } from "@/api/client"
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
  slow_lanes?: Record<string, number>
  events?: LaneEvent[]
  signal_plans?: Record<string, Partial<SignalPlan>>
  routing_mode?: "adaptive" | "static"
  reroute_interval?: number
  reroute_improvement?: number
  demand_source?: { kind: "synthetic" | "observed"; description?: string }
  vehicle_mix?: Record<string, number>
  site_calibration?: SiteCalibration
  [setting: string]: unknown
}

export type NativeScenarioOptions = {
  network_id: string
  network_name: string
  network_sha256: string
  defaults: NativeScenarioConfig
  junctions: Array<{ id: string; label: string; approaches: string[]; default_plan: SignalPlan }>
  boundaries: Array<{ id: string; label: string }>
  lanes: Array<{ id: string; label: string; road_name: string; source: string; target: string; speed_mps: number }>
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

export async function downloadObservationTemplate(kind: string, example: boolean, networkId?: string) {
  const network = networkId ? `&network_id=${encodeURIComponent(networkId)}` : ""
  const result = await apiRequest<{ filename: string; csv_text: string; network_id: string; network_sha256: string }>(
    `/api/scenarios/observations/template?kind=${encodeURIComponent(kind)}&example=${example}${network}`)
  const link = document.createElement("a")
  link.href = `${API_BASE_URL}/api/scenarios/observations/template?kind=${encodeURIComponent(kind)}&example=${example}&format=csv${network}`
  link.download = result.filename
  document.body.appendChild(link)
  try {
    link.click()
  } finally {
    link.remove()
  }
  return result
}

export function resolveNativeScenario(scenarioId: number) {
  return apiRequest<{ engine_config: NativeScenarioConfig }>(`/api/scenarios/${scenarioId}/native-config`)
}

export function importObservationCsv(payload: {
  kind: "trips" | "od_counts" | "turn_counts" | "pedestrian_counts"
  source_kind: "synthetic" | "observed"
  csv_text: string
  source_description: string
  collected_on: string
  collection_start?: string
  collection_end?: string
  engine_config: NativeScenarioConfig
  network_id?: string
}) {
  return apiRequest<{ engine_config: NativeScenarioConfig; summary: { row_count: number; arrival_count: number; sha256: string; conversion: string } }>(
    "/api/scenarios/observations/import", { method: "POST", body: payload })
}

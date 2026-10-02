import { API_BASE_URL, apiRequest } from "@/api/client"

export type SignalPlan = {
  mode: "signalized" | "all_way_stop"
  phase_order: string[]
  green_seconds: number
  minimum_green: number
  maximum_green: number
  yellow_seconds: number
  all_red_seconds: number
  offset_seconds: number
}

export type LaneEvent = {
  time: number
  lane_id: string
  closed?: boolean
  speed_factor?: number
  label?: string
}

export type NativeScenarioConfig = {
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
}

export function getNativeScenarioOptions() {
  return apiRequest<NativeScenarioOptions>("/api/simulation/options")
}

export async function downloadObservationTemplate(kind: string, example: boolean) {
  const result = await apiRequest<{ filename: string; csv_text: string; network_id: string; network_sha256: string }>(
    `/api/scenarios/observations/template?kind=${encodeURIComponent(kind)}&example=${example}`)
  const link = document.createElement("a")
  link.href = `${API_BASE_URL}/api/scenarios/observations/template?kind=${encodeURIComponent(kind)}&example=${example}&format=csv`
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
}) {
  return apiRequest<{ engine_config: NativeScenarioConfig; summary: { row_count: number; arrival_count: number; sha256: string; conversion: string } }>(
    "/api/scenarios/observations/import", { method: "POST", body: payload })
}

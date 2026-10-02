import { apiRequest } from "@/api/client"
import type { NativeScenarioConfig } from "@/api/native-scenario"

export type ApiScenario = {
  id: number
  name: string
  description: string | null
  traffic_density: string
  pedestrian_density: string
  emergency_mode: string
  road_constraint: string
  intersection_id: string
  engine_config: NativeScenarioConfig
  lane_closure_config: Record<string, unknown>
  construction_config: Record<string, unknown>
  accident_config: Record<string, unknown>
  flooding_config: Record<string, unknown>
  created_by: number | null
  created_at: string | null
  updated_at: string | null
  is_official: boolean
  is_archived: boolean
}

export type ScenarioListResponse = {
  scenarios: ApiScenario[]
}

export type ScenarioWritePayload = {
  name: string
  description?: string
  traffic_density: string
  pedestrian_density: string
  emergency_mode: string
  road_constraint: string
  intersection_id: string
  engine_config?: NativeScenarioConfig
  lane_closure_config?: Record<string, unknown>
  construction_config?: Record<string, unknown>
  accident_config?: Record<string, unknown>
  flooding_config?: Record<string, unknown>
}

export function listScenarios(options: { includeArchived?: boolean; officialOnly?: boolean } = {}) {
  const params = new URLSearchParams()
  if (options.includeArchived) params.set("include_archived", "true")
  if (options.officialOnly) params.set("official_only", "true")
  const query = params.toString()
  return apiRequest<ScenarioListResponse>(`/api/scenarios${query ? `?${query}` : ""}`)
}

export function createScenario(payload: ScenarioWritePayload) {
  return apiRequest<ApiScenario>("/api/scenarios", {
    method: "POST",
    body: payload,
  })
}

export function updateScenario(scenarioId: number, payload: ScenarioWritePayload) {
  return apiRequest<ApiScenario>(`/api/scenarios/${scenarioId}`, {
    method: "PUT",
    body: payload,
  })
}

export function archiveScenario(scenarioId: number) {
  return apiRequest<ApiScenario>(`/api/scenarios/${scenarioId}/archive`, { method: "POST" })
}

export function restoreScenario(scenarioId: number) {
  return apiRequest<ApiScenario>(`/api/scenarios/${scenarioId}/restore`, { method: "POST" })
}

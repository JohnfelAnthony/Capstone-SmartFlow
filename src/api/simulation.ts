import type { RenderPedestrian, RenderVehicle } from "@/simulation/frame-types"
import { apiRequest } from "@/api/client"

export type SimulationStatePayload = {
  status: string
  selected_scenario_id: number | null
  selected_scenario_name: string | null
  duration_seconds: number
  seed: number
  control_mode: string
  state: {
    time?: number
    step_length?: number
    status?: string
    phase?: string
    phase_remaining?: number
    cycle_count?: number
    vehicle_count?: number
    pedestrian_count?: number
    queues?: Record<string, number>
    metrics?: Record<string, number>
    events?: Array<Record<string, unknown>>
    scenario?: Record<string, unknown>
    dashboard?: Record<string, unknown>
    playback?: {
      frame_index?: number
      frame_count?: number
      progress_percent?: number
    }
    vehicles?: RenderVehicle[]
    pedestrians?: RenderPedestrian[]
    visual?: {
      constraint_marker?: {
        active?: boolean
        x?: number
        y?: number
      }
    }
    traffic_lights?: Record<string, { state: string; phase: string }>
    charts?: Record<string, unknown>
    flow?: {
      state?: string
      status_label?: string
      status_detail?: string
      live_indicator_label?: string
      controls?: Record<string, boolean>
    }
  }
}

export type SimulationActionResponse = {
  ok: boolean
  message: string
  simulation: SimulationStatePayload
}

export type SimulationConfigurePayload = {
  scenario_id?: number
  intersection_id?: string
  traffic_density?: string
  pedestrian_density?: string
  emergency_mode?: string
  road_constraint?: string
  duration_seconds?: number
  seed?: number
  control_mode?: string
}

export type SimulationStartPayload = {
  scenario_id?: number
  duration_seconds?: number
  seed?: number
  control_mode?: string
}

export type SimulationRunRecord = {
  id: number
  scenario_id: number | null
  scenario_name: string | null
  user_id: number | null
  user_name: string | null
  run_mode: string
  control_mode: string
  status: string
  start_time: string | null
  end_time: string | null
  duration_seconds: number
  seed: number | null
  notes: string | null
  timeline_path: string | null
  is_favorite: boolean
  metrics: Record<string, unknown> | null
}

export type SimulationRunListResponse = {
  runs: SimulationRunRecord[]
}

export type TimelineGeneratePayload = {
  scenario_id: number
  duration_seconds?: number
  seed?: number
  control_mode?: string
}

export type TimelineGenerateResponse = {
  message: string
  run: SimulationRunRecord
}

export function getSimulationState() {
  return apiRequest<SimulationStatePayload>("/api/simulation/state")
}

export function listSimulationRuns(params: {
  runMode?: string
  status?: string
  scenarioId?: number
  limit?: number
} = {}) {
  const query = new URLSearchParams()
  if (params.runMode) query.set("run_mode", params.runMode)
  if (params.status) query.set("status", params.status)
  if (params.scenarioId) query.set("scenario_id", String(params.scenarioId))
  if (params.limit) query.set("limit", String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ""
  return apiRequest<SimulationRunListResponse>(`/api/simulation/runs${suffix}`)
}

export function configureSimulation(payload: SimulationConfigurePayload) {
  return apiRequest<SimulationActionResponse>("/api/simulation/configure", {
    method: "POST",
    body: payload,
  })
}

export function startSimulation(payload: SimulationStartPayload = {}) {
  return apiRequest<SimulationActionResponse>("/api/simulation/start", {
    method: "POST",
    body: payload,
  })
}

export function pauseSimulation() {
  return apiRequest<SimulationActionResponse>("/api/simulation/pause", { method: "POST" })
}

export function resumeSimulation() {
  return apiRequest<SimulationActionResponse>("/api/simulation/resume", { method: "POST" })
}

export function stopSimulation() {
  return apiRequest<SimulationActionResponse>("/api/simulation/stop", { method: "POST" })
}

export function resetSimulation() {
  return apiRequest<SimulationActionResponse>("/api/simulation/reset", { method: "POST" })
}

export function stepSimulation(numTicks = 10) {
  return apiRequest<SimulationActionResponse>("/api/simulation/step", {
    method: "POST",
    body: { num_ticks: numTicks },
  })
}

export function generateTimeline(payload: TimelineGeneratePayload) {
  return apiRequest<TimelineGenerateResponse>("/api/simulation/timelines", {
    method: "POST",
    body: payload,
  })
}

export function loadPlayback(runId: number) {
  return apiRequest<SimulationActionResponse>("/api/simulation/playback/load", {
    method: "POST",
    body: { run_id: runId },
  })
}

export function startPlayback() {
  return apiRequest<SimulationActionResponse>("/api/simulation/playback/start", { method: "POST" })
}

export function seekPlayback(frameIndex: number) {
  return apiRequest<SimulationActionResponse>("/api/simulation/playback/seek", {
    method: "POST",
    body: { frame_index: frameIndex },
  })
}

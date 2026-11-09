import { apiDownload, apiRequest } from "@/api/client"
import type { SimulationRunRecord } from "@/api/simulation"
import type { VisualNetwork } from "@/api/visual-network"
import type { RenderFrame } from "@/simulation/frame-types"

export type CompareTimelineMeta = {
  intersection_id: string | null
  requested_duration_seconds: number
  actual_duration_seconds: number
  step_length_seconds: number
  frame_count: number
}

export type CompareRunOption = {
  run: SimulationRunRecord
  label: string
  timeline: CompareTimelineMeta
  compatibility_key: string
  provenance: {
    engine_version?: string | null
    network_sha256?: string | null
    demand_sha256?: string | null
    demand_source?: string | null
    demand_description?: string | null
    model_id?: number | null
    model_sha256?: string | null
  }
}

export type CompareRunListResponse = {
  runs: CompareRunOption[]
}

export type CompareTimelineFrame = {
  index: number
  time: number
  phase: string
  phase_remaining: number
  queues: Record<string, number>
  vehicle_count: number
  pedestrian_count: number
  avg_wait: number
  avg_queue: number
  max_queue: number
  throughput: number
  avg_ped_delay: number
  interpreted_metrics?: Record<string, number | null>
}

export type CompareRunBundle = {
  option: CompareRunOption
  frames: CompareTimelineFrame[]
  metrics: Record<string, unknown>
}

export type ComparePairResponse = {
  left: CompareRunBundle
  right: CompareRunBundle
  frame_count: number
  playback_times: number[]
  geometry: VisualNetwork | null
  opening_frames?: ComparePairFramesResponse | null
  comparison_type: "signal" | "routing" | "repeat"
  warnings: string[]
}

export function listCompareRuns(limit = 500) {
  return apiRequest<CompareRunListResponse>(`/api/compare/runs?limit=${limit}`)
}

export function listCompatibleCompareRuns(leftRunId: number) {
  return apiRequest<CompareRunListResponse>(`/api/compare/compatible-runs?left_run_id=${leftRunId}`)
}

export function getComparePair(leftRunId: number, rightRunId: number, signal?: AbortSignal) {
  return apiRequest<ComparePairResponse>(
    `/api/compare/pair?left_run_id=${leftRunId}&right_run_id=${rightRunId}&interactive=true`, { signal },
  )
}

export type CompareRenderFrame = RenderFrame & { queues?: Record<string, number> }

export type ComparePairFramesResponse = {
  times: number[]
  left: CompareRenderFrame[]
  right: CompareRenderFrame[]
  duration: number
}

export function getComparePairFrames(leftRunId: number, rightRunId: number, start: number, end: number, signal?: AbortSignal) {
  return apiRequest<ComparePairFramesResponse>(
    `/api/compare/pair/frames?left_run_id=${leftRunId}&right_run_id=${rightRunId}&start=${start}&end=${end}`, { signal },
  )
}

export type ComparePairHistory = { left: CompareTimelineFrame[]; right: CompareTimelineFrame[] }

export function getCompareHistory(leftRunId: number, rightRunId: number, signal?: AbortSignal) {
  return apiRequest<ComparePairHistory>(
    `/api/compare/pair/history?left_run_id=${leftRunId}&right_run_id=${rightRunId}`, { signal },
  )
}

export type SignalEvidence = {
  junction_id: string | null
  start: number; end: number; step_seconds: number; unavailable_seconds: number
  settings: Record<string, unknown>
  segments: Array<{ start: number; end: number; phase: string; stage: string }>
  phases: Array<{ phase: string; total_seconds: number; complete_count: number; mean_seconds: number | null; min_seconds: number | null; max_seconds: number | null }>
}
export type CompareSignals = { start: number; end: number; left: SignalEvidence; right: SignalEvidence }

export function getCompareSignals(left: number, right: number, signal?: AbortSignal) {
  return apiRequest<CompareSignals>(`/api/compare/pair/signals?left_run_id=${left}&right_run_id=${right}`, { signal })
}

export function getCompareReport(left: number, right: number) {
  return apiDownload(`/api/compare/pair/report?left_run_id=${left}&right_run_id=${right}`)
}

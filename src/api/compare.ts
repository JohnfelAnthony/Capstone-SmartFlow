import { apiRequest } from "@/api/client"
import type { SimulationRunRecord } from "@/api/simulation"

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
  warnings: string[]
}

export function listCompareRuns(limit = 500) {
  return apiRequest<CompareRunListResponse>(`/api/compare/runs?limit=${limit}`)
}

export function listCompatibleCompareRuns(leftRunId: number) {
  return apiRequest<CompareRunListResponse>(`/api/compare/compatible-runs?left_run_id=${leftRunId}`)
}

export function getComparePair(leftRunId: number, rightRunId: number) {
  return apiRequest<ComparePairResponse>(
    `/api/compare/pair?left_run_id=${leftRunId}&right_run_id=${rightRunId}`,
  )
}

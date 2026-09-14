import { API_BASE_URL, ApiError, apiRequest } from "@/api/client"
import type { CompareTimelineFrame, CompareTimelineMeta } from "@/api/compare"
import type { SimulationRunListResponse, SimulationRunRecord } from "@/api/simulation"

export type RunFilters = {
  scenarioId?: number
  runMode?: string
  controlMode?: string
  status?: string
  limit?: number
}

export function listRuns(filters: RunFilters = {}) {
  const params = new URLSearchParams()
  if (filters.scenarioId) params.set("scenario_id", String(filters.scenarioId))
  if (filters.runMode) params.set("run_mode", filters.runMode)
  if (filters.controlMode) params.set("control_mode", filters.controlMode)
  if (filters.status) params.set("status", filters.status)
  if (filters.limit) params.set("limit", String(filters.limit))
  const query = params.toString()
  return apiRequest<SimulationRunListResponse>(`/api/runs${query ? `?${query}` : ""}`)
}

export function getRun(runId: number) {
  return apiRequest<SimulationRunRecord>(`/api/runs/${runId}`)
}

export function getRunMetrics(runId: number) {
  return apiRequest<Record<string, unknown>>(`/api/runs/${runId}/metrics`)
}

export type RunTimelineResponse = {
  run: SimulationRunRecord
  timeline: CompareTimelineMeta
  frames: CompareTimelineFrame[]
  manifest: Record<string, unknown>
}

export function getRunTimeline(runId: number) {
  return apiRequest<RunTimelineResponse>(`/api/runs/${runId}/timeline`)
}

export function favoriteRun(runId: number, isFavorite: boolean) {
  return apiRequest<SimulationRunRecord>(`/api/runs/${runId}/favorite`, {
    method: "POST",
    body: { is_favorite: isFavorite },
  })
}

export function deleteRun(runId: number) {
  return apiRequest<{ message: string }>(`/api/runs/${runId}`, {
    method: "DELETE",
  })
}

async function downloadReport(path: string, filename: string, body: unknown) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let message = `Report export failed with status ${response.status}.`
    try {
      const payload = await response.json()
      if (typeof payload.detail === "string") {
        message = payload.detail
      }
    } catch {
      // Keep the generic message when the server did not send JSON.
    }
    throw new ApiError(response.status, message)
  }

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

export function exportRuns(runIds: number[], format: "csv" | "json") {
  return downloadReport("/api/reports/export", `smartflow-runs.${format}`, {
    run_ids: runIds,
    format,
  })
}

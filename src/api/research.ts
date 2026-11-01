import { apiRequest, API_BASE_URL } from "@/api/client"
import type { SimulationRunRecord } from "@/api/simulation"

export type MetricDefinition = { key: string; label: string; unit: string; definition: string }
export type Measurement = { metric: string; location: string; definition: string; unit: string; observed: number; tolerance: number; tolerance_mode: "absolute" | "percent"; simulated: number | null; simulation_method: string }
export type FitDraft = { name: string; site_id: string; purpose: "calibration" | "validation"; source_kind: "observed" | "synthetic"; source_reference: string; source_sha256: string; collection_start: string; collection_end: string; run_id: number; calibration_id: number | null; measurement_start: number; measurement_seconds: number; definitions_confirmed: boolean; measurements: Measurement[]; parameter_changes: string; notes: string }
export type Comparison = Measurement & { simulated: number; difference: number; absolute_error: number; percent_error: number | null; within_tolerance: boolean }
export type FitRecord = FitDraft & { id: number; created_at: string; created_by: number | null; comparisons: Comparison[]; within_tolerance: boolean; assessment: string; snapshot: { run_id: number; scenario_name: string | null; seed: number | null; controller: string; experiment: Record<string, unknown>; metrics: Record<string, unknown> } }
export function listFitRecords() { return apiRequest<{ records: FitRecord[]; metrics: MetricDefinition[] }>("/api/calibration") }
export function saveFitRecord(draft: FitDraft) { return apiRequest<FitRecord>("/api/calibration", { method: "POST", body: draft }) }
export async function downloadFitRecord(id: number, format: "json" | "csv") {
  // Check authorization before navigating to the authenticated attachment URL.
  await apiRequest<FitRecord>(`/api/calibration/${id}/export?format=json`)
  const link = document.createElement("a")
  link.href = `${API_BASE_URL}/api/calibration/${id}/export?format=${format}`
  link.download = `smartflow-fit-${id}.${format}`
  document.body.appendChild(link); link.click(); link.remove()
}
export function rawRunMetrics(run: SimulationRunRecord): Record<string, unknown> {
  const raw = run.metrics?.raw_metrics
  return raw && typeof raw === "object" ? raw as Record<string, unknown> : {}
}

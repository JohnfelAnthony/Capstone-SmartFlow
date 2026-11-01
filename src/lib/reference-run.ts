import type { SimulationRunRecord } from "@/api/simulation"
import { savedExperiment } from "@/lib/metrics"

export type SavedExperiment = Record<string, unknown>

const IDENTITY_KEYS = ["engine_version", "network_sha256", "seed", "duration_seconds", "measurement_start", "demand_sha256"] as const

function stable(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stable)
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([key, item]) => [key, stable(item)]))
  return value
}

/** The TypeScript twin of backend/main.py compare_key: the inputs two runs must share to be compared. Only the routing mode may differ. */
export function comparisonKey(experiment: SavedExperiment): string {
  const { routing_mode: _routingMode, ...settings } = (experiment.config && typeof experiment.config === "object" ? experiment.config : {}) as Record<string, unknown>
  void _routingMode
  const identity = Object.fromEntries(IDENTITY_KEYS.map((key) => [key, experiment[key] ?? null]))
  return JSON.stringify(stable({ ...identity, config_except_routing_mode: settings }))
}

export type ReferenceRun = { run: SimulationRunRecord; kind: "no-signal" | "fixed-time" }

/** The newest completed no-signal run with the same comparison key, else the newest matching fixed-time run. */
export function pickReferenceRun(runs: SimulationRunRecord[], current: { experiment: SavedExperiment; activeRunId: number | null }): ReferenceRun | null {
  if (!Object.keys(current.experiment).length) return null
  const key = comparisonKey(current.experiment)
  const matching = runs.filter((run) => run.id !== current.activeRunId && comparisonKey(savedExperiment(run.metrics)) === key)
  const newest = (kind: ReferenceRun["kind"]) => matching.filter((run) => run.control_mode === kind).sort((a, b) => b.id - a.id)[0]
  const noSignal = newest("no-signal")
  if (noSignal) return { run: noSignal, kind: "no-signal" }
  const fixed = newest("fixed-time")
  return fixed ? { run: fixed, kind: "fixed-time" } : null
}

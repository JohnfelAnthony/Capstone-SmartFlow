import catalog from "../../simulation/metric_definitions.json"

export const metricCatalog = catalog
export const metricDefinitions = catalog.metrics
export type MetricDefinition = (typeof metricDefinitions)[number]
const byKey = new Map(metricDefinitions.flatMap((item) =>
  [item.key, ...item.aliases].map((key) => [key, item] as const)))

export function metricDefinition(key: string) { return byKey.get(key) }
export function metricLabel(key: string) { return byKey.get(key)?.label ?? key }
export function metricDescription(key: string) { return byKey.get(key)?.definition ?? "Definition unavailable." }

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function rawMetrics(saved: Record<string, unknown>) {
  return saved.raw_metrics && typeof saved.raw_metrics === "object" ? saved.raw_metrics as Record<string, unknown> : saved
}

/** The experiment record (engine version, network fingerprint, seed…) saved with a run's metrics. */
export function savedExperiment(metrics: Record<string, unknown> | null | undefined): Record<string, unknown> {
  const raw = rawMetrics(metrics ?? {})
  return raw.experiment && typeof raw.experiment === "object" ? raw.experiment as Record<string, unknown> : {}
}

export function metricEngineVersion(metrics: Record<string, unknown> | null | undefined): unknown {
  return savedExperiment(metrics).engine_version
}

export function metricValue(metrics: Record<string, unknown> | null | undefined, key: string): number | null {
  const saved = metrics ?? {}
  const raw = rawMetrics(saved)
  const engineVersion = metricEngineVersion(saved)
  if (engineVersion !== undefined && engineVersion !== null && engineVersion !== metricCatalog.engine_version) return null
  const definition = byKey.get(key)
  const sources = raw === saved ? [saved] : [raw, saved]
  const lookup = (keys: string[]) => {
    for (const source of sources) {
      for (const name of keys) if (Object.hasOwn(source, name)) return finite(source[name])
    }
    return null
  }
  const value = lookup(definition ? [definition.key, ...definition.aliases] : [key])
  if (value === null || !definition) return value
  const counts = definition.population_keys.map((name) => lookup([name]))
  if (counts.length && (counts.some((count) => count === null) || counts.reduce<number>((sum, count) => sum + (count ?? 0), 0) <= 0)) return null
  if (definition.requires_ticks && (lookup(["step_count"]) ?? 0) <= 0) return null
  if (definition.requires_elapsed && (lookup(["measurement_seconds"]) ?? 0) <= 0) return null
  return value
}

export function formatMetric(value: number | null | undefined, digits = 1) {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

/** Percentage change against the baseline; undefined when either side is unavailable or the baseline is zero. */
export function percentChange(current: number | null, baseline: number | null) {
  if (current === null || baseline === null || baseline === 0) return undefined
  return (current - baseline) / Math.abs(baseline) * 100
}

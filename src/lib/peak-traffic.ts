import type { NativeScenarioConfig } from "@/api/native-scenario"

export const PEAK_SCHEMA = "smartflow_peak_counts"

export type TrafficSource = "peak" | "preset" | "imported"

/** Where a scenario's vehicles come from: the site's peak-traffic video count, a density preset, or counts imported before the importers were removed. */
export function trafficSource(config: NativeScenarioConfig): TrafficSource {
  if (config.demand_source?.datasets?.some((dataset) => dataset.schema === PEAK_SCHEMA)) return "peak"
  return (config.demand_windows?.length ?? 0) > 0 ? "imported" : "preset"
}

export function savedPeakSha(config: NativeScenarioConfig) {
  return config.demand_source?.datasets?.find((dataset) => dataset.schema === PEAK_SCHEMA)?.sha256
}

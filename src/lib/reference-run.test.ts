import { describe, expect, it } from "vitest"
import type { SimulationRunRecord } from "@/api/simulation"
import { comparisonKey, pickReferenceRun } from "./reference-run"

const config = { traffic_density: "low", routing_mode: "adaptive", signal_plans: {} }
const experiment = { engine_version: "native-7", network_sha256: "n1", seed: 1, duration_seconds: 300, measurement_start: 0, demand_sha256: "d1", config }
const current = { experiment, activeRunId: 9 as number | null }

function run(id: number, control_mode: string, changes: Record<string, unknown> = {}): SimulationRunRecord {
  return { id, scenario_id: 1, scenario_name: "S", user_id: null, user_name: null, run_mode: "pre-record", control_mode, status: "completed", start_time: null, end_time: null,
    duration_seconds: 300, seed: 1, rl_model_id: null, notes: null, timeline_path: null, is_favorite: false, metrics: { raw_metrics: { experiment: { ...experiment, ...changes } } } }
}
const fixed = (id: number, changes: Record<string, unknown> = {}) => run(id, "fixed-time", changes)
const noSignal = (id: number, changes: Record<string, unknown> = {}) => run(id, "no-signal", changes)

describe("comparisonKey", () => {
  it("is the same for any key order and ignores only the routing mode", () => {
    const reordered = { demand_sha256: "d1", config: { signal_plans: {}, routing_mode: "static", traffic_density: "low" }, measurement_start: 0, duration_seconds: 300, seed: 1, network_sha256: "n1", engine_version: "native-7" }
    expect(comparisonKey(reordered)).toBe(comparisonKey(experiment))
    expect(comparisonKey({ ...experiment, config: { ...config, traffic_density: "high" } })).not.toBe(comparisonKey(experiment))
  })
})

describe("pickReferenceRun", () => {
  it("prefers the matching no-signal run", () => expect(pickReferenceRun([fixed(5), noSignal(4)], current)?.kind).toBe("no-signal"))
  it("falls back to fixed-time", () => expect(pickReferenceRun([fixed(5)], current)?.run.id).toBe(5))
  it("takes the newest of its kind", () => expect(pickReferenceRun([noSignal(3), noSignal(7), fixed(8)], current)?.run.id).toBe(7))
  it("ignores another seed, network or engine, and the active run", () =>
    expect(pickReferenceRun([noSignal(4, { seed: 2 }), noSignal(6, { network_sha256: "other" }), noSignal(2, { engine_version: "native-6" }), noSignal(9)], current)).toBeNull())
  it("ignores a run made before the scenario was edited", () =>
    expect(pickReferenceRun([noSignal(4, { demand_sha256: "before-edit" }), fixed(3, { config: { ...config, traffic_density: "high" } })], current)).toBeNull())
  it("ignores a different measurement window or duration", () =>
    expect(pickReferenceRun([noSignal(4, { measurement_start: 60 }), noSignal(5, { duration_seconds: 600 })], current)).toBeNull())
  it("routing mode alone does not break the match", () =>
    expect(pickReferenceRun([noSignal(4, { config: { ...config, routing_mode: "static" } })], current)?.run.id).toBe(4))
  it("never offers an RL run as a reference", () => expect(pickReferenceRun([run(3, "ql:7")], current)).toBeNull())
  it("finds nothing without a saved experiment on the current run", () => expect(pickReferenceRun([fixed(5)], { experiment: {}, activeRunId: null })).toBeNull())
})

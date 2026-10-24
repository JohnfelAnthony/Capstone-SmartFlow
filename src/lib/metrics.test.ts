import { describe, expect, it } from "vitest"
import { formatMetric, metricCatalog, metricDefinition, metricValue, percentChange } from "./metrics"

describe("native metric interpretation", () => {
  it("distinguishes empty averages from zero measured outcomes", () => {
    const empty = { avg_wait: 0, total_vehicles_completed: 0, active_vehicle_count: 0, throughput: 0 }
    expect(metricValue(empty, "avg_wait")).toBeNull()
    expect(metricValue(empty, "throughput")).toBe(0)
    expect(metricValue({ throughput_per_hour: 0, measurement_seconds: 0 }, "throughput_per_hour")).toBeNull()
    expect(metricValue({ throughput_per_hour: 0, measurement_seconds: 2 }, "throughput_per_hour")).toBe(0)
    expect(metricValue({ ...empty, active_vehicle_count: 3 }, "avg_waiting_time")).toBe(0)
    expect(metricValue({}, "throughput")).toBeNull()
    expect(formatMetric(null)).toBe("—")
  })
  it("uses authoritative raw metrics and preserves unknown historical populations as unavailable", () => {
    expect(metricValue({ avg_waiting_time: 0 }, "avg_wait")).toBeNull()
    expect(metricValue({ avg_waiting_time: 99, raw_metrics: {
      avg_wait: 4, total_vehicles_completed: 2, active_vehicle_count: 1,
    } }, "avg_waiting_time")).toBe(4)
    expect(metricValue({ throughput: true }, "throughput")).toBeNull()
    expect(metricValue({ throughput: Number.NaN }, "throughput")).toBeNull()
    expect(metricValue({ throughput: 5, experiment: { engine_version: "historical-other-engine" } }, "throughput")).toBeNull()
  })
  it("requires sampled queue ticks and the appropriate average populations", () => {
    expect(metricValue({ avg_queue: 0, step_count: 0 }, "avg_queue")).toBeNull()
    expect(metricValue({ avg_queue: 0, step_count: 1 }, "avg_queue")).toBe(0)
    expect(metricValue({ avg_travel_time: 0, total_vehicles_completed: 0 }, "avg_travel_time")).toBeNull()
  })
  it("shares complete definitions, units and exclusions with the backend catalog", () => {
    expect(metricDefinition("avg_waiting_time")).toBe(metricDefinition("avg_wait"))
    expect(metricDefinition("avg_travel_time")?.definition).toContain("pre-window")
    expect(metricDefinition("requested_vehicles")?.definition).toContain("warmup")
    expect(metricCatalog.unsupported.emissions).toContain("Unavailable")
    for (const item of metricCatalog.metrics) {
      expect(item.label).toBeTruthy(); expect(item.unit).toBeTruthy()
      expect(item.population).toBeTruthy(); expect(item.zero).toBeTruthy()
    }
  })
})

describe("baseline percentage change", () => {
  it("compares against the baseline magnitude", () => {
    expect(percentChange(8, 10)).toBeCloseTo(-20)
    expect(percentChange(12, 10)).toBeCloseTo(20)
  })

  it("is undefined when either value is unavailable or the baseline is zero", () => {
    expect(percentChange(null, 10)).toBeUndefined()
    expect(percentChange(5, null)).toBeUndefined()
    expect(percentChange(5, 0)).toBeUndefined()
  })
})

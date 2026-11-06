import { describe, expect, it } from "vitest"

import { effectiveWarmupSeconds } from "@/api/native-scenario"

describe("effectiveWarmupSeconds", () => {
  it("uses the saved warm-up for steady traffic and the server's default for an old scenario", () => {
    expect(effectiveWarmupSeconds({ traffic_density: "medium", warmup_seconds: 90 }, 120)).toBe(90)
    expect(effectiveWarmupSeconds({ traffic_density: "Medium" }, 120)).toBe(120)
    expect(effectiveWarmupSeconds({ traffic_density: "none", demand_windows: [{}] }, 120)).toBe(120)
  })
  it("is none for scripted traffic, which a warm-up would play out unseen", () => {
    expect(effectiveWarmupSeconds({ traffic_density: "single" }, 120)).toBe(0)
    expect(effectiveWarmupSeconds({ traffic_density: "none" }, 120)).toBe(0)
    expect(effectiveWarmupSeconds({ traffic_density: "medium", trips: [{ time: 3 }] }, 120)).toBe(0)
  })
})

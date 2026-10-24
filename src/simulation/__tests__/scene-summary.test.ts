import { describe, expect, it } from "vitest"
import type { LaneMetrics } from "@/simulation/frame-types"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"
import { approachDirection, junctionShortLabel, laneDisplayLabel, longestQueuedApproach } from "@/simulation/scene-summary"
import { bentNetwork } from "./geometry-fixture"

const metric = (queue: number): LaneMetrics => ({ queue, vehicles: queue, mean_speed_mps: 0, density_vehicles_per_km: 0, exits: 0, closed: false, speed_factor: 1 })

describe("scene queue scope", () => {
  const geometry = normalizeSceneGeometry(bentNetwork)

  it("does not show another junction's longer queue beside a focused junction", () => {
    expect(longestQueuedApproach(geometry, { "lane-west": metric(0), "other-junction": metric(12) }, "J1"))
      .toEqual({ id: "lane-west", queue: 0 })
  })

  it("excludes outgoing lanes even if both endpoints are near the focused junction", () => {
    const outgoing = { ...geometry.lanes[0], id: "outgoing", junctionIds: ["J1"] }
    const network = { ...geometry, lanes: [...geometry.lanes, outgoing], laneById: new Map([...geometry.laneById, [outgoing.id, outgoing]]) }
    expect(longestQueuedApproach(network, { "lane-west": metric(2), outgoing: metric(18) }, "J1"))
      .toEqual({ id: "lane-west", queue: 2 })
  })

  it("allows explicitly network-wide summaries", () => {
    expect(longestQueuedApproach(geometry, { "lane-west": metric(0), remote: metric(12) }, null))
      .toEqual({ id: "remote", queue: 12 })
  })

  it("does not invent a zero for missing telemetry or an unknown junction", () => {
    expect(longestQueuedApproach(geometry, undefined, "J1")).toBeNull()
    expect(longestQueuedApproach(geometry, { "lane-west": metric(4) }, "unknown")).toBeNull()
  })

  it("uses deterministic ties without mutating telemetry", () => {
    const metrics = { z: metric(4), a: metric(4) }
    expect(longestQueuedApproach(geometry, metrics, null)).toEqual({ id: "a", queue: 4 })
    expect(Object.keys(metrics)).toEqual(["z", "a"])
  })

  it("keeps readable aliases separate from raw identifiers", () => {
    expect(junctionShortLabel(geometry, "J1")).toBe("J1")
    expect(laneDisplayLabel(geometry, "lane-west")).toBe("J1 approach 1")
    expect(laneDisplayLabel(geometry, "unknown-lane")).toBe("unknown-lane")
  })
})

describe("approach direction", () => {
  const geometry = normalizeSceneGeometry(bentNetwork)

  it("names the side traffic arrives from", () => {
    expect(approachDirection(geometry, "lane-west")).toBe("From west")
  })

  it("returns null for unknown lanes", () => {
    expect(approachDirection(geometry, "missing")).toBeNull()
  })
})

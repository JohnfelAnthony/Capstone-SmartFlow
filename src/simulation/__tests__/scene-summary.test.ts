import { describe, expect, it } from "vitest"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"
import { approachDirection, junctionShortLabel, junctionTagText, laneDisplayLabel, phaseService, signalArms } from "@/simulation/scene-summary"
import { bentNetwork, crossNetwork } from "./geometry-fixture"

describe("scene labels", () => {
  const geometry = normalizeSceneGeometry(bentNetwork)

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

describe("junction display helpers", () => {
  it("shortens backend junction labels for map tags", () => {
    expect(junctionTagText("J1: Arellano Street / Osmeña Street")).toBe("J1 · Arellano × Osmeña")
    expect(junctionTagText("Plain junction")).toBe("Plain junction")
  })

  it("maps engine phase names to their service", () => {
    expect(phaseService("SOUTH_GREEN")).toBe("south")
    expect(phaseService("NORTH_YELLOW")).toBe("north")
    expect(phaseService("PED_GREEN")).toBe("pedestrian")
    expect(phaseService("ALL_RED")).toBeNull()
    expect(phaseService(undefined)).toBeNull()
  })
})

describe("signalArms", () => {
  const geometry = normalizeSceneGeometry(crossNetwork())
  const lights = (state: Record<string, string>) => ({ traffic_lights: Object.fromEntries(Object.entries(state).map(([id, value]) => [id, { state: value }])) })

  it("places each approach on its real side with north up", () => {
    const arms = signalArms(geometry, "J", lights({}))
    const arm = (laneId: string) => arms.find(candidate => candidate.laneId === laneId)!
    expect(arms).toHaveLength(4)
    expect(arm("north-in").y).toBeLessThan(-.9)
    expect(arm("south-in").y).toBeGreaterThan(.9)
    expect(arm("east-in").x).toBeGreaterThan(.9)
    expect(arm("west-in").x).toBeLessThan(-.9)
  })

  it("lights only the lane the engine reports as served", () => {
    const arms = signalArms(geometry, "J", lights({ "north-in": "G", "south-in": "y", "east-in": "r", "west-in": "r" }))
    expect(Object.fromEntries(arms.map(arm => [arm.laneId, arm.color]))).toEqual({ "north-in": "green", "south-in": "yellow", "east-in": "red", "west-in": "red" })
  })

  it("has no arms for an unknown junction", () => {
    expect(signalArms(geometry, "missing", null)).toEqual([])
  })
})

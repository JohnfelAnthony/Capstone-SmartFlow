import { describe, expect, it } from "vitest"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"
import { approachDirection, junctionShortLabel, junctionTagText, laneDisplayLabel, phaseService } from "@/simulation/scene-summary"
import { bentNetwork } from "./geometry-fixture"

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

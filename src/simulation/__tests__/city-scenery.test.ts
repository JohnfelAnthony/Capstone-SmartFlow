import { describe, expect, it } from "vitest"
import { crossNetwork } from "./geometry-fixture"
import { cityScenery, pedestrianWalkways, sceneryClearance, STREET_EDGE, vergeLines } from "@/simulation/city-scenery"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"

describe("illustrative city scenery", () => {
  const geometry = normalizeSceneGeometry(crossNetwork(90))
  // Like the engine's path at a T-junction: it starts well inside the block west of the kerb.
  const walkways = pedestrianWalkways([{ shape: [{ x: -14, y: 6 }, { x: 9, y: 6 }] }, { shape: [{ x: 0, y: 0 }] }])
  const items = cityScenery(geometry, walkways), clearance = sceneryClearance(geometry, walkways)

  it("fills the blocks with buildings, open space and trees", () => {
    const kinds = new Set(items.map((item) => item.kind))
    expect(kinds.has("building")).toBe(true)
    expect(kinds.has("tree")).toBe(true)
  })
  it("draws only paths with a length as walkways", () => expect(walkways).toHaveLength(1))
  it("keeps every lot behind the sidewalk and verge of every road, junction and pedestrian walkway", () => {
    for (const item of items) if (item.kind !== "tree") for (const point of [...item.corners, item.center]) expect(clearance(point)).toBeGreaterThanOrEqual(STREET_EDGE.sidewalk + STREET_EDGE.verge)
  })
  it("never plants a tree on the pavement or the sidewalk", () => {
    for (const item of items) if (item.kind === "tree") expect(clearance(item.center)).toBeGreaterThanOrEqual(STREET_EDGE.sidewalk)
  })
  it("is stable for the same network", () => expect(cityScenery(geometry, walkways)).toEqual(items))
  it("runs one verge strip behind each kerb, none along the centre line", () => {
    const streetClearance = sceneryClearance(geometry, [])
    expect(vergeLines(geometry)).toHaveLength(geometry.lanes.length)
    // Ends at the junction mouth sit next to the rounded kerb, a few millimetres closer than the straight run.
    for (const line of vergeLines(geometry)) for (const point of line) {
      expect(streetClearance(point)).toBeLessThanOrEqual(STREET_EDGE.sidewalk + STREET_EDGE.verge / 2 + 1e-9)
      expect(streetClearance(point)).toBeGreaterThan(STREET_EDGE.sidewalk + STREET_EDGE.verge / 2 - .05)
    }
  })
})

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

describe("a surveyed site's own features", () => {
  const square = (x: number, y: number, half: number) => [{ x: x - half, y: y - half }, { x: x + half, y: y - half }, { x: x + half, y: y + half }, { x: x - half, y: y + half }]
  const strip = (x0: number, x1: number, y0: number, y1: number) => [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }]
  const network = crossNetwork(90)
  network.site_features = [{ id: "lot", kind: "plaza", shape: square(40, 40, 25) }, { id: "paint", kind: "marking", shape: square(-40, -40, 25) }]
  network.islands = [
    { id: "narrow", shape: strip(20, 60, 4, 5.5), planted: true },
    { id: "wide", shape: strip(-60, -20, 8, 12), planted: true },
    { id: "bare", shape: strip(-60, -20, -12, -8), planted: false },
  ]
  const geometry = normalizeSceneGeometry(network), items = cityScenery(geometry, [])
  const inside = (point: { x: number; y: number }, x0: number, x1: number, y0: number, y1: number) => point.x >= x0 && point.x <= x1 && point.y >= y0 && point.y <= y1

  it("keeps generated lots and trees off paved site features", () => {
    for (const item of items) {
      if (item.kind === "tree") { if (!inside(item.center, 20, 60, 4, 5.5)) expect(inside(item.center, 15, 65, 15, 65)).toBe(false) }
      else for (const point of item.corners) expect(inside(point, 15, 65, 15, 65)).toBe(false)
    }
  })
  it("does not reserve room for paint", () => {
    expect(sceneryClearance(geometry, [])({ x: -40, y: -40 })).toBeGreaterThan(0)
  })
  it("plants palms along planted islands only, closer together on the wide ones", () => {
    const palms = (x0: number, x1: number, y0: number, y1: number) => items.filter((item) => item.kind === "tree" && inside(item.center, x0, x1, y0, y1))
    expect(palms(20, 60, 4, 5.5).length).toBeGreaterThanOrEqual(4)
    expect(palms(-60, -20, 8, 12).length).toBeGreaterThan(palms(20, 60, 4, 5.5).length)
    expect(palms(-60, -20, -12, -8)).toHaveLength(0)
  })
})

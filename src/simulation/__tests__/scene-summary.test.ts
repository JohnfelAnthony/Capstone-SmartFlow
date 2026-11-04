import { describe, expect, it } from "vitest"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"
import { approachDirection, junctionShortLabel, junctionTagText, laneDisplayLabel, phaseService, signalMovements, TURN_ARROW_EXTENSION_M } from "@/simulation/scene-summary"
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

describe("signalMovements", () => {
  const connector = (id: string, shape: { x: number; y: number }[]) => ({ index: 0, function: "internal", toward_intersection: true, away_from_intersection: true, shape,
    lanes: [{ id, index: 0, width: 3.3, allow: "passenger", disallow: "", source_length: 18, clip_start_position: 0, clip_end_position: 18, shape }] })
  const northStopLine = { x: -1.65, y: 9 }
  const geometry = normalizeSceneGeometry({ ...crossNetwork(), internal_lanes: [
    connector("north-in->west-out", [northStopLine, { x: -9, y: 1.65 }]),
    connector("north-in->south-out", [northStopLine, { x: -1.65, y: -9 }]),
    connector("north-in->east-out", [northStopLine, { x: 9, y: -1.65 }]),
    connector("east-in->west-out", [{ x: 9, y: 1.65 }, { x: -9, y: 1.65 }]),
  ] })
  const lights = (state: Record<string, string>) => ({ traffic_lights: Object.fromEntries(Object.entries(state).map(([id, value]) => [id, { state: value }])) })
  const byLane = (frame: Parameters<typeof signalMovements>[2]) => new Map(signalMovements(geometry, "J", frame).map(movement => [movement.laneId, movement]))

  it("gives an approach only the turns it can make", () => {
    const movements = byLane(null)
    expect(movements.size).toBe(4)
    expect(movements.get("north-in")?.turns).toHaveLength(3)
    expect(movements.get("east-in")?.turns).toHaveLength(1)
    expect(movements.get("south-in")?.turns).toHaveLength(0)
  })

  it("runs each arrow from behind the stop line to past the exit's start", () => {
    const [leftTurn, straight, rightTurn] = byLane(null).get("north-in")!.turns
    for (const arrow of [leftTurn, straight, rightTurn]) expect(arrow[0].y).toBeCloseTo(9 + TURN_ARROW_EXTENSION_M)
    expect(leftTurn.at(-1)).toEqual({ x: 9 + TURN_ARROW_EXTENSION_M, y: -1.65 })
    expect(straight.at(-1)).toEqual({ x: -1.65, y: -9 - TURN_ARROW_EXTENSION_M })
    expect(rightTurn.at(-1)).toEqual({ x: -9 - TURN_ARROW_EXTENSION_M, y: 1.65 })
  })

  it("starts arrows apart with the left turn on the driver's left, so they never bundle", () => {
    const [leftTurn, straight, rightTurn] = byLane(null).get("north-in")!.turns
    // Heading south, the driver's left is east (+x); the middle arrow stays on the lane's centre.
    expect(straight[0].x).toBeCloseTo(-1.65)
    expect(leftTurn[0].x).toBeCloseTo(-1.65 + 1.4)
    expect(rightTurn[0].x).toBeCloseTo(-1.65 - 1.4)
    expect(byLane(null).get("east-in")!.turns[0][0].y).toBeCloseTo(1.65)
  })

  it("lights only the lane the engine reports as served", () => {
    const movements = byLane(lights({ "north-in": "G", "south-in": "y", "east-in": "r", "west-in": "r" }))
    expect(movements.get("north-in")?.color).toBe("green")
    expect(movements.get("south-in")?.color).toBe("yellow")
    expect(movements.get("east-in")?.color).toBe("red")
  })

  it("keeps every approach unlit without a frame, and has none for an unknown junction", () => {
    expect([...byLane(null).values()].every(movement => movement.color === "off")).toBe(true)
    expect(signalMovements(geometry, "missing", null)).toEqual([])
  })
})

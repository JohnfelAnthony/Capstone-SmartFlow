import { describe, expect, it } from "vitest"
import type { VisualNetwork } from "@/api/visual-network"
import { bentNetwork, crossNetwork } from "./geometry-fixture"
import {
  boundsForJunction, centeredVehicleFootprint, dashedPieces, forwardAtHeading, headingToThreeYaw, laneDividers,
  normalizeSceneGeometry, normalizeVehicleClass, pickSceneEntity, pointToThree, signalAppearance, signalHeadPlacement, vehicleDimensions, walkSignalState,
} from "@/simulation/scene-geometry"

describe("canonical native display geometry", () => {
  it("preserves both bent-road endpoints despite the connected-network flags", () => {
    const before = JSON.stringify(bentNetwork)
    const geometry = normalizeSceneGeometry(bentNetwork)
    const lane = geometry.lanes[0]
    expect(lane.centerline).toEqual(bentNetwork.roads[0].lanes[0].shape)
    expect(lane.centerline[0]).toEqual({ x: -150, y: 0 })
    expect(lane.centerline.at(-1)).toEqual({ x: -12, y: 4 })
    expect(JSON.stringify(bentNetwork)).toBe(before)
    expect(geometry.laneById.get("lane-west")).toBe(lane)
    expect(geometry.signalGroups[0].junctionId).toBe("J1")
  })

  it("makes centered width-preserving road ends rather than extending native centerlines", () => {
    const lane = normalizeSceneGeometry(bentNetwork).lanes[0]
    const polygon = lane.polygon
    expect(polygon[0].x).toBe(-150)
    expect(polygon.at(-1)?.x).toBe(-150)
    expect(Math.abs(polygon[0].y - polygon.at(-1)!.y)).toBeCloseTo(3.3)
    const endLeft = polygon[2], endRight = polygon[3]
    expect((endLeft.x + endRight.x) / 2).toBeCloseTo(-12)
    expect((endLeft.y + endRight.y) / 2).toBeCloseTo(4)
  })

  it("fits the selected junction and clipped immediate approach with twenty-percent padding", () => {
    const geometry = normalizeSceneGeometry(bentNetwork)
    const unpadded = boundsForJunction(geometry, "J1", 0)
    const padded = boundsForJunction(geometry, "J1")
    expect(padded.max_x - padded.min_x).toBeCloseTo((unpadded.max_x - unpadded.min_x) * 1.2)
    expect(padded.min_x).toBeGreaterThan(-100)
    expect(padded.max_x).toBeGreaterThan(12)
    expect(boundsForJunction(geometry, "missing")).toEqual(geometry.bounds)
  })

  it("keeps native XY and Three XZ coordinates consistent", () => {
    expect(pointToThree({ x: 10, y: 20 }, 0.3)).toEqual({ x: 10, y: 0.3, z: -20 })
  })
})

describe("centered vehicles and native clockwise-from-north heading", () => {
  it.each([["car", 4.5, 1.8], ["motorcycle", 2, .8], ["tricycle", 3, 1.4], ["bus", 10, 2.5], ["truck", 8, 2.5]])(
    "retains native %s class dimensions", (visual_type, length, width) => {
      expect(normalizeVehicleClass(String(visual_type))).toBe(visual_type)
      expect(vehicleDimensions({ visual_type: String(visual_type) })).toEqual({ length, width })
      expect(vehicleDimensions({ visual_type: String(visual_type), length: 6.3, width: 2.3 })).toEqual({ length: 6.3, width: 2.3 })
    })
  it.each([[0, 0, 1], [90, 1, 0], [180, 0, -1], [270, -1, 0], [45, Math.SQRT1_2, Math.SQRT1_2]])(
    "maps heading %s to the same native and Three forward direction", (angle, dx, dy) => {
      const forward = forwardAtHeading(angle)
      expect(forward.x).toBeCloseTo(dx)
      expect(forward.y).toBeCloseTo(dy)
      const yaw = headingToThreeYaw(angle)
      expect(Math.cos(yaw)).toBeCloseTo(dx)
      expect(-Math.sin(yaw)).toBeCloseTo(-dy)
    })

  it.each([0, 45, 90, 180, 270])("centers the vehicle footprint at heading %s", (angle) => {
    const footprint = centeredVehicleFootprint({ x: 17, y: -9, angle, length: 10, width: 2.5 })
    expect(footprint.reduce((sum, point) => sum + point.x, 0) / 4).toBeCloseTo(17)
    expect(footprint.reduce((sum, point) => sum + point.y, 0) / 4).toBeCloseTo(-9)
    expect(Math.hypot(footprint[0].x - footprint[1].x, footprint[0].y - footprint[1].y)).toBeCloseTo(10)
    expect(Math.hypot(footprint[1].x - footprint[2].x, footprint[1].y - footprint[2].y)).toBeCloseTo(2.5)
  })
})

describe("signal truth", () => {
  it.each([["G", "green"], ["y", "yellow"], ["r", "red"], ["o", "off"], ["O", "off"]])(
    "keeps %s distinct as %s", (state, color) => {
      expect(signalAppearance(bentNetwork.signal_groups[0], { traffic_lights: { "lane-west": { state } } }).color).toBe(color)
    })

  it("does not invent red or a lit lamp when signal telemetry is unavailable", () => {
    const appearance = signalAppearance(bentNetwork.signal_groups[0], null)
    expect(appearance.color).toBe("off")
    expect(appearance.available).toBe(false)
    expect(appearance.lit).toBe(false)
  })

  it("honors off link states and multiple real links without treating a queued request as a green", () => {
    const group = { ...bentNetwork.signal_groups[0], link_indices: [0, 1] }
    expect(signalAppearance(group, { traffic_lights: { "lane-west": { state: "oo" } } }).lit).toBe(false)
    expect(signalAppearance(group, { traffic_lights: { "lane-west": { state: "ry" } } }).color).toBe("yellow")
    expect(signalAppearance(group, { traffic_lights: { "lane-west": { state: "rg" } } }).color).toBe("green")
  })
})

describe("native-coordinate analytical selection", () => {
  const geometry = normalizeSceneGeometry(bentNetwork)
  it("selects a stable vehicle ID at its center and through a diagonal heading", () => {
    const frame = { vehicles: [{ id: "v-diagonal", x: -30, y: 3, angle: 45, length: 4.5, width: 1.8 }], pedestrians: [] }
    expect(pickSceneEntity(geometry, frame, { x: -30, y: 3 })).toEqual({ kind: "vehicle", id: "v-diagonal" })
  })
  it("selects a modeled person before the pavement beneath them", () => {
    expect(pickSceneEntity(geometry, { vehicles: [], pedestrians: [{ id: "p1", x: 0, y: 0 }] }, { x: 0, y: 0 })).toEqual({ kind: "pedestrian", id: "p1" })
  })
  it("picks the junction polygon, directed lane, and empty background correctly", () => {
    expect(pickSceneEntity(geometry, null, { x: 0, y: 0 })).toEqual({ kind: "junction", id: "J1" })
    expect(pickSceneEntity(geometry, null, { x: -100, y: 0 })).toEqual({ kind: "lane", id: "lane-west" })
    expect(pickSceneEntity(geometry, null, { x: 80, y: 80 })).toBe(null)
  })
})

describe("road width markings", () => {
  const line = [{ x: 0, y: 0 }, { x: 10, y: 0 }]
  it("puts one divider on the centre line of a two-lane carriageway", () => {
    expect(laneDividers(line, 6.6, 2)).toEqual([[{ x: 0, y: 0 }, { x: 10, y: 0 }]])
  })
  it("puts two dividers 1.65 m either side of a 9.9 m three-lane centre line", () => {
    const ys = laneDividers(line, 9.9, 3).map((divider) => Math.abs(divider[0].y))
    expect(ys.map((y) => y.toFixed(2))).toEqual(["1.65", "1.65"])
  })
  it("draws no dividers for a single lane", () => expect(laneDividers(line, 3.3, 1)).toEqual([]))
  it("cuts a polyline into dashes", () => {
    expect(dashedPieces([{ x: 0, y: 0 }, { x: 12, y: 0 }], 3, 3)).toEqual([[{ x: 0, y: 0 }, { x: 3, y: 0 }], [{ x: 6, y: 0 }, { x: 9, y: 0 }]])
  })
  it("reads the lane count, defaulting to one, and precomputes road dividers", () => {
    for (const [count, expected] of [[2, 2], [undefined, 1], [0, 1], [1.5, 1]] as const) {
      const network: VisualNetwork = structuredClone(bentNetwork)
      network.roads[0].lanes[0].width = 6.6
      network.roads[0].lanes[0].lane_count = count
      const lane = normalizeSceneGeometry(network).laneById.get("lane-west")!
      expect([lane.laneCount, lane.dividers.length]).toEqual([expected, expected - 1])
    }
  })
  it("keeps a dash whole across a polyline corner", () => {
    expect(dashedPieces([{ x: 0, y: 0 }, { x: 2, y: 0 }, { x: 2, y: 2 }], 3, 3)).toEqual([[{ x: 0, y: 0 }, { x: 2, y: 0 }, { x: 2, y: 1 }]])
  })
})

describe("street illustration geometry", () => {
  const geometry = normalizeSceneGeometry(crossNetwork())
  const junction = geometry.junctions[0]
  it("draws a centre line where opposing carriageways meet and none on a one-way kerb", () => {
    expect(geometry.lanes.every((lane) => lane.centreLine !== null)).toBe(true)
    expect(geometry.laneById.get("north-in")!.centreLine!.every((point) => Math.abs(point.x) < 1e-9)).toBe(true)
    expect(normalizeSceneGeometry(bentNetwork).lanes[0].centreLine).toBeNull()
  })
  it("rounds each kerb corner between approaches toward the junction centre", () => {
    const corner = junction.kerb.filter((point) => point.x > 3.31 && point.y > 3.31)
    expect(corner.length).toBe(7)
    for (const point of corner) {
      expect(point.x + point.y).toBeLessThan(12.3)
      expect(Math.hypot(point.x - 9, point.y - 9)).toBeGreaterThan(5.6)
    }
    expect(junction.kerb.some((point) => Math.hypot(point.x - 3.3, point.y - 9) < 1e-9)).toBe(true)
  })
  it("paints a zebra on every carriageway end, inside the junction and before the conflict area", () => {
    expect(junction.crosswalks.map((crosswalk) => crosswalk.laneId).sort()).toEqual(geometry.lanes.map((lane) => lane.id).sort())
    const north = junction.crosswalks.filter((crosswalk) => crosswalk.laneId.startsWith("north")).flatMap((crosswalk) => crosswalk.stripes)
    expect(north).toHaveLength(6)
    for (const point of north.flat()) {
      expect(point.y).toBeGreaterThanOrEqual(9 - 3.6 - 1e-9)
      expect(point.y).toBeLessThanOrEqual(9 - 0.6 + 1e-9)
      expect(Math.abs(point.x)).toBeLessThanOrEqual(3.3)
    }
    expect(north.map((stripe) => Math.min(...stripe.map((point) => point.x))).sort((a, b) => a - b).map((x) => x.toFixed(2))).toEqual(["-2.75", "-1.75", "-0.75", "0.25", "1.25", "2.25"])
  })
  it("stands walk signals on the kerb ends of each crossing", () => {
    const north = junction.crosswalks.filter((crosswalk) => crosswalk.laneId.startsWith("north")).flatMap((crosswalk) => crosswalk.walkSignals)
    expect(north.map((point) => [point.x.toFixed(2), point.y.toFixed(2)]).sort()).toEqual([["-4.40", "6.90"], ["4.40", "6.90"]])
  })
  it("hangs each approach's head just past its stop line, facing the oncoming vehicles", () => {
    const group = geometry.signalGroups.find((candidate) => candidate.lane_id === "north-in")!
    const placement = signalHeadPlacement(group)
    expect(placement.head.x).toBeCloseTo(-1.65); expect(placement.head.y).toBeCloseTo(8.1)
    expect(placement.facing.x).toBeCloseTo(0); expect(placement.facing.y).toBeCloseTo(1)
    expect(placement.pole.x).toBeCloseTo(-4.4); expect(placement.pole.y).toBeCloseTo(9.3)
  })
  it("reads the junction's exclusive pedestrian phase for every crossing", () => {
    const frame = (phase: string, mode = "fixed_time") => ({ junction_controls: { J: { mode, phase } } })
    expect(walkSignalState("J", frame("PED_GREEN"))).toBe("walk")
    expect(walkSignalState("J", frame("PED_YELLOW"))).toBe("clearance")
    expect(walkSignalState("J", frame("NORTH_GREEN"))).toBe("dont_walk")
    expect(walkSignalState("J", frame("ALL_RED", "all_way_stop"))).toBe("off")
    expect(walkSignalState("J", null)).toBeNull()
  })
})

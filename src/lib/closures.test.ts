import { describe, expect, it } from "vitest"
import { closureLines, closureProblem, describeRule, groupRoads, readClosures, ruleProblem, writeClosures } from "@/lib/closures"

describe("reading closures from a scenario's settings", () => {
  it("reads whole-run closures and timed ones with a start and an end", () => {
    const { rules, locked } = readClosures({ closed_lanes: ["a"], events: [
      { time: 100, lane_id: "b", closed: true }, { time: 300, lane_id: "b", closed: false },
      { time: 50, lane_id: "c", closed: true }, { time: 20, lane_id: "d", closed: true }, { time: 40, lane_id: "d", closed: false }, { time: 60, lane_id: "d", closed: true },
    ] })
    expect(rules).toEqual({ a: { start: 0, end: null }, b: { start: 100, end: 300 }, c: { start: 50, end: null } })
    expect(locked).toEqual(["d"])
  })

  it("treats a closure from the start that reopens as a rule ending then", () => {
    expect(readClosures({ closed_lanes: ["a"], events: [{ time: 90, lane_id: "a", closed: false }] }).rules).toEqual({ a: { start: 0, end: 90 } })
  })

  it("has no closures when none are set", () => {
    expect(readClosures({})).toEqual({ rules: {}, locked: [] })
  })
})

describe("writing closures back", () => {
  const base = { traffic_density: "low", slow_lanes: { z: 0.5 }, events: [{ time: 10, lane_id: "z", speed_factor: 0.5 }, { time: 5, lane_id: "d", closed: true }, { time: 8, lane_id: "d", closed: false }, { time: 9, lane_id: "d", closed: true }] }

  it("keeps speed events and the lanes it cannot edit, and replaces the rest", () => {
    const written = writeClosures(base, { a: { start: 0, end: null }, b: { start: 100, end: 300 }, c: { start: 0, end: 90 } }, ["d"])
    expect(written.closed_lanes).toEqual(["a", "c"])
    expect(written.events).toEqual([
      { time: 5, lane_id: "d", closed: true }, { time: 8, lane_id: "d", closed: false }, { time: 9, lane_id: "d", closed: true },
      { time: 10, lane_id: "z", speed_factor: 0.5 }, { time: 90, lane_id: "c", closed: false },
      { time: 100, lane_id: "b", closed: true }, { time: 300, lane_id: "b", closed: false },
    ].sort((x, y) => x.time - y.time))
    expect(written.traffic_density).toBe("low")
  })

  it("round-trips", () => {
    const rules = { a: { start: 0, end: null }, b: { start: 100, end: 300 }, c: { start: 0, end: 90 } }
    expect(readClosures(writeClosures({}, rules, [])).rules).toEqual(rules)
  })

  it("leaves no closed_lanes entry when nothing is closed", () => {
    expect(writeClosures({ closed_lanes: ["a"] }, {}, []).closed_lanes).toEqual([])
  })
})

describe("rules in words", () => {
  it("describes the whole run, a start only and a start and end", () => {
    expect(describeRule({ start: 0, end: null })).toBe("whole run")
    expect(describeRule({ start: 120, end: null })).toBe("from 120 s")
    expect(describeRule({ start: 0, end: 90 })).toBe("until 90 s")
    expect(describeRule({ start: 120, end: 300 })).toBe("120–300 s")
  })

  it("refuses an end that does not follow the start, and negative times", () => {
    expect(ruleProblem({ start: 100, end: 100 })).toMatch(/after/)
    expect(ruleProblem({ start: -1, end: null })).toMatch(/negative|0/)
    expect(ruleProblem({ start: 0, end: null })).toBeNull()
  })
})

describe("a form's closure times", () => {
  it("reports the first bad rule and nothing for good ones", () => {
    expect(closureProblem({ events: [{ time: 100, lane_id: "a", closed: true }, { time: 100, lane_id: "a", closed: false }] })).toMatch(/after/)
    expect(closureProblem({ closed_lanes: ["a"] })).toBeNull()
  })
})

describe("grouping lanes into road pieces", () => {
  const lanes = [
    { id: "road2f", road_id: "road2", road_name: "Capitol Road", direction: "eastbound", kind: "link", where: "west, 0–226 m out" },
    { id: "road2r", road_id: "road2", road_name: "Capitol Road", direction: "westbound", kind: "link", where: "west, 0–226 m out" },
    { id: "road0f", road_id: "road0", road_name: "Dalisay Road", direction: "northbound", kind: "exit", where: "south, 0–134 m out" },
  ]
  it("pairs the two directions of a road under one row", () => {
    const groups = groupRoads(lanes as never)
    expect(groups.map(group => [group.roadId, group.lanes.map(lane => lane.id)])).toEqual([["road0", ["road0f"]], ["road2", ["road2f", "road2r"]]])
    expect(groups[1].title).toBe("Capitol Road · west, 0–226 m out")
  })
})

describe("closures in words for a scenario record", () => {
  const lanes = [{ id: "road2r", road_id: "road2", road_name: "Capitol Road", direction: "westbound", kind: "link", where: "west, 0–226 m out" }]
  it("names each closed road piece with its direction and timing", () => {
    expect(closureLines({ closed_lanes: ["road2r"] }, lanes as never)).toEqual(["Capitol Road · west, 0–226 m out · westbound — whole run"])
    expect(closureLines({ events: [{ time: 60, lane_id: "road2r", closed: true }, { time: 90, lane_id: "road2r", closed: false }] }, lanes as never)).toEqual(["Capitol Road · west, 0–226 m out · westbound — 60–90 s"])
    expect(closureLines({}, lanes as never)).toEqual([])
  })
})

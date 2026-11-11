import { describe, expect, it } from "vitest"
import type { NativeScenarioConfig } from "@/api/native-scenario"
import type { ClosureOverride } from "@/api/routes"
import { closuresIntoConfig, routeScenarioDraft } from "./route-scenario"

const saved: NativeScenarioConfig = {
  traffic_density: "high", pedestrian_density: "low", green_seconds: 40,
  closed_lanes: ["old_a"],
  closure_responses: { old_a: "wait", old_timed: "nearest_exit" },
  events: [
    { time: 60, lane_id: "old_timed", closed: true },
    { time: 120, lane_id: "old_timed", closed: false },
    { time: 30, lane_id: "slow_road", speed_factor: 0.5 },
  ],
}

describe("Route Planner closures in a scenario", () => {
  it("makes the planner's closures the whole-run closures and keeps everything else", () => {
    const next = closuresIntoConfig(saved, { closedLanes: ["z", "a"], closureResponses: { z: "side_street", a: "share" } })
    expect(next.closed_lanes).toEqual(["a", "z"])
    expect(next.closure_responses).toEqual({ a: "share", z: "side_street" })
    expect(next).toMatchObject({ traffic_density: "high", pedestrian_density: "low", green_seconds: 40 })
  })

  it("drops the base scenario's timed closures and reopenings but keeps its speed events", () => {
    const next = closuresIntoConfig(saved, { closedLanes: ["a"], closureResponses: {} })
    expect(next.events).toEqual([{ time: 30, lane_id: "slow_road", speed_factor: 0.5 }])
  })

  it("keeps a response only for a lane that is closed", () => {
    const next = closuresIntoConfig(saved, { closedLanes: ["a"], closureResponses: { a: "wait", gone: "wait" } })
    expect(next.closure_responses).toEqual({ a: "wait" })
  })

  it("does not change the settings it was given", () => {
    const before = structuredClone(saved)
    closuresIntoConfig(saved, { closedLanes: ["a"], closureResponses: {} })
    expect(saved).toEqual(before)
  })
})

describe("the draft handed to the New Scenario form", () => {
  const context = { network_id: "site-a" }
  const closures: ClosureOverride = { closed_lanes: ["b", "a"], closure_responses: { a: "wait" } }

  it("starts from the site when the planner is a temporary arrangement", () => {
    expect(routeScenarioDraft({ source: { kind: "network", network_id: "site-a" }, context, closures }))
      .toEqual({ networkId: "site-a", baseScenarioId: null, baseScenarioName: null, closedLanes: ["a", "b"], closureResponses: { a: "wait" } })
  })

  it("remembers the saved scenario it was based on, by id and name", () => {
    expect(routeScenarioDraft({ source: { kind: "scenario", scenario_id: 7 }, context, closures, scenarioName: "Market day" }))
      .toMatchObject({ baseScenarioId: 7, baseScenarioName: "Market day" })
  })

  it("has no draft without closed roads", () => {
    expect(routeScenarioDraft({ source: { kind: "network", network_id: "site-a" }, context, closures: { closed_lanes: [], closure_responses: {} } })).toBeNull()
    expect(routeScenarioDraft({ source: null, context, closures })).toBeNull()
  })
})

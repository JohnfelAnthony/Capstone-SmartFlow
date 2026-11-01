import { describe, expect, it } from "vitest"
import { automaticMaximumRed, fixedTimeRed, groupWithNext, movePhase, phaseKey, splitGroup, walkRed } from "./signal-plan"

const plan = { phase_order: ["north", "east", "south", "west", "pedestrian"], green_seconds: 14, yellow_seconds: 3, all_red_seconds: 1 }
const grouped = { phase_order: [["north", "south"], ["east", "west"], "pedestrian"], green_seconds: 14, yellow_seconds: 3, all_red_seconds: 1, phase_greens: [39, 23, 10] }

describe("signal plan timing", () => {
  it("matches the engine's own fixed-time red: an 87 s cycle minus 14 s green", () => {
    expect(fixedTimeRed(plan)).toBe(73)
  })
  it("uses 120 s automatically unless the plan's own red is longer", () => {
    expect(automaticMaximumRed(plan)).toBe(120)
    expect(automaticMaximumRed({ ...plan, green_seconds: 40 })).toBe(5 * 40 + 5 + 4 * 3 - 40)
  })
  it("fixed-time red uses per-phase greens", () => {
    expect(fixedTimeRed({ phase_order: [["north", "south"], ["east", "west"]], green_seconds: 14, yellow_seconds: 3, all_red_seconds: 1, phase_greens: [39, 23] })).toBe(47)
  })
  it("the maximum-red check uses the longest vehicle red, not the walk phase's", () => {
    expect(fixedTimeRed(grouped)).toBe(58)
    expect(walkRed(grouped)).toBe(71)
  })
  it("names a group by its members joined with +, as the engine does", () => {
    expect([phaseKey(["north", "south"]), phaseKey("pedestrian")]).toEqual(["north+south", "pedestrian"])
  })
})

describe("editing the phase order", () => {
  const four = { phase_order: ["north", "south", "east", "west", "pedestrian"] as (string | string[])[], phase_greens: [20, 30, 25, 15, 10] }
  it("groups a phase with the next one and keeps one green for the group", () => {
    expect(groupWithNext(four, 0)).toEqual({ phase_order: [["north", "south"], "east", "west", "pedestrian"], phase_greens: [20, 25, 15, 10] })
  })
  it("never groups the walk phase", () => {
    expect(groupWithNext(four, 3)).toBeNull()
    expect(groupWithNext(four, 4)).toBeNull()
  })
  it("splits a group back into approaches that each keep the group's green", () => {
    const merged = { phase_order: [["north", "south"], "east", "west", "pedestrian"] as (string | string[])[], phase_greens: [20, 25, 15, 10] }
    expect(splitGroup(merged, 0)).toEqual({ phase_order: ["north", "south", "east", "west", "pedestrian"], phase_greens: [20, 20, 25, 15, 10] })
    expect(splitGroup(four, 1)).toBeNull()
  })
  it("moves a phase together with its green, and works without per-phase greens", () => {
    expect(movePhase(four, 1, -1)).toEqual({ phase_order: ["south", "north", "east", "west", "pedestrian"], phase_greens: [30, 20, 25, 15, 10] })
    expect(movePhase({ phase_order: ["a", "b"] }, 0, 1)).toEqual({ phase_order: ["b", "a"] })
  })
})

import { describe, expect, it } from "vitest"
import { automaticMaximumRed, fixedTimeRed } from "./signal-plan"

const plan = { phase_order: ["north", "east", "south", "west", "pedestrian"], green_seconds: 14, yellow_seconds: 3, all_red_seconds: 1 }

describe("signal plan timing", () => {
  it("matches the engine's own fixed-time red: an 87 s cycle minus 14 s green", () => {
    expect(fixedTimeRed(plan)).toBe(73)
  })
  it("uses 120 s automatically unless the plan's own red is longer", () => {
    expect(automaticMaximumRed(plan)).toBe(120)
    expect(automaticMaximumRed({ ...plan, green_seconds: 40 })).toBe(5 * 40 + 5 + 4 * 3 - 40)
  })
})

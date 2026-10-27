import { describe, expect, it } from "vitest"
import { matchingMixPreset, mixShares } from "./vehicle-mix"

const presets = {
  tagum_provisional: { label: "Tagum (provisional)", mix: { motorcycle: 0.55, tricycle: 0.25, car: 0.15, truck: 0.03, bus: 0.02 } },
  cars_only: { label: "Cars only", mix: { car: 1 } },
}

describe("vehicle mix presets", () => {
  it("matches presets by proportion, not by scale", () => {
    expect(matchingMixPreset({ motorcycle: 55, tricycle: 25, car: 15, truck: 3, bus: 2 }, presets)).toBe("tagum_provisional")
    expect(matchingMixPreset({ car: 1 }, presets)).toBe("cars_only")
  })

  it("leaves a saved custom mix unmatched", () => {
    expect(matchingMixPreset({ car: 65, motorcycle: 15, tricycle: 10, bus: 5, truck: 5 }, presets)).toBeNull()
    expect(matchingMixPreset(undefined, presets)).toBeNull()
  })

  it("lists shares in descending percent", () => {
    expect(mixShares({ car: 3, motorcycle: 1 })).toEqual([{ type: "car", percent: 75 }, { type: "motorcycle", percent: 25 }])
  })
})

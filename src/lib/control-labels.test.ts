import { describe, expect, it } from "vitest"
import { controlLabel, isRlControl } from "./control-labels"

describe("controlLabel", () => {
  it("names the no-signal condition without calling it a controller or RL", () => {
    expect(controlLabel("no-signal")).toBe("No signal (first come, first served)")
  })
  it("keeps fixed-time and playback distinct", () => {
    expect(controlLabel("fixed-time")).toBe("Fixed-time")
    expect(controlLabel("playback")).toBe("Playback")
  })
  it("names RL by algorithm, with or without a model id", () => {
    expect(controlLabel("ql")).toBe("SmartFlow RL (QL)")
    expect(controlLabel("ql:7")).toBe("SmartFlow RL (QL)")
    expect(controlLabel("dql:3")).toBe("SmartFlow RL (DQL)")
    expect(controlLabel("ppo:12")).toBe("SmartFlow RL (PPO)")
  })
  it("falls back to a readable name for unknown or missing modes", () => {
    expect(controlLabel("all-way-stop")).toBe("all way stop")
    expect(controlLabel(null)).toBe("unknown")
  })
})

describe("isRlControl", () => {
  it("is true only for trained-policy modes", () => {
    expect(["ql", "dql:3", "ppo:12"].every(isRlControl)).toBe(true)
    expect(["no-signal", "fixed-time", "playback", ""].some(isRlControl)).toBe(false)
  })
})

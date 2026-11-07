import { describe, expect, it } from "vitest"
import { resumeTargetCompatible } from "./rl-resume"

const model = { compatible: false, checkpoints: [{ id: 3, compatible: true }, { id: 4, compatible: false }] }

describe("resumeTargetCompatible", () => {
  it("follows the selected checkpoint when there is one, so a compatible checkpoint can resume without a final artifact", () => {
    expect(resumeTargetCompatible(model, 3)).toBe(true)
    expect(resumeTargetCompatible(model, 4)).toBe(false)
  })
  it("follows the final model artifact without a checkpoint, and is false without a model", () => {
    expect(resumeTargetCompatible(model, null)).toBe(false)
    expect(resumeTargetCompatible({ ...model, compatible: true }, null)).toBe(true)
    expect(resumeTargetCompatible(undefined, null)).toBe(false)
  })
})

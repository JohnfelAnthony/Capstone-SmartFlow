import { describe, expect, it } from "vitest"
import { advancePlayback, frameAtTime, frameWindow, kpiChange, studyQueue } from "./compare-view"

describe("kpiChange", () => {
  it("marks a drop in a lower-is-better metric as better and a rise as worse", () => {
    expect(kpiChange(10, 8, true)).toEqual({ delta: -2, tone: "better" })
    expect(kpiChange(10, 12, true)).toEqual({ delta: 2, tone: "worse" })
  })
  it("marks a rise in a higher-is-better metric as better", () => {
    expect(kpiChange(100, 120, false)).toEqual({ delta: 20, tone: "better" })
  })
  it("stays neutral, with no difference, when a value is unavailable", () => {
    expect(kpiChange(null, 5, true)).toEqual({ delta: null, tone: "neutral" })
    expect(kpiChange(5, null, true)).toEqual({ delta: null, tone: "neutral" })
  })
  it("stays neutral when the metric has no direction or the change is negligible", () => {
    expect(kpiChange(3, 7, null)).toEqual({ delta: 4, tone: "neutral" })
    expect(kpiChange(5, 5.00001, true).tone).toBe("neutral")
  })
})

describe("frameWindow", () => {
  it("aligns windows to multiples of the window length", () => {
    expect(frameWindow(0)).toEqual({ start: 0, end: 60 })
    expect(frameWindow(135)).toEqual({ start: 120, end: 180 })
  })
})

describe("frameAtTime", () => {
  it("returns the last frame at or before the time, or -1 before the first", () => {
    expect(frameAtTime([0, 0.5, 1], 0.7)).toBe(1)
    expect(frameAtTime([0, 0.5, 1], 5)).toBe(2)
    expect(frameAtTime([10, 11], 5)).toBe(-1)
    expect(frameAtTime([], 5)).toBe(-1)
  })
})

describe("advancePlayback", () => {
  it("moves by elapsed time times the speed and stops at the end", () => {
    expect(advancePlayback(10, 500, 2, 300)).toEqual({ time: 11, finished: false })
    expect(advancePlayback(299.5, 1000, 1, 300)).toEqual({ time: 300, finished: true })
  })
})

describe("studyQueue", () => {
  it("sums the four approach queues", () => {
    expect(studyQueue({ north: 2, east: 0, south: 3, west: 1 })).toBe(6)
    expect(studyQueue(undefined)).toBe(0)
  })
})

import { createMapInterpolator } from "@/simulation/map-navigation"
import type { RenderFrame } from "@/simulation/frame-types"
import { describe, expect, it } from "vitest"
import { advancePlayback, compareCanvasFrame, compareFrameWindow, frameAtTime, frameWindow, kpiChange, studyJunctionId, studyQueue, windowsNear, windowsToRequest } from "./compare-view"

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

describe("studyJunctionId", () => {
  it("finds the junction selected for RL, or null", () => {
    expect(studyJunctionId({ junction_controls: { a: { selected_for_rl: false }, b: { selected_for_rl: true } } })).toBe("b")
    expect(studyJunctionId({ junction_controls: { a: {} } })).toBeNull()
    expect(studyJunctionId(null)).toBeNull()
  })
})

describe("windowsToRequest", () => {
  it("asks again for a window that was dropped from the cache, but not for loaded or in-flight ones", () => {
    expect(windowsToRequest([0, 10], { 20: 1, 30: 1 }, new Set())).toEqual([0, 10])
    expect(windowsToRequest([0, 10], { 0: 1 }, new Set())).toEqual([10])
    expect(windowsToRequest([0, 10], {}, new Set([10]))).toEqual([0])
  })
})

describe("windowsNear", () => {
  it("keeps only the windows within reach of the requested one", () => {
    expect(Object.keys(windowsNear({ 0: 1, 10: 1, 50: 1, 60: 1 }, 50, 30)).map(Number)).toEqual([50, 60])
  })
})

describe("compare playback and the map interpolator", () => {
  function snapshot(time: number): RenderFrame {
    return {
      time, step_length: 0.1, status: "running", intersection_id: "test", render_mode: "idle",
      playback: { active: false, frame_index: 0, frame_count: 0 },
      render_ts: time, flow_state: "IDLE", phase: "ALL_RED", ns_state: "r", ew_state: "r",
      vehicle_count: 1, pedestrian_count: 0,
      vehicles: [{
        id: "car", x: time * 10, y: 0, angle: 0, speed: 10,
        lane_id: "lane", lane_position: time * 10, length: 4, width: 2,
        stopped: false, visual_type: "car",
      }],
      pedestrians: [],
      visual: { closed_lanes: [], slow_lanes: {} },
      junction_controls: {},
      traffic_lights: {},
    }
  }

  it.each([1, 2, 4])("interpolates at %sx, snaps on seek and freezes on pause", (speed) => {
    const map = createMapInterpolator()
    const position = (now: number) => map.sample(now)?.vehicles[0].x
    for (let tick = 0; tick <= 16; tick++) {
      map.set(compareCanvasFrame(snapshot(tick * speed / 10), true, speed, 0), "run", tick * 100)
      position(tick * 100)
    }
    const before = position(1600)!
    const after = position(1650)!
    expect(after - before).toBeGreaterThan(0.4 * speed)
    expect(after - before).toBeLessThan(0.6 * speed)
    map.set(compareCanvasFrame(snapshot(8), true, speed, 1), "run", 1700)
    expect(position(1700)).toBe(80)
    map.set(compareCanvasFrame(snapshot(8.2), false, speed, 1), "run", 1800)
    expect(position(1800)).toBe(82)
    expect(position(2000)).toBe(82)
    expect(map.moving()).toBe(false)
  })

  it("uses the last shared frame's window when seeking into a gap", () => {
    const times = [0.5, 7.5, 36, 40]
    expect(compareFrameWindow(times, 0, 10)).toBe(0)
    expect(compareFrameWindow(times, 25, 10)).toBe(0)
    expect(compareFrameWindow(times, 36, 10)).toBe(30)
    expect(compareFrameWindow(times, 40, 10)).toBe(40)
    expect(windowsNear({ 0: "current", 80: "next", 120: "old" }, 0, 30, 80)).toEqual({ 0: "current", 80: "next" })
  })
})

import { describe, expect, it } from "vitest"
import type { RenderFrame, RenderVehicle } from "@/simulation/frame-types"
import { interpolationDuration, interpolateVehicle, isPresentationJump } from "@/simulation/entity-interpolation"

const vehicle: RenderVehicle = { id: "synthetic-vehicle", x: 10, y: 20, angle: 90, speed: 3,
  lane_id: "lane-A", lane_position: 10, length: 3, width: 1.4, stopped: false, visual_type: "tricycle", emergency: false, wait_time: 2 }

function frame(overrides: Partial<RenderFrame> = {}): RenderFrame {
  return { time: 2, render_ts: 100, step_length: .1, status: "running", flow_state: "LIVE_RUNNING",
    intersection_id: "network-A", phase: "NORTH_GREEN", ns_state: "green", ew_state: "red", render_mode: "live",
    vehicle_count: 1, pedestrian_count: 0, playback: { active: false, frame_index: 0, frame_count: 0 },
    vehicles: [vehicle], pedestrians: [], visual: { closed_lanes: [], slow_lanes: {} }, junction_controls: {}, traffic_lights: {}, ...overrides }
}

const degrees = (angle: number) => (angle % 360 + 360) % 360

describe("authoritative entity interpolation lifecycle", () => {
  it("uses snapshot delivery timing, falling back to the supplied native step length", () => {
    expect(interpolationDuration(frame(), frame({ render_ts: 100.25 }))).toBe(250)
    expect(interpolationDuration(null, frame({ step_length: .2 }))).toBe(200)
    expect(interpolationDuration(frame(), frame({ render_ts: 100, step_length: .3 }))).toBe(300)
    expect(interpolationDuration(frame(), frame({ render_ts: 99, step_length: .05 }))).toBe(50)
  })

  it("keeps long or invalid delivery gaps within a bounded interpolation window", () => {
    expect(interpolationDuration(frame(), frame({ render_ts: 110 }))).toBe(1000)
    expect(interpolationDuration(null, frame({ step_length: 0 }))).toBe(1)
  })

  it("interpolates position without replacing authoritative speed/wait/class metadata", () => {
    const target = { ...vehicle, x: 30, y: 50, speed: 0, wait_time: 12, stopped: true }
    const middle = interpolateVehicle(vehicle, target, 50, 100)
    expect(middle.x).toBe(20)
    expect(middle.y).toBe(35)
    expect(middle.speed).toBe(0)
    expect(middle.wait_time).toBe(12)
    expect(middle.stopped).toBe(true)
    expect(middle.visual_type).toBe("tricycle")
    expect(middle.length).toBe(3)
  })

  it("never extrapolates beyond the authoritative target through a stop line", () => {
    const target = { ...vehicle, x: 12, y: 22, angle: 180, stopped: true, speed: 0 }
    for (const elapsed of [100, 1000, 60000]) {
      const result = interpolateVehicle(vehicle, target, elapsed, 100)
      expect({ x: result.x, y: result.y }).toEqual({ x: target.x, y: target.y })
      expect(degrees(result.angle)).toBe(target.angle)
    }
    const early = interpolateVehicle(vehicle, target, -10, 100)
    expect({ x: early.x, y: early.y }).toEqual({ x: vehicle.x, y: vehicle.y })
  })

  it("turns by the shortest heading arc across north without a full spin", () => {
    const clockwise = interpolateVehicle({ ...vehicle, angle: 350 }, { ...vehicle, angle: 10 }, 50, 100)
    expect(degrees(clockwise.angle)).toBe(0)
    const counterclockwise = interpolateVehicle({ ...vehicle, angle: 10 }, { ...vehicle, angle: 350 }, 50, 100)
    expect(degrees(counterclockwise.angle)).toBe(0)
    for (const angle of [0, 90, 180, 270]) {
      expect(degrees(interpolateVehicle(vehicle, { ...vehicle, angle }, 100, 100).angle)).toBe(angle)
    }
  })

  it("snaps initial frames, run/reset tokens, network changes and mode changes", () => {
    expect(isPresentationJump(null, frame(), "run-A", "run-A")).toBe(true)
    expect(isPresentationJump(frame(), frame(), "run-A", "run-B")).toBe(true)
    expect(isPresentationJump(frame(), frame(), "run-A:revision0", "run-A:revision1")).toBe(true)
    expect(isPresentationJump(frame(), frame({ intersection_id: "network-B" }), "run-A", "run-A")).toBe(true)
    expect(isPresentationJump(frame(), frame({ render_mode: "playback" }), "run-A", "run-A")).toBe(true)
  })

  it("snaps pause/completion/stop and backward simulation time", () => {
    for (const status of ["paused", "completed", "stopped", "error"]) {
      expect(isPresentationJump(frame(), frame({ status }), "run-A", "run-A")).toBe(true)
    }
    expect(isPresentationJump(frame(), frame({ time: 1 }), "run-A", "run-A")).toBe(true)
    expect(isPresentationJump(frame(), frame({ time: 2.1 }), "run-A", "run-A")).toBe(false)
  })

  it("snaps nonadjacent replay seeks and permits ordinary consecutive playback frames", () => {
    const old = frame({ render_mode: "playback", playback: { active: true, frame_index: 10, frame_count: 100 } })
    expect(isPresentationJump(old, frame({ render_mode: "playback", playback: { active: true, frame_index: 11, frame_count: 100 } }), "recording-A", "recording-A")).toBe(false)
    expect(isPresentationJump(old, frame({ render_mode: "playback", time: 1, playback: { active: true, frame_index: 5, frame_count: 100 } }), "recording-A", "recording-A")).toBe(true)
    expect(isPresentationJump(old, frame({ render_mode: "playback", time: 3, playback: { active: true, frame_index: 30, frame_count: 100 } }), "recording-A", "recording-A")).toBe(true)
    // Host revision tokens cover an explicit seek to an adjacent frame too.
    expect(isPresentationJump(old, frame({ render_mode: "playback", playback: { active: true, frame_index: 11, frame_count: 100 } }), "recording-A:0", "recording-A:1")).toBe(true)
  })
})

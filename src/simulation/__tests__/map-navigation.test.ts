import { describe, expect, it } from "vitest"
import { boundMapPan, claimMapLabel, createMapInterpolator, fitMap, mapScale, mapToScreen, resizeMap, screenToMap, zoomMapAt } from "@/simulation/map-navigation"
import type { RenderFrame } from "@/simulation/frame-types"

const bounds = { min_x: -100, max_x: 100, min_y: -50, max_y: 50 }
function frame(x: number, overrides: Partial<RenderFrame> = {}): RenderFrame {
  return { time: x, render_ts: x / 100, step_length: .1, status: "running", flow_state: "LIVE_RUNNING", intersection_id: "test", render_mode: "live", phase: "NORTH_GREEN", ns_state: "green", ew_state: "red", vehicle_count: 1, pedestrian_count: 1,
    vehicles: [{ id: "v", x, y: 0, angle: 90, speed: 2, lane_id: "a", lane_position: x, length: 4.5, width: 1.8, stopped: false, visual_type: "car", emergency: false }],
    pedestrians: [{ id: "p", x, y: 5, speed: 1, lane_id: "p", stopped: false }], visual: { closed_lanes: [], slow_lanes: {} }, playback: { active: false, frame_index: 0, frame_count: 0 }, junction_controls: {}, traffic_lights: {}, ...overrides }
}
describe("2D map navigation", () => {
  it("round-trips native coordinates and keeps north at the top", () => {
    const camera = fitMap(bounds, 800, 500), point = { x: 12, y: 7 }
    const restored = screenToMap(mapToScreen(point, camera), camera)
    expect(restored.x).toBeCloseTo(point.x); expect(restored.y).toBeCloseTo(point.y)
    expect(mapToScreen({ x: 0, y: 1 }, camera).y).toBeLessThan(mapToScreen({ x: 0, y: 0 }, camera).y)
  })
  it("anchors wheel/pinch zoom at the cursor even when clamped", () => {
    const camera = fitMap(bounds, 800, 500), pointer = { x: 235, y: 160 }
    for (const factor of [.001, .5, 2, 1000]) {
      const zoomed = zoomMapAt(camera, pointer, factor, .5, 28), before = screenToMap(pointer, camera), after = screenToMap(pointer, zoomed)
      expect(after.x).toBeCloseTo(before.x); expect(after.y).toBeCloseTo(before.y)
      expect(zoomed.scale).toBeGreaterThanOrEqual(.5); expect(zoomed.scale).toBeLessThanOrEqual(28)
    }
  })
  it("keeps the same world center on resize and bounds navigation to reachable network context", () => {
    const camera = fitMap(bounds, 800, 500), resized = resizeMap(camera, 1200, 700)
    expect(screenToMap({ x: 600, y: 350 }, resized)).toEqual(screenToMap({ x: 400, y: 250 }, camera))
    const bounded = boundMapPan({ ...camera, ox: 1e6, oy: -1e6 }, bounds)
    const center = screenToMap({ x: 400, y: 250 }, bounded)
    expect(center.x).toBeCloseTo(-170); expect(center.y).toBeCloseTo(-120)
  })
  it("uses readable metric scale lengths", () => {
    expect(mapScale(4)).toEqual({ pixels: 80, label: "20 m" })
    expect(mapScale(.04)).toEqual({ pixels: 80, label: "2 km" })
  })
  it("moves labels away from collisions and suppresses labels with no room", () => {
    const occupied = [{ x: 10, y: 10, width: 50, height: 20 }]
    expect(claimMapLabel([{ x: 15, y: 12, width: 30, height: 15 }, { x: 70, y: 12, width: 30, height: 15 }], occupied, 200, 100)?.x).toBe(70)
    expect(claimMapLabel([{ x: 15, y: 12, width: 30, height: 15 }, { x: 195, y: 12, width: 30, height: 15 }], occupied, 200, 100)).toBeNull()
  })
})
describe("2D displayed-frame interpolation", () => {
  it("moves both entity types, uses target metadata and never extrapolates", () => {
    const stream = createMapInterpolator(); stream.set(frame(0), "run", 0); stream.set(frame(10), "run", 100)
    const middle = stream.sample(150)!
    expect(middle.vehicles[0].x).toBe(5); expect(middle.pedestrians[0].x).toBe(5); expect(middle.time).toBe(10)
    expect(stream.sample(1000)!.vehicles[0].x).toBe(10); expect(stream.moving(1000)).toBe(false)
  })
  it("starts a new delivery from the current displayed position instead of jumping backward", () => {
    const stream = createMapInterpolator(); stream.set(frame(0), "run", 0); stream.set(frame(10), "run", 100)
    stream.set(frame(20), "run", 150)
    expect(stream.sample(150)!.vehicles[0].x).toBe(5)
    expect(stream.sample(200)!.vehicles[0].x).toBe(12.5)
  })
  it("snaps pause, run reset and backward seek and discards departed entities", () => {
    const stream = createMapInterpolator(); stream.set(frame(0), "run", 0); stream.set(frame(10), "run", 100)
    stream.set(frame(10, { status: "paused" }), "run", 125)
    expect(stream.sample(125)!.vehicles[0].x).toBe(10); expect(stream.moving(125)).toBe(false)
    stream.set(frame(1), "new-run", 130); expect(stream.sample(130)!.vehicles[0].x).toBe(1)
    stream.set(frame(0, { vehicles: [], pedestrians: [] }), "new-run", 140)
    expect(stream.sample(140)!.vehicles).toEqual([]); expect(stream.sample(140)!.pedestrians).toEqual([])
  })
  it("does not animate stationary or empty snapshots while keeping current metrics", () => {
    const stream = createMapInterpolator(); stream.set(frame(0), "run", 0)
    stream.set(frame(0, { time: 1, render_ts: .1, phase: "EAST_GREEN" }), "run", 100)
    expect(stream.moving(100)).toBe(false)
    expect(stream.sample(100)!.phase).toBe("EAST_GREEN")
    stream.set(frame(0, { time: 2, render_ts: .2, vehicles: [], pedestrians: [] }), "run", 200)
    expect(stream.moving(200)).toBe(false)
    expect(stream.sample(200)!.vehicles).toEqual([])
  })
  it("finishes in-flight motion when a stationary delivery arrives before the last target", () => {
    const stream = createMapInterpolator(); stream.set(frame(0), "run", 0); stream.set(frame(10), "run", 100)
    stream.set(frame(10, { time: 11, render_ts: .15 }), "run", 150)
    expect(stream.moving(150)).toBe(true)
    expect(stream.sample(150)!.vehicles[0].x).toBe(5)
    expect(stream.sample(200)!.vehicles[0].x).toBe(10)
    expect(stream.moving(200)).toBe(false)
  })
  it("snaps explicit adjacent replay seeks and clears the display when a run is unloaded", () => {
    const stream = createMapInterpolator()
    stream.set(frame(0, { render_mode: "playback", playback: { active: true, frame_index: 0, frame_count: 10 } }), "recording:0", 0)
    stream.set(frame(10, { render_mode: "playback", playback: { active: true, frame_index: 1, frame_count: 10 } }), "recording:1", 100)
    expect(stream.sample(100)!.vehicles[0].x).toBe(10)
    expect(stream.moving(100)).toBe(false)
    stream.set(null, "", 125)
    expect(stream.sample(125)).toBeNull(); expect(stream.moving(125)).toBe(false)
  })
})

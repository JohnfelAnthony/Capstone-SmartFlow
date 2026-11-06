import { describe, expect, it } from "vitest"
import { boundMapPan, claimMapLabel, createMapInterpolator, fitMap, mapScale, mapToScreen, resizeMap, screenToMap, zoomMapAt } from "@/simulation/map-navigation"
import type { RenderFrame } from "@/simulation/frame-types"

const bounds = { min_x: -100, max_x: 100, min_y: -50, max_y: 50 }
function frame(x: number, overrides: Partial<RenderFrame> = {}): RenderFrame {
  return { time: x, render_ts: x / 100, step_length: .1, status: "running", flow_state: "LIVE_RUNNING", intersection_id: "test", render_mode: "live", phase: "NORTH_GREEN", ns_state: "green", ew_state: "red", vehicle_count: 1, pedestrian_count: 1,
    vehicles: [{ id: "v", x, y: 0, angle: 90, speed: 2, lane_id: "a", lane_position: x, length: 4.5, width: 1.8, stopped: false, visual_type: "car" }],
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
describe("2D displayed-frame playback", () => {
  // Simulation time equals wall time here (1x speed); each frame is delivered at `now` milliseconds.
  const at = (time: number, x: number, overrides: Partial<RenderFrame> = {}) => frame(x, { time, render_ts: time, ...overrides })

  it("plays steadily between frames, uses the next frame's metadata and never extrapolates", () => {
    const stream = createMapInterpolator()
    for (let tick = 0; tick <= 10; tick++) stream.set(at(tick / 10, tick, { phase: `P${tick}` }), "run", tick * 100)
    const shown = stream.sample(1000)!
    expect(shown.vehicles[0].x).toBeGreaterThan(7); expect(shown.vehicles[0].x).toBeLessThan(10)
    expect(shown.phase).toBe(`P${Math.ceil(shown.vehicles[0].x)}`)
    expect(stream.moving()).toBe(true)
    // No further frames arrive: the display stops at the newest frame and goes no further.
    expect(stream.sample(5000)!.vehicles[0].x).toBe(10); expect(stream.moving()).toBe(false)
  })

  it("keeps a constant speed when frames arrive unevenly or carry two engine ticks", () => {
    // One car at 10 m/s; the engine ticks every 100 ms. Before this fix the display swung by 42-92% between paints and froze.
    for (const [every, noise] of [[110, 0], [100, 30]]) {
      let seed = 7
      const random = () => (seed = seed * 16807 % 2147483647) / 2147483647
      const deliveries = Array.from({ length: Math.floor(20000 / every) }, (_, index) => {
        const wall = index * every, time = Math.floor(wall / 100) / 10
        return { arrives: wall + random() * noise, frame: at(time, time * 10, { render_ts: (wall + random() * noise) / 1000 }) }
      })
      const stream = createMapInterpolator(), speeds: number[] = []
      let next = 0, previous: number | null = null
      for (let now = 0; now < 19000; now += 1000 / 60) {
        while (next < deliveries.length && deliveries[next].arrives <= now) stream.set(deliveries[next++].frame, "run", now)
        const x = stream.sample(now)?.vehicles[0].x ?? 0
        if (previous !== null && now > 2000) speeds.push((x - previous) * 60)
        previous = x
      }
      const swings = speeds.map((speed) => Math.abs(speed - 10) / 10).sort((a, b) => a - b)
      expect(swings[Math.floor(swings.length * .95)]).toBeLessThan(.2)
      expect(Math.min(...speeds)).toBeGreaterThan(5)
    }
  })

  it("snaps pause, run reset and backward seek and discards departed entities", () => {
    const stream = createMapInterpolator(); stream.set(at(0, 0), "run", 0); stream.set(at(.1, 1), "run", 100)
    stream.set(at(.1, 1, { status: "paused" }), "run", 125)
    expect(stream.sample(125)!.vehicles[0].x).toBe(1); expect(stream.moving()).toBe(false)
    stream.set(at(5, 50), "run", 130); stream.set(at(1, 9), "run", 140)
    expect(stream.sample(140)!.vehicles[0].x).toBe(9)
    stream.set(at(0, 3), "new-run", 150); expect(stream.sample(150)!.vehicles[0].x).toBe(3)
    stream.set(at(.1, 4, { vehicles: [], pedestrians: [] }), "new-run", 250)
    expect(stream.sample(400)!.vehicles).toEqual([]); expect(stream.sample(400)!.pedestrians).toEqual([])
  })

  it("snaps explicit adjacent replay seeks and clears the display when a run is unloaded", () => {
    const stream = createMapInterpolator()
    stream.set(frame(0, { render_mode: "playback", playback: { active: true, frame_index: 0, frame_count: 10 } }), "recording:0", 0)
    stream.set(frame(10, { render_mode: "playback", playback: { active: true, frame_index: 1, frame_count: 10 } }), "recording:1", 100)
    expect(stream.sample(100)!.vehicles[0].x).toBe(10)
    expect(stream.moving()).toBe(false)
    stream.set(null, "", 125)
    expect(stream.sample(125)).toBeNull(); expect(stream.moving()).toBe(false)
  })
})

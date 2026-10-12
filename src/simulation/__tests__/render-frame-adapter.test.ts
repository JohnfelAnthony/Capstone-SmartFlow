/// <reference types="node" />
import { readFileSync } from "node:fs"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { SimulationStatePayload } from "@/api/simulation"
import type { RenderFrame } from "@/simulation/frame-types"
import { distributeEntities, mergeRenderFrame, renderFrameFromSimulation, timingLabel } from "@/simulation/render-frame-adapter"
import { useSimulationSocket } from "@/hooks/useSimulationSocket"

type Fixture = { name: string; state: SimulationStatePayload["state"]; expected: RenderFrame }
const fixtures = JSON.parse(readFileSync(new URL("../../../tests/fixtures/render-presentation.json", import.meta.url), "utf8")) as Fixture[]

function simulationFor(state: SimulationStatePayload["state"]): SimulationStatePayload {
  return { status: state.status ?? "running", owner_user_id: null, owner_name: null, active_run_id: 1,
    run_mode: "synthetic-test", speed_multiplier: 1, selected_scenario_id: null, selected_scenario_name: null,
    duration_seconds: 30, seed: 17, control_mode: "fixed_time", state }
}

function byteBudgetState(): SimulationStatePayload["state"] {
  return structuredClone(fixtures.find(fixture => fixture.name === "byte-budget")!.state)
}

describe("Python / HTTP presentation parity", () => {
  for (const fixture of fixtures) {
    it(`matches every serialized field and entity order for ${fixture.name}`, () => {
      const simulation = simulationFor(fixture.state)
      // Production HTTP supplies the authoritative Python allocation. A raw
      // historical fallback uses its own actual JavaScript JSON byte encoding.
      const source = fixture.name === "byte-budget" ? { ...simulation, render_frame: fixture.expected } : simulation
      expect(renderFrameFromSimulation(source, 0)).toEqual(fixture.expected)
    })
  }

  it("preserves engine units and request meanings until a display converts them", () => {
    const frame = renderFrameFromSimulation(simulationFor(fixtures[0].state), 0)!
    expect(frame.vehicles[1].speed).toBe(2)
    expect(frame.vehicles[1].wait_time).toBe(.1)
    expect(frame.pedestrians[1].wait_time).toBe(.5)
    expect(frame.lane_metrics!['lane-0'].mean_speed_mps).toBe(2)
    expect(frame.controller_events!.last_policy_decision).toMatchObject({ action: "SERVE_EAST", applied: true, reason: "queued_safely", time: 11 })
    expect(frame.junction_controls.J0.phase).toBe("NORTH_GREEN")
    expect(frame.junction_controls.J0.pending_service).toBe("east")
  })

  it("shows all default entities and allocates above-limit slots across lanes/junctions", () => {
    const state = structuredClone(fixtures[2].state)
    const frame = renderFrameFromSimulation(simulationFor(state), 0)!
    expect(frame.render_coverage).toEqual({ vehicles: { total: 304, shown: 300 }, pedestrians: { total: 132, shown: 128 }, limited: true, reason: "entity_limit" })
    for (let group = 0; group < 4; group++) {
      expect(frame.vehicles.filter(entity => entity.lane_id === `lane-${group}`)).toHaveLength(75)
      expect(frame.pedestrians.filter(entity => entity.lane_id === `J${group}`)).toHaveLength(32)
    }
    state.vehicles!.reverse()
    state.pedestrians!.reverse()
    expect(renderFrameFromSimulation(simulationFor(state), 0)).toEqual(frame)
    state.vehicles = state.vehicles!.slice(0, 300)
    state.pedestrians = state.pedestrians!.slice(0, 128)
    state.vehicle_count = 300
    state.pedestrian_count = 128
    const full = renderFrameFromSimulation(simulationFor(state), 0)!
    expect(full.vehicles).toHaveLength(300)
    expect(full.pedestrians).toHaveLength(128)
    expect(full.render_coverage!.limited).toBe(false)
    expect(full.render_coverage!.reason).toBeNull()
  })

  it("does not mutate an input population while sorting deterministic slots", () => {
    const entities = [{ id: "z", lane_id: "a" }, { id: "a", lane_id: "a" }, { id: "m", lane_id: "b" }]
    expect(distributeEntities(entities, 2).map(entity => entity.id)).toEqual(["a", "m"])
    expect(entities.map(entity => entity.id)).toEqual(["z", "a", "m"])
  })

  it("preserves telemetry and reports actual UTF-8 byte trimming", () => {
    const state = byteBudgetState()
    const frame = renderFrameFromSimulation(simulationFor(state), 0)!
    const encoded = JSON.stringify(frame)
    expect(new TextEncoder().encode(encoded).length).toBeLessThanOrEqual(262144)
    expect(new TextEncoder().encode(encoded).length).toBeGreaterThan(encoded.length)
    expect(frame.render_coverage!.reason).toBe("byte_limit")
    expect(frame.vehicles.length).toBeLessThan(300)
    expect(frame.pedestrians.length).toBeLessThan(128)
    expect(frame.lane_metrics).toEqual(state.metrics!.lanes)
    expect(frame.junction_metrics).toEqual(state.metrics!.junctions)
    expect(frame.junction_controls).toEqual(state.junction_controls)
    expect(frame.controller_events).toEqual(state.experiment)
    expect(renderFrameFromSimulation(simulationFor(state), 0)).toEqual(frame)
  })

  it("fails explicitly when metadata alone cannot fit, keeping source data intact", () => {
    const state = byteBudgetState()
    state.junction_controls!.J0.controller = "測".repeat(90000)
    const original = structuredClone(state)
    expect(() => renderFrameFromSimulation(simulationFor(state), 0)).toThrow(/metadata exceeds/i)
    expect(state).toEqual(original)
  })

  it("surfaces the server's explicit metadata error instead of reconstructing an incomplete frame", () => {
    const source = { ...simulationFor(fixtures[0].state), render_frame: null,
      render_frame_error: "Render metadata exceeds 262144 bytes; authoritative telemetry was preserved." }
    expect(() => renderFrameFromSimulation(source, 0)).toThrow(source.render_frame_error)
  })

  it("clears optional telemetry when an older recording replaces a newer frame", () => {
    const current = simulationFor(fixtures[0].state)
    const merged = mergeRenderFrame(current, fixtures[1].expected)!
    expect(merged.state.metrics?.lanes).toBeUndefined()
    expect(merged.state.metrics?.junctions).toBeUndefined()
    expect(merged.state.experiment?.last_policy_decision).toBeNull()
    expect(merged.state.experiment?.last_safety_override).toBeNull()
    expect(merged.state.visual?.pedestrian_paths).toBeUndefined()
    expect(merged.state.junction_controls?.J0.timing_kind).toBeUndefined()
    expect(merged.state.vehicles?.[0].wait_time).toBeUndefined()
    expect(renderFrameFromSimulation(simulationFor(fixtures[1].state), 0)!.controller_events).toBeUndefined()
    expect(merged.state.time).toBe(3)
  })

  it("uses truthful countdown labels without promising another approach's next green", () => {
    const control = fixtures[0].expected.junction_controls.J0
    expect(timingLabel({ ...control, timing_kind: "fixed_stage", remaining_seconds: 2 })).toBe("Scheduled green remaining: 2.0 s")
    expect(timingLabel({ ...control, timing_kind: "minimum_hold", remaining_seconds: 2 })).toBe("Minimum hold remaining: 2.0 s")
    expect(timingLabel({ ...control, timing_kind: "minimum_hold", remaining_seconds: 0 })).toBe("Minimum hold satisfied")
    expect(timingLabel({ ...control, timing_kind: "clearance", remaining_seconds: 1 })).toBe("Clearance timer: 1.0 s")
    expect(timingLabel({ ...control, mode: "all_way_stop", timing_kind: "none", remaining_seconds: null })).toBe("All-way stop · no timer")
    expect(timingLabel(undefined)).toBe("Timing unavailable")
    expect(timingLabel(fixtures[1].expected.junction_controls.J0)).toBe("Timing unavailable")
  })
})

const hooks = vi.hoisted(() => ({ states: [] as unknown[], effect: null as null | (() => void | (() => void)) }))
vi.mock("react", () => ({
  useState: (initial: unknown) => {
    const index = hooks.states.length
    hooks.states.push(initial)
    return [initial, (next: unknown) => { hooks.states[index] = next }]
  },
  useRef: (initial: unknown) => ({ current: initial }),
  useEffect: (effect: () => void | (() => void)) => { hooks.effect = effect },
}))

type Listener = (event: { data?: string; code?: number }) => void
class SocketFixture {
  static CLOSED = 3
  static instances: SocketFixture[] = []
  readyState = 1
  listeners = new Map<string, Listener>()
  constructor() { SocketFixture.instances.push(this) }
  addEventListener(name: string, listener: Listener) { this.listeners.set(name, listener) }
  close() { this.readyState = SocketFixture.CLOSED }
  emit(name: string, event: { data?: string; code?: number } = {}) { this.listeners.get(name)?.(event) }
}

describe("stream budget failure lifecycle", () => {
  let cleanup: void | (() => void)
  const timeout = vi.fn(() => 1)
  beforeEach(() => {
    hooks.states = []
    hooks.effect = null
    SocketFixture.instances = []
    timeout.mockClear()
    vi.stubGlobal("WebSocket", SocketFixture)
    vi.stubGlobal("window", { setTimeout: timeout, clearTimeout: vi.fn() })
    useSimulationSocket({ enabled: true })
    cleanup = hooks.effect!()
  })
  afterEach(() => { cleanup?.(); vi.unstubAllGlobals() })

  it("keeps the server's explicit error after close1009, clearing the old frame for HTTP fallback", () => {
    const socket = SocketFixture.instances[0]
    socket.emit("open")
    socket.emit("message", { data: JSON.stringify(fixtures[0].expected) })
    expect(hooks.states[1]).toEqual(fixtures[0].expected)
    const message = "Render metadata exceeds 262144 bytes; authoritative telemetry was preserved."
    socket.emit("message", { data: JSON.stringify({ type: "stream_error", code: "render_metadata_budget", message }) })
    socket.emit("close", { code: 1009 })
    expect(hooks.states[0]).toBe("error")
    expect(hooks.states[1]).toBeNull()
    expect(hooks.states[2]).toBe(message)
    expect(hooks.states[4]).toBeNull()
    expect(timeout).not.toHaveBeenCalled()
    expect(SocketFixture.instances).toHaveLength(1)
  })

  it("does not reconnect a1009 close that arrived without its preceding error frame", () => {
    SocketFixture.instances[0].emit("close", { code: 1009 })
    expect(hooks.states[0]).toBe("error")
    expect(hooks.states[1]).toBeNull()
    expect(hooks.states[2]).toContain("budget")
    expect(timeout).not.toHaveBeenCalled()
  })

  it("retains permission-denial semantics and never retries1008", () => {
    SocketFixture.instances[0].emit("close", { code: 1008 })
    expect(hooks.states[2]).toBe("Simulation stream permission expired. Sign in again to continue streaming.")
    expect(timeout).not.toHaveBeenCalled()
  })

  it("still reconnects ordinary transient failures", () => {
    SocketFixture.instances[0].emit("close", { code: 1006 })
    expect(hooks.states[0]).toBe("reconnecting")
    expect(hooks.states[3]).toBe(1)
    expect(timeout).toHaveBeenCalledOnce()
  })
})

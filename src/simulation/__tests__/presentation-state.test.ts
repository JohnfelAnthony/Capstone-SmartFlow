import { describe, expect, it } from "vitest"
import { bentNetwork } from "./geometry-fixture"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"
import { createPresentationState, presentationReducer } from "@/simulation/presentation-state"

const geometry = normalizeSceneGeometry(bentNetwork)

describe("shared presentation navigation lifecycle", () => {
  it("starts at the configured junction and ordinary-laptop quality with the intended overlays", () => {
    const state = createPresentationState(geometry, "J1")
    expect(state.focus).toBe("junction")
    expect(state.junctionId).toBe("J1")
    expect(state.quality).toBe("laptop")
    expect(state.overlays).toEqual({ signals: true, labels: true, queues: true, heatmap: false, arrows: false, connectors: false, context: true })
  })

  it("uses the first valid junction when a configured junction is absent", () => {
    expect(createPresentationState(geometry, "missing").junctionId).toBe("J1")
  })

  it("does not permit follow without a selected vehicle", () => {
    const state = createPresentationState(geometry, "J1")
    expect(presentationReducer(state, { type: "focus", focus: "follow" }).focus).toBe("junction")
    const selected = presentationReducer(state, { type: "select", selection: { kind: "vehicle", id: "v1" } })
    expect(presentationReducer(selected, { type: "focus", focus: "follow" }).focus).toBe("follow")
  })

  it("returns to junction focus and announces a followed vehicle departure", () => {
    let state = createPresentationState(geometry, "J1")
    state = presentationReducer(state, { type: "select", selection: { kind: "vehicle", id: "v1" } })
    state = presentationReducer(state, { type: "focus", focus: "follow" })
    state = presentationReducer(state, { type: "entities", vehicleIds: [], pedestrianIds: [] })
    expect(state.selection).toBe(null)
    expect(state.focus).toBe("junction")
    expect(state.notice).toContain("left")
  })

  it("preserves static selection, quality, and toggles across entity updates and view changes", () => {
    let state = createPresentationState(geometry, "J1")
    state = presentationReducer(state, { type: "select", selection: { kind: "lane", id: "lane-west" } })
    state = presentationReducer(state, { type: "quality", quality: "enhanced" })
    state = presentationReducer(state, { type: "overlay", overlay: "heatmap", enabled: true })
    state = presentationReducer(state, { type: "entities", vehicleIds: [], pedestrianIds: [] })
    expect(state.selection).toEqual({ kind: "lane", id: "lane-west" })
    expect(state.quality).toBe("enhanced")
    expect(state.overlays.heatmap).toBe(true)
    // View mode is intentionally owned by the host; toggling it does not reset shared state.
  })

  it("clears stale dynamic details on stop/reset while keeping navigation preferences", () => {
    let state = createPresentationState(geometry, "J1")
    state = presentationReducer(state, { type: "select", selection: { kind: "pedestrian", id: "p1" } })
    state = presentationReducer(state, { type: "quality", quality: "enhanced" })
    const reset = presentationReducer(state, { type: "reset", junctionId: "J1" })
    expect(reset.selection).toBe(null)
    expect(reset.focus).toBe("junction")
    expect(reset.quality).toBe("enhanced")
    expect(reset.revision).toBe(state.revision + 1)
  })

  it("clears incompatible network selection and keeps presentation preferences", () => {
    let state = createPresentationState(geometry, "J1")
    state = presentationReducer(state, { type: "select", selection: { kind: "vehicle", id: "v1" } })
    state = presentationReducer(state, { type: "network", geometry: { ...geometry, networkId: "new-network" }, controlledJunction: "J1" })
    expect(state.selection).toBe(null)
    expect(state.networkId).toBe("new-network")
    expect(state.revision).toBe(1)
  })

  it("provides an explicit discontinuity revision for replay seeks", () => {
    const state = createPresentationState(geometry, "J1")
    const seek = presentationReducer(state, { type: "seek" })
    expect(seek.revision).toBe(state.revision + 1)
    expect(seek.junctionId).toBe(state.junctionId)
    expect(seek.overlays).toBe(state.overlays)
  })

  it("keeps the selected static object and network focus through a replay seek", () => {
    let state = createPresentationState(geometry, "J1")
    state = presentationReducer(state, { type: "select", selection: { kind: "lane", id: "lane-west" } })
    state = presentationReducer(state, { type: "focus", focus: "network" })
    const seek = presentationReducer(state, { type: "seek" })
    expect(seek.selection).toEqual({ kind: "lane", id: "lane-west" })
    expect(seek.focus).toBe("network")
    expect(seek.revision).toBe(state.revision + 1)
  })

  it("does not declare a hidden selected vehicle departed while its own display coverage is limited", () => {
    let state = createPresentationState(geometry, "J1")
    state = presentationReducer(state, { type: "select", selection: { kind: "vehicle", id: "hidden-v" } })
    state = presentationReducer(state, { type: "focus", focus: "follow" })
    const limited = presentationReducer(state, { type: "entities", vehicleIds: ["another-v"], pedestrianIds: [], coverageLimited: true })
    expect(limited.selection).toEqual(state.selection)
    expect(limited.focus).toBe("follow")
    expect(limited.notice).toBe(null)
  })

  it("clears a departed followed vehicle when vehicle coverage is complete even if another population is limited", () => {
    let state = createPresentationState(geometry, "J1")
    state = presentationReducer(state, { type: "select", selection: { kind: "vehicle", id: "departed-v" } })
    state = presentationReducer(state, { type: "focus", focus: "follow" })
    // Host passes the selected population's coverage, not the frame's overall limited flag.
    const completeVehicleCoverage = presentationReducer(state, { type: "entities", vehicleIds: [], pedestrianIds: ["shown-p"], coverageLimited: false })
    expect(completeVehicleCoverage.selection).toBe(null)
    expect(completeVehicleCoverage.focus).toBe("junction")
    expect(completeVehicleCoverage.notice).toContain("left")
  })
})


import type { SceneGeometry, Selection } from "@/simulation/scene-geometry"

export type MapFocus = "junction" | "network" | "follow"
export type OverlaySettings = {
  signals: boolean
  labels: boolean
  queues: boolean
  heatmap: boolean
  arrows: boolean
  connectors: boolean
  context: boolean
}
export type PresentationState = {
  networkId: string
  selection: Selection | null
  focus: MapFocus
  junctionId: string | null
  overlays: OverlaySettings
  notice: string | null
  /** Incremented on jumps/reset so renderers discard interpolation history. */
  revision: number
}

export const DEFAULT_OVERLAYS: OverlaySettings = {
  signals: true, labels: true, queues: true, heatmap: true, arrows: false, connectors: false, context: true,
}

function initialJunction(geometry: SceneGeometry, controlledJunction?: string | null) {
  return controlledJunction && geometry.junctionById.has(controlledJunction) ? controlledJunction : geometry.junctions[0]?.id ?? null
}

export function createPresentationState(geometry: SceneGeometry, controlledJunction?: string | null): PresentationState {
  const junctionId = initialJunction(geometry, controlledJunction)
  return { networkId: geometry.networkId, selection: null, focus: junctionId ? "junction" : "network", junctionId, overlays: { ...DEFAULT_OVERLAYS }, notice: null, revision: 0 }
}

export type PresentationAction =
  | { type: "select"; selection: Selection | null }
  | { type: "focus"; focus: MapFocus; junctionId?: string | null }
  | { type: "overlay"; overlay: keyof OverlaySettings; enabled: boolean }
  | { type: "network"; geometry: SceneGeometry; controlledJunction?: string | null }
  | { type: "entities"; vehicleIds: readonly string[]; pedestrianIds: readonly string[]; coverageLimited?: boolean }
  | { type: "reset"; junctionId?: string | null }
  | { type: "seek" }
  | { type: "clear-notice" }

/** Selection/navigation is presentation-only and never issues an engine command. */
export function presentationReducer(state: PresentationState, action: PresentationAction): PresentationState {
  switch (action.type) {
    case "select": {
      const selectedVehicle = action.selection?.kind === "vehicle"
      return { ...state, selection: action.selection, focus: state.focus === "follow" && !selectedVehicle ? (state.junctionId ? "junction" : "network") : state.focus, notice: null }
    }
    case "focus": {
      if (action.focus === "follow" && state.selection?.kind !== "vehicle") return state
      const junctionId = action.junctionId ?? state.junctionId
      return { ...state, focus: action.focus === "junction" && !junctionId ? "network" : action.focus, junctionId, notice: null }
    }
    case "overlay": return { ...state, overlays: { ...state.overlays, [action.overlay]: action.enabled } }
    case "network": {
      if (state.networkId === action.geometry.networkId) return state
      const next = createPresentationState(action.geometry, action.controlledJunction)
      const staticSelection = state.selection?.kind === "junction" && action.geometry.junctionById.has(state.selection.id) || state.selection?.kind === "lane" && action.geometry.laneById.has(state.selection.id)
      return { ...next, selection: staticSelection ? state.selection : null, overlays: state.overlays, revision: state.revision + 1 }
    }
    case "entities": {
      if (!state.selection || state.selection.kind === "junction" || state.selection.kind === "lane") return state
      const ids = state.selection.kind === "vehicle" ? action.vehicleIds : action.pedestrianIds
      if (ids.includes(state.selection.id) || action.coverageLimited) return state
      const followed = state.focus === "follow"
      return { ...state, selection: null, focus: followed ? (state.junctionId ? "junction" : "network") : state.focus, notice: followed ? "The selected vehicle left the simulation. Returned to junction focus." : "The selected entity left the simulation." }
    }
    case "reset": {
      const junctionId = action.junctionId ?? state.junctionId
      return { ...state, selection: null, focus: junctionId ? "junction" : "network", junctionId, notice: null, revision: state.revision + 1 }
    }
    case "seek": return { ...state, revision: state.revision + 1, notice: null }
    case "clear-notice": return { ...state, notice: null }
  }
}

import { useEffect, useMemo, useReducer, useRef } from "react"
import { ApiError, SESSION_RESTORED_EVENT } from "@/api/client"
import { getRouteContext, previewRoute, type ClosureOverride, type ClosureResponse, type RouteContext, type RoutePreview, type RoutePreviewRequest, type RouteSource, type RouteVehicleClass } from "@/api/routes"
import type { VisualNetwork } from "@/api/visual-network"
import { chooseResponse } from "@/lib/closures"

type PlannerError = { status?: number; message: string }
const NETWORK_CHANGED: PlannerError = { status: 409, message: "The base network changed. Reload the Route Planner context." }

export type RoutePlannerState = {
  source: RouteSource | null
  vehicleType: RouteVehicleClass
  context: RouteContext | null
  contextGeneration: number
  contextStatus: "idle" | "loading" | "ready" | "error"
  contextError: PlannerError | null
  entryId: string
  destinationId: string
  savedClosures: ClosureOverride | undefined
  override: ClosureOverride | undefined
  coordinationNotice: string
  preview: RoutePreview | null
  previewGeneration: number
  previewPending: boolean
  previewError: PlannerError | null
}

type Action =
  | { type: "source"; source: RouteSource | null }
  | { type: "class"; vehicleType: RouteVehicleClass }
  | { type: "reload" }
  | { type: "session-restored" }
  | { type: "context-ready"; generation: number; context: RouteContext }
  | { type: "context-error"; generation: number; error: PlannerError }
  | { type: "entry"; entryId: string }
  | { type: "destination"; destinationId: string }
  | { type: "toggle"; laneId: string }
  | { type: "response"; laneId: string; response: ClosureResponse }
  | { type: "reset" | "clear" }
  | { type: "preview-ready"; generation: number; preview: RoutePreview }
  | { type: "preview-error"; generation: number; error: PlannerError }

export const initialRoutePlannerState: RoutePlannerState = {
  source: null, vehicleType: "car", context: null, contextGeneration: 0, contextStatus: "idle",
  contextError: null, entryId: "", destinationId: "", savedClosures: undefined, override: undefined, coordinationNotice: "",
  preview: null, previewGeneration: 0, previewPending: false, previewError: null,
}

export function activeClosures({ context, savedClosures, override }: Pick<RoutePlannerState, "context" | "savedClosures" | "override">) {
  return override ?? savedClosures ?? context?.initial_closures
}

type PreviewInput = Pick<RoutePlannerState, "source" | "vehicleType" | "context" | "contextStatus" | "entryId" | "destinationId" | "override">

export function makePreviewRequest({ source, vehicleType, context, contextStatus, entryId, destinationId, override }: PreviewInput): RoutePreviewRequest | null {
  if (!source || contextStatus !== "ready" || !context?.eligible_pairs.some(pair => pair.entry_id === entryId && pair.destination_id === destinationId)) {
    return null
  }
  return {
    source, vehicle_type: vehicleType, expected_network_sha256: context.network_sha256,
    entry_id: entryId, destination_id: destinationId, ...(override === undefined ? {} : { closure_override: override }),
  }
}

function changePreview(state: RoutePlannerState, changes: Partial<RoutePlannerState>): RoutePlannerState {
  const next = { ...state, ...changes }
  return { ...next, preview: null, previewError: null, previewGeneration: state.previewGeneration + 1,
    previewPending: makePreviewRequest(next) !== null }
}

function changeContext(state: RoutePlannerState, source: RouteSource | null, vehicleType: RouteVehicleClass, preserveTrip: boolean) {
  return changePreview(state, {
    source, vehicleType, contextGeneration: state.contextGeneration + 1, contextStatus: source ? "loading" : "idle",
    contextError: null,
    ...(preserveTrip ? {} : { context: null, entryId: "", destinationId: "", savedClosures: undefined, override: undefined, coordinationNotice: "" }),
  })
}

export function routePlannerReducer(state: RoutePlannerState, action: Action): RoutePlannerState {
  switch (action.type) {
    case "source":
      return changeContext(state, action.source, state.vehicleType, false)
    case "class":
      return state.vehicleType === action.vehicleType ? state : changeContext(state, state.source, action.vehicleType, true)
    case "reload":
      return changeContext(state, state.source, state.vehicleType, false)
    case "session-restored":
      if (state.contextError?.status === 401) return changeContext(state, state.source, state.vehicleType, true)
      if (state.previewError?.status === 401) return changePreview(state, {})
      return state
    case "context-ready": {
      if (action.generation !== state.contextGeneration) return state
      const { context } = action
      if (state.context && state.context.network_sha256 !== context.network_sha256) {
        return { ...state, contextStatus: "error", contextError: NETWORK_CHANGED }
      }
      const first = context.eligible_pairs[0]
      const entryId = state.context
        ? context.entries.some(entry => entry.id === state.entryId) ? state.entryId : ""
        : first?.entry_id ?? ""
      const candidate = state.context ? state.destinationId : first?.destination_id
      const destinationId = context.eligible_pairs.some(pair => pair.entry_id === entryId && pair.destination_id === candidate) ? candidate ?? "" : ""
      return changePreview(state, { context, contextStatus: "ready", entryId, destinationId, savedClosures: undefined })
    }
    case "context-error":
      return action.generation === state.contextGeneration ? { ...state, contextStatus: "error", contextError: action.error } : state
    case "entry": {
      const pairs = state.context?.eligible_pairs.filter(pair => pair.entry_id === action.entryId) ?? []
      const destinationId = pairs.some(pair => pair.destination_id === state.destinationId) ? state.destinationId : pairs[0]?.destination_id ?? ""
      return changePreview(state, { entryId: action.entryId, destinationId })
    }
    case "destination":
      return changePreview(state, { destinationId: action.destinationId })
    case "toggle": {
      const current = activeClosures(state)
      if (state.contextStatus !== "ready" || !current || !state.context?.roads.some(road => road.lane_id === action.laneId)) return state
      const lanes = new Set(current.closed_lanes)
      const responses = { ...current.closure_responses }
      if (lanes.delete(action.laneId)) {
        delete responses[action.laneId]
      } else {
        lanes.add(action.laneId)
      }
      return changePreview(state, { override: { closed_lanes: [...lanes].sort(), closure_responses: responses }, coordinationNotice: "" })
    }
    case "response": {
      const current = activeClosures(state)
      if (state.contextStatus !== "ready" || !current?.closed_lanes.includes(action.laneId)) return state
      const responses = chooseResponse(current, action.laneId, action.response).closure_responses as ClosureOverride["closure_responses"]
      const coordinated = Object.entries(responses).filter(([lane, choice]) => lane !== action.laneId && choice !== current.closure_responses[lane])
      return changePreview(state, {
        override: { ...current, closure_responses: responses },
        coordinationNotice: coordinated.length ? `Updated ${coordinated.length} other side-street response(s) to match the network-wide setting.` : "",
      })
    }
    case "reset":
      return state.override === undefined ? state : changePreview(state, { override: undefined, coordinationNotice: "" })
    case "clear":
      return changePreview(state, { override: { closed_lanes: [], closure_responses: {} }, coordinationNotice: "" })
    case "preview-ready":
      if (action.generation !== state.previewGeneration) return state
      if (action.preview.network_sha256 !== state.context?.network_sha256) {
        return { ...state, preview: null, previewPending: false,
          previewError: NETWORK_CHANGED }
      }
      return { ...state, preview: action.preview, previewPending: false, previewError: null,
        savedClosures: state.source?.kind === "scenario" && state.override === undefined
          ? action.preview.effective_closures : state.savedClosures }
    case "preview-error":
      return action.generation === state.previewGeneration ? { ...state, previewPending: false, previewError: action.error } : state
  }
}

function plannerError(error: unknown): PlannerError {
  if (error instanceof ApiError) return { status: error.status, message: error.message }
  return { message: error instanceof Error ? error.message : "Could not load the route preview." }
}

export function useRoutePlanner() {
  const [state, dispatch] = useReducer(routePlannerReducer, initialRoutePlannerState)
  const geometryByFingerprint = useRef(new Map<string, VisualNetwork>())
  const { source, vehicleType, contextGeneration, context, contextStatus, entryId, destinationId, override, previewGeneration } = state

  useEffect(() => {
    const restore = () => dispatch({ type: "session-restored" })
    window.addEventListener(SESSION_RESTORED_EVENT, restore)
    return () => window.removeEventListener(SESSION_RESTORED_EVENT, restore)
  }, [])

  useEffect(() => {
    if (!source) return
    const controller = new AbortController()
    void getRouteContext({ source, vehicle_type: vehicleType }, controller.signal).then(context => {
      if (controller.signal.aborted) return
      const geometry = geometryByFingerprint.current.get(context.network_sha256) ?? context.geometry
      geometryByFingerprint.current.set(context.network_sha256, geometry)
      dispatch({ type: "context-ready", generation: contextGeneration, context: { ...context, geometry } })
    }).catch(error => {
      if (!controller.signal.aborted) dispatch({ type: "context-error", generation: contextGeneration, error: plannerError(error) })
    })
    return () => controller.abort()
  }, [source, vehicleType, contextGeneration])

  const request = useMemo(() => makePreviewRequest({ source, vehicleType, context, contextStatus, entryId, destinationId, override }),
    [source, vehicleType, context, contextStatus, entryId, destinationId, override])

  useEffect(() => {
    if (!request) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      void previewRoute(request, controller.signal).then(preview => {
        if (!controller.signal.aborted) dispatch({ type: "preview-ready", generation: previewGeneration, preview })
      }).catch(error => {
        if (!controller.signal.aborted) dispatch({ type: "preview-error", generation: previewGeneration, error: plannerError(error) })
      })
    }, 200)
    return () => { clearTimeout(timer); controller.abort() }
  }, [request, previewGeneration])

  return { state, dispatch }
}

export type RenderVehicle = {
  id: string
  x: number
  y: number
  angle: number
  speed: number
  lane_id: string
  lane_position: number
  length: number
  width: number
  stopped: boolean
  visual_type: string
  emergency: boolean
  wait_time?: number
}

export type RenderPedestrian = {
  id: string
  x: number
  y: number
  speed: number
  lane_id: string
  stopped: boolean
  wait_time?: number
}

export type LaneMetrics = { vehicles: number; queue: number; mean_speed_mps: number; density_vehicles_per_km: number; exits: number; closed: boolean; speed_factor: number }
export type JunctionMetrics = { queue: number; vehicle_passages: number; waiting_pedestrians: number }
export type JunctionControl = {
  mode: string; controller: string; selected_for_rl: boolean; phase: string
  stage?: string; elapsed_seconds?: number; remaining_seconds?: number | null
  timing_kind?: "fixed_stage" | "minimum_hold" | "clearance" | "none"
  pending_service?: string | null; external_control?: boolean
}
export type ControllerEvent = { time?: number; junction_id?: string; action?: number | string; service?: string; applied?: boolean; result?: string; reason?: string; [key: string]: unknown }
export type ControllerEvents = { last_policy_decision: ControllerEvent | null; last_safety_override: ControllerEvent | null }
export type PedestrianPath = { id: string; junction_id: string; shape: Array<{ x: number; y: number }>; provenance: "illustrative" }
export type RenderCoverage = { vehicles: { total: number; shown: number }; pedestrians: { total: number; shown: number }; limited: boolean; reason: "entity_limit" | "byte_limit" | null }

export type RenderFrame = {
  sequence?: number
  time: number
  render_ts: number
  step_length: number
  status: string
  flow_state: string
  intersection_id: string
  phase: string
  ns_state: string
  ew_state: string
  render_mode: "idle" | "live" | "playback" | string
  vehicle_count: number
  pedestrian_count: number
  render_limits?: { vehicles: number; pedestrians: number }
  render_coverage?: RenderCoverage
  lane_metrics?: Record<string, LaneMetrics>
  junction_metrics?: Record<string, JunctionMetrics>
  controller_events?: ControllerEvents
  playback: {
    active: boolean
    frame_index: number
    frame_count: number
  }
  vehicles: RenderVehicle[]
  pedestrians: RenderPedestrian[]
  visual: {
    closed_lanes: string[]
    slow_lanes: Record<string, number>
    pedestrian_paths?: PedestrianPath[]
    constraint_marker?: {
      active: boolean
      x: number
      y: number
    }
  }
  junction_controls: Record<string, JunctionControl>
  traffic_lights: Record<string, { state: string; phase: string }>
}

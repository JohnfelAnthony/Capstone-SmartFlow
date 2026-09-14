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
}

export type RenderPedestrian = {
  id: string
  x: number
  y: number
  speed: number
  lane_id: string
  stopped: boolean
}

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
  playback: {
    active: boolean
    frame_index: number
    frame_count: number
  }
  vehicles: RenderVehicle[]
  pedestrians: RenderPedestrian[]
  visual: {
    constraint_marker?: {
      active: boolean
      x: number
      y: number
    }
  }
  traffic_lights: Record<string, { state: string; phase: string }>
}

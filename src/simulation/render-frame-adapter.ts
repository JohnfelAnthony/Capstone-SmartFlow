import type { SimulationStatePayload } from "@/api/simulation"
import type { RenderFrame, RenderVehicle, RenderPedestrian } from "@/simulation/frame-types"

export const DISPLAY_LIMITS = { vehicles: 300, pedestrians: 128 }
const text = (value: unknown, fallback = "", size = 48) => String(value ?? "").trim().slice(0, size) || fallback
const numeric = (value: unknown, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback

/** Same stable lane round-robin allocation as the Python serializer. */
export function distributeEntities<T extends { id: string; lane_id: string }>(entities: T[], limit: number): T[] {
  const groups = new Map<string, T[]>()
  for (const entity of entities) {
    const key = entity.lane_id || ""
    const group = groups.get(key) ?? []
    group.push(entity); groups.set(key, group)
  }
  const ordered = [...groups.keys()].sort().map(key => groups.get(key)!.sort((a,b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
  const result: T[] = []
  for (let offset = 0; result.length < limit; offset++) {
    let added = false
    for (const group of ordered) if (group[offset]) {
      result.push(group[offset]); added = true
      if (result.length === limit) return result
    }
    if (!added) break
  }
  return result
}

function vehicle(raw: RenderVehicle): RenderVehicle {
  return { id:text(raw.id,"vehicle"), x:numeric(raw.x), y:numeric(raw.y), angle:numeric(raw.angle), speed:numeric(raw.speed), lane_id:text(raw.lane_id), lane_position:numeric(raw.lane_position), length:numeric(raw.length,4.5), width:numeric(raw.width,1.8), stopped:Boolean(raw.stopped), visual_type:text(raw.visual_type,"car"), ...(raw.wait_time === undefined ? {} : {wait_time:numeric(raw.wait_time)}) }
}
function pedestrian(raw: RenderPedestrian): RenderPedestrian {
  return { id:text(raw.id,"pedestrian"), x:numeric(raw.x), y:numeric(raw.y), speed:numeric(raw.speed), lane_id:text(raw.lane_id), stopped:Boolean(raw.stopped), ...(raw.wait_time === undefined ? {} : {wait_time:numeric(raw.wait_time)}) }
}

export function enforcePresentationBudget(frame: RenderFrame): RenderFrame {
  const coverage = (reason: "entity_limit" | "byte_limit") => {
    const limited = frame.vehicles.length < frame.vehicle_count || frame.pedestrians.length < frame.pedestrian_count
    frame.render_coverage = { vehicles:{total:frame.vehicle_count,shown:frame.vehicles.length}, pedestrians:{total:frame.pedestrian_count,shown:frame.pedestrians.length}, limited, reason:limited ? reason : null }
  }
  const bytes = () => new TextEncoder().encode(JSON.stringify(frame)).length
  coverage("entity_limit")
  if (bytes() <= 262144) return frame
  const vehicles = frame.vehicles, pedestrians = frame.pedestrians
  frame.vehicles=[]; frame.pedestrians=[]; coverage("byte_limit")
  if (bytes() > 262144) throw new Error("Render metadata exceeds 262,144 bytes. Research telemetry could not be displayed.")
  const total = vehicles.length + pedestrians.length
  let low=0, high=total
  while (low < high) {
    const candidate=Math.ceil((low+high)/2), count=Math.floor(candidate*vehicles.length/total)
    frame.vehicles=vehicles.slice(0,count); frame.pedestrians=pedestrians.slice(0,candidate-count); coverage("byte_limit")
    if (bytes() <= 262144) low=candidate; else high=candidate-1
  }
  const count=total ? Math.floor(low*vehicles.length/total) : 0
  frame.vehicles=vehicles.slice(0,count); frame.pedestrians=pedestrians.slice(0,low-count); coverage("byte_limit")
  return frame
}

export function renderFrameFromSimulation(simulation: SimulationStatePayload | null, renderTs = Date.now()/1000): RenderFrame | null {
  if (!simulation) return null
  if (simulation.render_frame_error) throw new Error(simulation.render_frame_error)
  if (simulation.render_frame) return simulation.render_frame
  const state=simulation.state, status=state.status ?? simulation.status
  const phase=status === "stopped" ? "ALL_RED" : String(state.phase ?? "ALL_RED")
  const color=phase.endsWith("_GREEN") ? "green" : phase.endsWith("_YELLOW") ? "yellow" : "red"
  const north=/^(NORTH|SOUTH|NS)_/.test(phase), east=/^(EAST|WEST|EW)_/.test(phase)
  const flow=String(state.flow?.state ?? "IDLE")
  const lights=Object.fromEntries(Object.entries(state.traffic_lights ?? {}).filter(([,light]) => light.state).map(([id,light])=>[text(id,"",16),{state:text(light.state,"",64),phase:text(light.phase,"ALL_RED",32)}]))
  return enforcePresentationBudget({
    time:numeric(state.time), render_ts:renderTs, step_length:numeric(state.step_length,.1), status, flow_state:flow,
    intersection_id:text(state.scenario?.intersection_id ?? state.scenario?.network_id,"tagum_network",24), phase, ns_state:north ? color : "red", ew_state:east ? color : "red",
    render_mode:flow === "LIVE_RUNNING" ? "live" : state.playback ? "playback" : "idle",
    vehicle_count:numeric(state.vehicle_count,state.vehicles?.length ?? 0), pedestrian_count:numeric(state.pedestrian_count,state.pedestrians?.length ?? 0),
    render_limits:{...DISPLAY_LIMITS}, playback:{active:Boolean(state.playback),frame_index:numeric(state.playback?.frame_index),frame_count:numeric(state.playback?.frame_count)},
    vehicles:distributeEntities(state.vehicles ?? [],300).map(vehicle), pedestrians:distributeEntities(state.pedestrians ?? [],128).map(pedestrian),
    visual:{closed_lanes:state.visual?.closed_lanes ?? [],slow_lanes:state.visual?.slow_lanes ?? {},constraint_marker:{active:Boolean(state.visual?.constraint_marker?.active),x:numeric(state.visual?.constraint_marker?.x),y:numeric(state.visual?.constraint_marker?.y)},...(state.visual?.pedestrian_paths ? {pedestrian_paths:state.visual.pedestrian_paths} : {})},
    junction_controls:state.junction_controls ?? {}, traffic_lights:lights,
    ...(state.metrics?.lanes ? {lane_metrics:state.metrics.lanes} : {}), ...(state.metrics?.junctions ? {junction_metrics:state.metrics.junctions} : {}),
    ...(state.experiment && ("last_policy_decision" in state.experiment || "last_safety_override" in state.experiment) ? {controller_events:{last_policy_decision:state.experiment.last_policy_decision ?? null,last_safety_override:state.experiment.last_safety_override ?? null}} : {}),
  })
}

/** Optional telemetry must be replaced, including absence in older replay frames. */
export function mergeRenderFrame(simulation: SimulationStatePayload | null, frame: RenderFrame): SimulationStatePayload | null {
  if (!simulation) return null
  return { ...simulation, render_frame:frame, render_frame_error:null, status:frame.status, state:{ ...simulation.state, time:frame.time, step_length:frame.step_length, status:frame.status, phase:frame.phase,
    traffic_lights:frame.traffic_lights, vehicles:frame.vehicles, pedestrians:frame.pedestrians, visual:frame.visual, junction_controls:frame.junction_controls,
    vehicle_count:frame.vehicle_count, pedestrian_count:frame.pedestrian_count, render_coverage:frame.render_coverage,
    metrics:{...simulation.state.metrics,lanes:frame.lane_metrics,junctions:frame.junction_metrics},
    experiment:{...simulation.state.experiment,last_policy_decision:frame.controller_events?.last_policy_decision ?? null,last_safety_override:frame.controller_events?.last_safety_override ?? null},
    scenario:{...simulation.state.scenario,intersection_id:frame.intersection_id},
    flow:{...simulation.state.flow,state:frame.flow_state,live_indicator_label:frame.flow_state === "LIVE_RUNNING" ? "LIVE" : frame.flow_state},
  }}
}

export function timingLabel(control: RenderFrame["junction_controls"][string] | undefined): string {
  if (!control?.timing_kind || control.timing_kind === "none" || control.remaining_seconds == null) return control?.mode === "all_way_stop" ? "All-way stop · no timer" : "Timing unavailable"
  if (control.timing_kind === "minimum_hold" && control.remaining_seconds <= 0) return "Minimum hold satisfied"
  const label={fixed_stage:"Scheduled green remaining",minimum_hold:"Minimum hold remaining",clearance:"Clearance timer"}[control.timing_kind]
  return `${label}: ${control.remaining_seconds.toFixed(1)} s`
}

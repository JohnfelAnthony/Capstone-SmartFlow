import type { RenderFrame, RenderVehicle } from "@/simulation/frame-types"

export function isPresentationJump(previous: RenderFrame | null, next: RenderFrame, previousRun: string, nextRun: string) {
  return !previous || previousRun !== nextRun || previous.intersection_id !== next.intersection_id ||
    previous.render_mode !== next.render_mode || next.time < previous.time ||
    previous.status !== "running" || next.status !== "running" ||
    (next.playback.active && (next.playback.seek_revision ?? 0) !== (previous.playback.seek_revision ?? 0))
}

/** Interpolation stops at authoritative target; it never extrapolates. */
export function interpolateVehicle(previous: RenderVehicle, target: RenderVehicle, elapsed: number, duration: number): RenderVehicle {
  const amount=Math.max(0,Math.min(1,elapsed/duration))
  const delta=((target.angle-previous.angle+540)%360)-180
  return {...target,x:previous.x+(target.x-previous.x)*amount,y:previous.y+(target.y-previous.y)*amount,angle:previous.angle+delta*amount}
}

import type { VisualPoint } from "@/api/visual-network"
import type { RenderFrame, RenderPedestrian, RenderVehicle } from "@/simulation/frame-types"
import { interpolationDuration, interpolateVehicle, isPresentationJump } from "@/simulation/entity-interpolation"
import type { SceneBounds } from "@/simulation/scene-geometry"

export type MapCamera = { scale: number; ox: number; oy: number; width: number; height: number }
export type LabelRect = { x: number; y: number; width: number; height: number }

export function fitMap(bounds: SceneBounds, width: number, height: number): MapCamera {
  const scale = Math.min(width / Math.max(1, bounds.max_x - bounds.min_x), height / Math.max(1, bounds.max_y - bounds.min_y)) * .82
  return { scale, ox: width / 2 - (bounds.min_x + bounds.max_x) / 2 * scale, oy: height / 2 + (bounds.min_y + bounds.max_y) / 2 * scale, width, height }
}
export function mapToScreen(point: VisualPoint, camera: MapCamera): VisualPoint {
  return { x: point.x * camera.scale + camera.ox, y: -point.y * camera.scale + camera.oy }
}
export function screenToMap(point: VisualPoint, camera: MapCamera): VisualPoint {
  return { x: (point.x - camera.ox) / camera.scale, y: (camera.oy - point.y) / camera.scale }
}
/** Zoom keeps the world point below the cursor stationary, including at either limit. */
export function zoomMapAt(camera: MapCamera, point: VisualPoint, factor: number, minimum: number, maximum = 28): MapCamera {
  const scale = Math.max(minimum, Math.min(maximum, camera.scale * factor)), ratio = scale / camera.scale
  return { ...camera, scale, ox: point.x - (point.x - camera.ox) * ratio, oy: point.y - (point.y - camera.oy) * ratio }
}
export function boundMapPan(camera: MapCamera, bounds: SceneBounds, margin = 70): MapCamera {
  const center = screenToMap({ x: camera.width / 2, y: camera.height / 2 }, camera)
  const x = Math.max(bounds.min_x - margin, Math.min(bounds.max_x + margin, center.x))
  const y = Math.max(bounds.min_y - margin, Math.min(bounds.max_y + margin, center.y))
  return { ...camera, ox: camera.width / 2 - x * camera.scale, oy: camera.height / 2 + y * camera.scale }
}
export function resizeMap(camera: MapCamera, width: number, height: number): MapCamera {
  return { ...camera, width, height, ox: camera.ox + (width - camera.width) / 2, oy: camera.oy + (height - camera.height) / 2 }
}
export function mapScale(scale: number, maximumPixels = 85) {
  const desired = maximumPixels / scale, power = 10 ** Math.floor(Math.log10(desired))
  const metres = [5, 2, 1].map((value) => value * power).find((value) => value <= desired) ?? power / 2
  return { pixels: metres * scale, label: metres >= 1000 ? `${metres / 1000} km` : `${Number(metres.toPrecision(3))} m` }
}
export function claimMapLabel(candidates: LabelRect[], occupied: LabelRect[], width: number, height: number): LabelRect | null {
  const selected = candidates.find((rect) => rect.x >= 8 && rect.y >= 8 && rect.x + rect.width <= width - 8 && rect.y + rect.height <= height - 8 && !occupied.some((other) => rect.x < other.x + other.width + 5 && rect.x + rect.width + 5 > other.x && rect.y < other.y + other.height + 5 && rect.y + rect.height + 5 > other.y))
  if (selected) occupied.push(selected)
  return selected ?? null
}

/** One presentation stream; metadata is always current and motion never extrapolates. */
export function createMapInterpolator() {
  let target: RenderFrame | null = null, displayed: RenderFrame | null = null, previousRun = "", beganAt = 0, duration = 0
  let vehicles = new Map<string, RenderVehicle>(), people = new Map<string, RenderPedestrian>()
  const sample = (now: number): RenderFrame | null => {
    if (!target || duration === 0 || now - beganAt >= duration) { displayed = target; return displayed }
    const elapsed = Math.max(0, now - beganAt), amount = Math.min(1, elapsed / duration)
    displayed = { ...target,
      vehicles: target.vehicles.map((vehicle) => { const previous = vehicles.get(vehicle.id); return previous ? interpolateVehicle(previous, vehicle, elapsed, duration) : vehicle }),
      pedestrians: target.pedestrians.map((person) => { const previous = people.get(person.id); return previous ? { ...person, x: previous.x + (person.x - previous.x) * amount, y: previous.y + (person.y - previous.y) * amount } : person }),
    }
    return displayed
  }
  return {
    set(next: RenderFrame | null, run: string, now: number) {
      if (next === target && run === previousRun) return
      const start = sample(now)
      const snap = !next || isPresentationJump(target, next, previousRun, run)
      vehicles = new Map((start?.vehicles ?? []).map((entity) => [entity.id, entity]))
      people = new Map((start?.pedestrians ?? []).map((entity) => [entity.id, entity]))
      // Compare the displayed pose, so an early duplicate delivery still finishes
      // an in-flight movement. New/departed entities and metrics update immediately.
      const movingVehicles = next?.vehicles.some((entity) => {
        const previous = vehicles.get(entity.id)
        return previous && (previous.x !== entity.x || previous.y !== entity.y || (previous.angle - entity.angle) % 360 !== 0)
      })
      const movingPeople = next?.pedestrians.some((entity) => {
        const previous = people.get(entity.id)
        return previous && (previous.x !== entity.x || previous.y !== entity.y)
      })
      duration = snap || !next || (!movingVehicles && !movingPeople) ? 0 : interpolationDuration(target, next)
      target = next; previousRun = run; beganAt = now
    },
    sample,
    moving(now: number) { return target?.status === "running" && duration > 0 && now - beganAt < duration },
  }
}

import type { VisualPoint } from "@/api/visual-network"
import type { RenderFrame } from "@/simulation/frame-types"
import { interpolateVehicle, isPresentationJump } from "@/simulation/entity-interpolation"
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

type EntityPose = { id: string; x: number; y: number; angle?: number }

function posesChanged(previous: EntityPose[], next: EntityPose[]) {
  if (previous.length !== next.length) return true
  const byId = new Map(previous.map(entity => [entity.id, entity]))
  return next.some(entity => {
    const old = byId.get(entity.id)
    return !old || old.x !== entity.x || old.y !== entity.y ||
      ((old.angle ?? 0) - (entity.angle ?? 0)) % 360 !== 0
  })
}

/** Interpolate buffered snapshots on the configured simulation clock without extrapolating. */
export function createMapInterpolator() {
  let frames: RenderFrame[] = [], previousRun = "", clock = 0, lastNow = 0
  let motionUntil = 0
  const newest = () => frames.length ? frames[frames.length - 1] : null
  const advance = (now: number) => {
    const latest = newest()
    if (!latest) return
    const rate = latest.speed_multiplier ?? 1
    // Mirror ticks_per_frame: at slow speeds the server still sends at least one tick.
    const step = Math.max(1, Math.round(rate)) * latest.step_length
    const elapsed = Math.max(0, Math.min(1, (now - lastNow) / 1000)), behind = latest.time - 2 * step - clock
    lastNow = now
    // Catch up after a long gap without rewinding when the target buffer depth changes.
    if (behind > Math.max(1, 10 * step)) clock = latest.time - 2 * step
    else clock += elapsed * rate * (1 + Math.max(-.1, Math.min(.1, behind / rate)))
    clock = Math.max(frames[0].time, Math.min(latest.time, clock))
  }
  const sample = (now: number): RenderFrame | null => {
    advance(now)
    let index = 0
    while (index + 1 < frames.length && frames[index + 1].time <= clock) index++
    if (index > 0) frames.splice(0, index)
    if (clock >= motionUntil) return newest()
    const from = frames[0], to = frames[1]
    if (!from || !to) return from ?? null
    const amount = (clock - from.time) / (to.time - from.time)
    const vehicles = new Map(from.vehicles.map((entity) => [entity.id, entity])), people = new Map(from.pedestrians.map((entity) => [entity.id, entity]))
    return { ...to,
      vehicles: to.vehicles.map((vehicle) => { const previous = vehicles.get(vehicle.id); return previous ? interpolateVehicle(previous, vehicle, amount, 1) : vehicle }),
      pedestrians: to.pedestrians.map((person) => { const previous = people.get(person.id); return previous ? { ...person, x: previous.x + (person.x - previous.x) * amount, y: previous.y + (person.y - previous.y) * amount } : person }),
    }
  }
  return {
    set(next: RenderFrame | null, run: string, now: number) {
      const latest = newest()
      if (next === latest && run === previousRun) return
      if (!next || !latest || isPresentationJump(latest, next, previousRun, run)) {
        frames = next ? [next] : []
        clock = next?.time ?? 0
        motionUntil = clock
        lastNow = now
        previousRun = run
        return
      }
      advance(now)
      if (next.time > latest.time) {
        if (posesChanged(latest.vehicles, next.vehicles) || posesChanged(latest.pedestrians, next.pedestrians)) {
          motionUntil = next.time
        }
        frames.push(next)
      } else frames[frames.length - 1] = next // same simulation time: newer metadata only
      previousRun = run
    },
    sample,
    moving() { return newest()?.status === "running" && clock < motionUntil },
  }
}

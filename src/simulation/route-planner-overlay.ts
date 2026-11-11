import type { RoutePath } from "@/api/routes"
import type { VisualPoint } from "@/api/visual-network"
import type { SharedRoad } from "@/simulation/frame-types"
import type { EndRole } from "@/lib/route-ends"
import { mapToScreen, screenToMap, type MapCamera } from "@/simulation/map-navigation"
import { boundsOfPoints, distanceToPolyline, lanePolygon, pointInPolygon, type SceneBounds, type SceneGeometry, type SceneLane } from "@/simulation/scene-geometry"

export type PlannerEnd = { key: string; label: string; x: number; y: number; role: EndRole }

export type PlannerOverlay = {
  original: RoutePath | null
  selected: RoutePath | null
  closedLaneIds: readonly string[]
  sharedRoads: readonly SharedRoad[]
  selectedLaneId: string | null
  ends: readonly PlannerEnd[]
}

export type PlannerFitRequest = { revision: number; target: "network" | "routes" }

const sharedLine = (points: Array<[number, number]>) => points.map(([x, y]) => ({ x, y }))
const END_RADIUS = 12
const END_REACH = 18
const palette = { original: "#d1d5db", selected: "#4ade80", amber: "#f9b545", outline: "#7dd3fc" }

export function plannerPathLines(path: RoutePath | null) {
  return path?.segments.map(segment => segment.points) ?? []
}

export function plannerFitBounds(network: SceneBounds, overlay: PlannerOverlay): SceneBounds {
  const points = [
    ...plannerPathLines(overlay.original).flat(),
    ...plannerPathLines(overlay.selected).flat(),
    ...overlay.sharedRoads.flatMap(road => Object.values(road.lanes).flatMap(points => lanePolygon(sharedLine(points), road.width))),
  ]
  if (!points.length) return network
  const { min_x, min_y, max_x, max_y } = boundsOfPoints(points)
  return { min_x: min_x - 12, min_y: min_y - 12, max_x: max_x + 12, max_y: max_y + 12 }
}

export function pickPlannerLane(lanes: readonly SceneLane[], point: VisualPoint, camera: MapCamera, sharedRoads: readonly SharedRoad[] = []) {
  const world = screenToMap(point, camera)
  for (const road of sharedRoads) {
    for (const [laneId, points] of Object.entries(road.lanes)) {
      if (pointInPolygon(world, lanePolygon(sharedLine(points), road.width))) return laneId
    }
  }
  let best: string | null = null
  let closest = Infinity
  const tolerance = Math.min(3, 5 / camera.scale)
  for (const lane of lanes) {
    if (lane.kind !== "road") continue
    const distance = distanceToPolyline(world, lane.centerline)
    if (distance < closest && distance <= lane.width / 2 + tolerance) {
      closest = distance
      best = lane.id
    }
  }
  return best
}

/** The road end under a click or tap, if any. Ends win over the road beneath them. */
export function pickPlannerEnd(ends: readonly PlannerEnd[], point: VisualPoint, camera: MapCamera) {
  let best: PlannerEnd | null = null
  let closest = END_REACH
  for (const end of ends) {
    const screen = mapToScreen(end, camera)
    const distance = Math.hypot(screen.x - point.x, screen.y - point.y)
    if (distance <= closest) { closest = distance; best = end }
  }
  return best
}

function trace(ctx: CanvasRenderingContext2D, line: readonly VisualPoint[]) {
  if (!line.length) return
  ctx.beginPath()
  ctx.moveTo(line[0].x, line[0].y)
  for (const point of line.slice(1)) ctx.lineTo(point.x, point.y)
}

function strokeLine(ctx: CanvasRenderingContext2D, line: VisualPoint[], color: string, width: number, dash: number[] = []) {
  if (line.length < 2) return
  trace(ctx, line)
  ctx.strokeStyle = color
  ctx.lineWidth = width
  ctx.setLineDash(dash)
  ctx.stroke()
}

function arrows(ctx: CanvasRenderingContext2D, points: VisualPoint[], color: string, size: number) {
  const steps = points.slice(1).map((b, index) => Math.hypot(b.x - points[index].x, b.y - points[index].y))
  const length = steps.reduce((sum, step) => sum + step, 0)
  if (length < 15) return
  let next = Math.min(38, length / 2)
  let distance = 0
  for (const [index, step] of steps.entries()) {
    const a = points[index], b = points[index + 1]
    while (step > 0 && next <= distance + step) {
      const ratio = (next - distance) / step
      const point = { x: a.x + (b.x - a.x) * ratio, y: a.y + (b.y - a.y) * ratio }
      ctx.save()
      ctx.translate(point.x, point.y)
      ctx.rotate(Math.atan2(b.y - a.y, b.x - a.x))
      ctx.fillStyle = color
      trace(ctx, [{ x: size, y: 0 }, { x: -size, y: size * .65 }, { x: -size, y: -size * .65 }])
      ctx.closePath()
      ctx.fill()
      ctx.restore()
      next += 76
    }
    distance += step
  }
}

function hatchClosedLane(ctx: CanvasRenderingContext2D, polygon: VisualPoint[], camera: MapCamera) {
  if (polygon.length < 3) return
  const points = polygon.map(point => mapToScreen(point, camera))
  const box = boundsOfPoints(points)
  const left = Math.max(0, box.min_x), top = Math.max(0, box.min_y)
  const right = Math.min(camera.width, box.max_x), bottom = Math.min(camera.height, box.max_y)
  if (left >= right || top >= bottom) return
  ctx.save()
  trace(ctx, points)
  ctx.closePath()
  ctx.clip()
  ctx.fillStyle = "rgba(220, 38, 38, .35)"
  ctx.fillRect(left, top, right - left, bottom - top)
  ctx.strokeStyle = "#f87171"
  ctx.lineWidth = 1.3
  ctx.beginPath()
  for (let offset = left - (bottom - top); offset < right; offset += 8) {
    ctx.moveTo(offset, bottom)
    ctx.lineTo(offset + bottom - top, top)
  }
  ctx.stroke()
  ctx.restore()
}

const endColors = { start: "#1D9E75", destination: "#378ADD" } as const

function drawEnd(ctx: CanvasRenderingContext2D, end: PlannerEnd, camera: MapCamera) {
  const { x, y } = mapToScreen(end, camera)
  const chosen = end.role === "start" || end.role === "destination"
  ctx.save()
  ctx.beginPath()
  ctx.arc(x, y, END_RADIUS, 0, Math.PI * 2)
  if (chosen) {
    ctx.fillStyle = endColors[end.role as "start" | "destination"]
    ctx.fill()
    ctx.lineWidth = 2
    ctx.strokeStyle = "#ffffff"
    ctx.stroke()
    ctx.fillStyle = "#ffffff"
    ctx.font = "600 12px system-ui, sans-serif"
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    ctx.fillText(end.role === "start" ? "A" : "B", x, y + 0.5)
    ctx.font = "500 12px system-ui, sans-serif"
    ctx.textAlign = "left"
    // Put the name beside the marker on the side with room, and never past the canvas edge.
    const width = ctx.measureText(end.label).width
    const fitsRight = x + END_RADIUS + 6 + width <= camera.width - 4
    const labelX = Math.max(4, Math.min(camera.width - width - 4, fitsRight ? x + END_RADIUS + 6 : x - END_RADIUS - 6 - width))
    ctx.lineWidth = 3
    ctx.strokeStyle = "rgba(15,23,42,.85)"
    ctx.strokeText(end.label, labelX, y)
    ctx.fillStyle = "#f8fafc"
    ctx.fillText(end.label, labelX, y)
  } else {
    ctx.fillStyle = "rgba(15,23,42,.55)"
    ctx.fill()
    ctx.lineWidth = 2
    ctx.setLineDash([4, 3])
    ctx.strokeStyle = end.role === "available" ? "#7dd3fc" : "rgba(148,163,184,.55)"
    ctx.stroke()
  }
  ctx.restore()
}

export function drawPlannerOverlay(ctx: CanvasRenderingContext2D, geometry: SceneGeometry, overlay: PlannerOverlay, camera: MapCamera, hoverId: string | null) {
  ctx.save()
  for (const id of overlay.closedLaneIds) {
    const lane = geometry.laneById.get(id)
    if (lane) hatchClosedLane(ctx, lane.polygon, camera)
  }
  for (const road of overlay.sharedRoads) {
    for (const [id, points] of Object.entries(road.lanes)) {
      const line = sharedLine(points).map(point => mapToScreen(point, camera))
      strokeLine(ctx, line, id === road.shared_lane ? "rgba(245,158,11,.72)" : "rgba(245,158,11,.42)", Math.max(2, road.width * camera.scale))
      arrows(ctx, line, palette.amber, 4)
    }
  }
  ctx.lineJoin = "round"
  for (const line of plannerPathLines(overlay.original)) {
    const points = line.map(point => mapToScreen(point, camera))
    strokeLine(ctx, points, palette.original, 7, [7, 5])
    arrows(ctx, points, palette.original, 7)
  }
  for (const line of plannerPathLines(overlay.selected)) {
    const points = line.map(point => mapToScreen(point, camera))
    strokeLine(ctx, points, "#123723", 5)
    strokeLine(ctx, points, palette.selected, 3)
    arrows(ctx, points, palette.selected, 5)
  }
  const highlight = geometry.laneById.get(overlay.selectedLaneId ?? hoverId ?? "")
  if (highlight) {
    const outline = highlight.polygon.map(point => mapToScreen(point, camera))
    if (outline.length) strokeLine(ctx, [...outline, outline[0]], palette.outline, 1.6)
  }
  for (const end of overlay.ends) drawEnd(ctx, end, camera)
  ctx.restore()
}

import type { RoutePath } from "@/api/routes"
import type { VisualPoint } from "@/api/visual-network"
import type { SharedRoad } from "@/simulation/frame-types"
import type { EndRole } from "@/lib/route-ends"
import { claimMapLabel, mapToScreen, screenToMap, type LabelRect, type MapCamera } from "@/simulation/map-navigation"
import { boundsOfPoints, distanceToPolyline, lanePolygon, pointInPolygon, type SceneBounds, type SceneGeometry, type SceneLane } from "@/simulation/scene-geometry"

export type PlannerEnd = { key: string; label: string; x: number; y: number; role: EndRole; selectable: boolean }
export type PlannerTarget = { kind: "end"; key: string } | { kind: "road"; laneId: string }
export type PlannerMapAction = { target: PlannerTarget | null; anchor: VisualPoint; contextMenu: boolean }

export type PlannerOverlay = {
  interactive: boolean
  original: RoutePath | null
  selected: RoutePath | null
  closedLaneIds: readonly string[]
  sharedRoads: readonly SharedRoad[]
  selectedLaneId: string | null
  ends: readonly PlannerEnd[]
}

export type PlannerFitRequest = { revision: number; target: "network" | "routes" }

const sharedLine = (points: Array<[number, number]>) => points.map(([x, y]) => ({ x, y }))
const END_RADIUS = 15
const END_REACH = 22
const END_LABEL_FONT = "600 12px system-ui, sans-serif"
const palette = { original: "#e2e8f0", selected: "#39e895", closed: "#ef4444", amber: "#f9b545", outline: "#7dd3fc" }
const PIN_REMOVE_RADIUS = 14

export function plannerRemovePosition(point: VisualPoint, camera: MapCamera) {
  const room = PIN_REMOVE_RADIUS + 2
  const offset = END_RADIUS + 10
  return { x: point.x + offset + room <= camera.width ? point.x + offset : point.x - offset,
    y: point.y - offset + 5 >= room ? point.y - offset + 5 : point.y + offset - 5 }
}

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

/** Markers take precedence if a tap overlaps a nearby label. */
export function pickPlannerEnd(ends: readonly PlannerEnd[], point: VisualPoint, camera: MapCamera,
  labels?: ReadonlyMap<string, LabelRect>) {
  const actionable = (end: PlannerEnd) => end.selectable || end.role === "start" || end.role === "destination"
  let best: PlannerEnd | null = null
  let closest = END_REACH
  for (const end of ends) {
    if (!actionable(end)) continue
    const screen = mapToScreen(end, camera)
    const distance = Math.hypot(screen.x - point.x, screen.y - point.y)
    if (distance <= closest) { closest = distance; best = end }
  }
  if (best || !labels) return best
  return ends.find(end => {
    const rect = actionable(end) ? labels.get(end.key) : undefined
    return rect && point.x >= rect.x && point.x <= rect.x + rect.width && point.y >= rect.y && point.y <= rect.y + rect.height
  }) ?? null
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

const markerStyles = {
  start: { color: "#126748", symbol: "A", label: "Start" },
  destination: { color: "#1e52a7", symbol: "B", label: "Destination" },
  other_exit: { color: "#983b13", symbol: "↗", label: "Actual exit" },
  available: { color: "#1e52a7", symbol: "•", label: null },
}

function drawEnds(ctx: CanvasRenderingContext2D, ends: readonly PlannerEnd[], camera: MapCamera) {
  const visible = ends.flatMap(end => {
    if (end.role === "unavailable") return []
    const point = mapToScreen(end, camera)
    if (point.x < -END_RADIUS || point.y < -END_RADIUS || point.x > camera.width + END_RADIUS || point.y > camera.height + END_RADIUS) return []
    return [{ end, point, style: markerStyles[end.role] }]
  })
  const labels = new Map<string, LabelRect>()
  const occupied = visible.map(({ point }) => ({ x: point.x - END_RADIUS, y: point.y - END_RADIUS, width: END_RADIUS * 2, height: END_RADIUS * 2 }))
  for (const { end, point } of visible) {
    if (end.role !== "start" && end.role !== "destination") continue
    const remove = plannerRemovePosition(point, camera)
    occupied.push({ x: remove.x - PIN_REMOVE_RADIUS, y: remove.y - PIN_REMOVE_RADIUS, width: PIN_REMOVE_RADIUS * 2, height: PIN_REMOVE_RADIUS * 2 })
  }

  ctx.textBaseline = "middle"
  ctx.setLineDash([])
  for (const { end, point: { x, y }, style } of visible) {
    ctx.beginPath()
    ctx.arc(x, y, END_RADIUS, 0, Math.PI * 2)
    ctx.fillStyle = style.color
    ctx.fill()
    ctx.strokeStyle = "#ffffff"
    ctx.lineWidth = 2.5
    ctx.stroke()
    ctx.fillStyle = "#ffffff"
    ctx.font = "700 16px system-ui, sans-serif"
    ctx.textAlign = "center"
    ctx.fillText(style.symbol, x, y)

    ctx.font = END_LABEL_FONT
    const text = style.label ?? end.label
    const width = Math.min(ctx.measureText(text).width + 16, camera.width - 16)
    const height = 23, gap = END_RADIUS + 6
    const alignedX = Math.max(4, Math.min(camera.width - width - 4, x - width / 2))
    const rect = claimMapLabel([
      { x: x + gap, y: y - height / 2, width, height },
      { x: x - gap - width, y: y - height / 2, width, height },
      { x: alignedX, y: y + gap, width, height },
      { x: alignedX, y: y - gap - height, width, height },
    ], occupied, camera.width, camera.height)
    if (!rect) continue
    labels.set(end.key, rect)
    ctx.beginPath()
    ctx.roundRect(rect.x, rect.y, rect.width, rect.height, 5)
    ctx.fillStyle = "#172635"
    ctx.fill()
    ctx.textAlign = "left"
    ctx.fillStyle = "#ffffff"
    ctx.fillText(text, rect.x + 8, rect.y + rect.height / 2, rect.width - 16)
  }
  return labels
}

export function drawPlannerOverlay(ctx: CanvasRenderingContext2D, geometry: SceneGeometry, overlay: PlannerOverlay, camera: MapCamera, hoverId: string | null) {
  ctx.save()
  for (const id of overlay.closedLaneIds) {
    const lane = geometry.laneById.get(id)
    if (lane) {
      hatchClosedLane(ctx, lane.polygon, camera)
      strokeLine(ctx, lane.centerline.map(point => mapToScreen(point, camera)), palette.closed, 4, [5, 4])
    }
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
    strokeLine(ctx, points, palette.original, 5, [7, 5])
  }
  for (const line of plannerPathLines(overlay.selected)) {
    const points = line.map(point => mapToScreen(point, camera))
    strokeLine(ctx, points, "#123723", 8)
    strokeLine(ctx, points, palette.selected, 4)
    arrows(ctx, points, palette.selected, 5)
  }
  const highlight = geometry.laneById.get(overlay.selectedLaneId ?? hoverId ?? "")
  if (highlight) {
    const outline = highlight.polygon.map(point => mapToScreen(point, camera))
    if (outline.length) strokeLine(ctx, [...outline, outline[0]], palette.outline, 1.6)
  }
  const labels = drawEnds(ctx, overlay.ends, camera)
  ctx.restore()
  return labels
}

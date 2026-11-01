import type { VisualNetwork, VisualPoint, VisualSignalGroup } from "@/api/visual-network"

/** Native metres, X east and Y north. Geometry never extends a supplied lane. */
export type SceneBounds = { min_x: number; min_y: number; max_x: number; max_y: number }
export type Selection = { kind: "junction" | "lane" | "vehicle" | "pedestrian"; id: string }
export type VehicleClass = "car" | "motorcycle" | "tricycle" | "bus" | "truck"
export type LaneKind = "road" | "connector" | "crossing" | "walking"
export type SceneLane = {
  id: string
  kind: LaneKind
  width: number
  /** Lanes across this carriageway; 1 when missing or invalid. */
  laneCount: number
  /** Precomputed so renderers can cache their paths. */
  dividers: VisualPoint[][]
  /** Left edge where an opposing carriageway meets this one; null when that edge is a kerb. */
  centreLine: VisualPoint[] | null
  length: number
  centerline: VisualPoint[]
  polygon: VisualPoint[]
  junctionIds: string[]
}
/** Painted zebra on one carriageway end inside a junction; walk signals stand on its kerb ends. */
export type SceneCrosswalk = { laneId: string; stripes: VisualPoint[][]; walkSignals: VisualPoint[] }
export type SceneJunction = {
  id: string
  label: string
  center: VisualPoint
  polygon: VisualPoint[]
  /** Drawn pavement outline: the polygon with rounded kerb corners between approaches. Picking keeps `polygon`. */
  kerb: VisualPoint[]
  crosswalks: SceneCrosswalk[]
}
export type SceneSignalGroup = VisualSignalGroup & { junctionId: string | null }
export type SceneGeometry = {
  networkId: string
  bounds: SceneBounds
  lanes: SceneLane[]
  connectors: SceneLane[]
  junctions: SceneJunction[]
  signalGroups: SceneSignalGroup[]
  laneById: Map<string, SceneLane>
  junctionById: Map<string, SceneJunction>
}

export const SCENE_PALETTE = {
  ground: "#E8ECE8", pavement: "#414852", markings: "#F3F2E9", curb: "#B8C0BA",
  building: "#D6DAD3", vegetation: "#839A83", selected: "#38BDF8", tricycle: "#69B83F",
  glass: "#293C43", tyre: "#232A30", pedestrian: "#D47746", red: "#E85E60",
  yellow: "#E9BF56", green: "#62B685", off: "#353D43", closed: "#BA5054", slow: "#B48B46",
  cars: ["#7A95A9", "#BD957C", "#D7DADB", "#AC817F", "#9092A3", "#71858D"],
} as const

/** Same defaults as simulation/scenario_config.py; frame dimensions take precedence. */
export const VEHICLE_DIMENSIONS: Record<VehicleClass, { length: number; width: number }> = {
  car: { length: 4.5, width: 1.8 }, motorcycle: { length: 2, width: 0.8 },
  tricycle: { length: 3, width: 1.4 }, bus: { length: 10, width: 2.5 },
  truck: { length: 8, width: 2.5 },
}

export function normalizeVehicleClass(type: string | undefined): VehicleClass {
  return type && Object.hasOwn(VEHICLE_DIMENSIONS, type) ? type as VehicleClass : "car"
}

export function vehicleDimensions(vehicle: { visual_type?: string; length?: number; width?: number }) {
  const defaults = VEHICLE_DIMENSIONS[normalizeVehicleClass(vehicle.visual_type)]
  return {
    length: Number.isFinite(vehicle.length) && vehicle.length! > 0 ? vehicle.length! : defaults.length,
    width: Number.isFinite(vehicle.width) && vehicle.width! > 0 ? vehicle.width! : defaults.width,
  }
}

export function selectionKey(selection: Selection | null) {
  return selection ? `${selection.kind}:${selection.id}` : ""
}

export function pointToThree(point: VisualPoint, elevation = 0) {
  return { x: point.x, y: elevation, z: -point.y }
}

/** Frame angles are clockwise from north; signal-group headings are from +X. */
export function headingToThreeYaw(angle: number) { return (90 - angle) * Math.PI / 180 }
export function headingToCanvasRotation(angle: number) { return (angle - 90) * Math.PI / 180 }
export function forwardAtHeading(angle: number): VisualPoint {
  const radians = angle * Math.PI / 180
  return { x: Math.sin(radians), y: Math.cos(radians) }
}

export function centeredVehicleFootprint(vehicle: { x: number; y: number; angle: number; length: number; width: number }): VisualPoint[] {
  const forward = forwardAtHeading(vehicle.angle)
  const left = { x: -forward.y, y: forward.x }
  return [[1, 1], [-1, 1], [-1, -1], [1, -1]].map(([longitudinal, lateral]) => ({
    x: vehicle.x + forward.x * longitudinal * vehicle.length / 2 + left.x * lateral * vehicle.width / 2,
    y: vehicle.y + forward.y * longitudinal * vehicle.length / 2 + left.y * lateral * vehicle.width / 2,
  }))
}

function clonePoints(points: readonly VisualPoint[]) {
  return points.map((point) => {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) throw new Error("Road geometry contains a non-finite coordinate")
    return { x: point.x, y: point.y }
  })
}

export function polylineLength(points: readonly VisualPoint[]) {
  let total = 0
  for (let index = 1; index < points.length; index++) total += Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y)
  return total
}

/** Left miter normal per point and the stretch that keeps a perpendicular distance across the join. */
function miterNormals(points: readonly VisualPoint[]) {
  const directions = points.slice(1).map((point, index) => {
    const dx = point.x - points[index].x, dy = point.y - points[index].y
    const length = Math.hypot(dx, dy) || 1
    return { x: dx / length, y: dy / length }
  })
  return points.map((_, index) => {
    const previous = directions[Math.max(0, index - 1)], next = directions[Math.min(index, directions.length - 1)]
    const normalX = -(previous.y + next.y), normalY = previous.x + next.x
    const normalLength = Math.hypot(normalX, normalY)
    const nx = normalLength > 1e-8 ? normalX / normalLength : -previous.y
    const ny = normalLength > 1e-8 ? normalY / normalLength : previous.x
    return { nx, ny, stretch: 1 / Math.max(Math.abs(nx * -previous.y + ny * previous.x), 1e-8) }
  })
}

/** Flat ends and bounded miter joins keep the road width without overshooting its ends. */
export function lanePolygon(points: readonly VisualPoint[], width: number): VisualPoint[] {
  if (points.length < 2) return []
  const left: VisualPoint[] = [], right: VisualPoint[] = []
  miterNormals(points).forEach(({ nx, ny, stretch }, index) => {
    const point = points[index]
    const offset = Math.min(width * 1.5, width / 2 * stretch)
    left.push({ x: point.x + nx * offset, y: point.y + ny * offset })
    right.push({ x: point.x - nx * offset, y: point.y - ny * offset })
  })
  return [...left, ...right.reverse()]
}

/** The polyline moved `distance` metres along lanePolygon's left normal (negative: right), with bounded miter joins. */
export function offsetLine(points: readonly VisualPoint[], distance: number): VisualPoint[] {
  const normals = miterNormals(points)
  return points.map((point, index) => {
    const { nx, ny, stretch } = normals[index]
    const offset = Math.sign(distance) * Math.min(Math.abs(distance) * 3, Math.abs(distance) * stretch)
    return { x: point.x + nx * offset, y: point.y + ny * offset }
  })
}

/** Lines between the lanes of a carriageway, offset -width/2 + k·width/laneCount along lanePolygon's normal. */
export function laneDividers(centerline: readonly VisualPoint[], width: number, laneCount: number): VisualPoint[][] {
  if (centerline.length < 2 || laneCount < 2) return []
  return Array.from({ length: laneCount - 1 }, (_, index) => offsetLine(centerline, -width / 2 + (index + 1) * width / laneCount))
}

/** Dash pieces of a polyline: `dash` metres drawn, then `gap` metres skipped. */
export function dashedPieces(points: readonly VisualPoint[], dash: number, gap: number): VisualPoint[][] {
  const pieces: VisualPoint[][] = []
  let current: VisualPoint[] | null = [{ ...points[0] }], remaining = dash
  for (let index = 1; index < points.length; index++) {
    let a = points[index - 1]
    const b = points[index]
    let segment = Math.hypot(b.x - a.x, b.y - a.y)
    while (segment > 1e-9) {
      const step = Math.min(segment, remaining)
      const fraction = step / segment
      const point = { x: a.x + (b.x - a.x) * fraction, y: a.y + (b.y - a.y) * fraction }
      if (current) current.push(point)
      segment -= step; remaining -= step; a = point
      if (remaining <= 1e-9) {
        if (current) { pieces.push(current); current = null; remaining = gap } else { current = [{ ...point }]; remaining = dash }
      }
    }
  }
  if (current && current.length > 1) pieces.push(current)
  return pieces
}

export function boundsOfPoints(points: readonly VisualPoint[], paddingFraction = 0): SceneBounds {
  if (!points.length) return { min_x: -25, min_y: -25, max_x: 25, max_y: 25 }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const point of points) { minX = Math.min(minX, point.x); minY = Math.min(minY, point.y); maxX = Math.max(maxX, point.x); maxY = Math.max(maxY, point.y) }
  if (maxX - minX < 1) { minX -= 0.5; maxX += 0.5 }
  if (maxY - minY < 1) { minY -= 0.5; maxY += 0.5 }
  const padX = (maxX - minX) * paddingFraction / 2, padY = (maxY - minY) * paddingFraction / 2
  return { min_x: minX - padX, min_y: minY - padY, max_x: maxX + padX, max_y: maxY + padY }
}

function distance(a: VisualPoint, b: VisualPoint) { return Math.hypot(a.x - b.x, a.y - b.y) }
type JunctionOutline = Pick<SceneJunction, "center" | "polygon">
function junctionRadius(junction: JunctionOutline) {
  return Math.max(15, ...junction.polygon.map((point) => distance(point, junction.center))) + 8
}
function unit(dx: number, dy: number) { const length = Math.hypot(dx, dy) || 1; return { x: dx / length, y: dy / length } }
function cross(a: VisualPoint, b: VisualPoint) { return a.x * b.y - a.y * b.x }

/** Painted markings and street furniture, in metres. Illustrative: the engine models none of them. */
const ZEBRA = { start: 0.6, end: 3.6, stripe: 0.5, period: 1, kerbMargin: 0.15 }
const WALK_SIGNAL_SETBACK = 1.1

type LaneEnd = { lane: SceneLane; point: VisualPoint; travel: VisualPoint; inward: VisualPoint }
/** The carriageway end at a junction, its direction of travel, and the direction into the junction. */
function laneEndAt(lane: SceneLane, junction: JunctionOutline): LaneEnd {
  const points = lane.centerline, last = points.length - 1
  const entering = distance(points[last], junction.center) <= distance(points[0], junction.center)
  const travel = entering ? unit(points[last].x - points[last - 1].x, points[last].y - points[last - 1].y) : unit(points[1].x - points[0].x, points[1].y - points[0].y)
  return { lane, point: entering ? points[last] : points[0], travel, inward: entering ? travel : { x: -travel.x, y: -travel.y } }
}

/** Kerb corners of every carriageway end, joined around the junction; corners between approaches become rounded kerbs. */
export function junctionKerbOutline(junction: JunctionOutline, ends: readonly LaneEnd[]): VisualPoint[] {
  const corners = ends.flatMap(({ lane, point, inward }) => [1, -1].map((side) => ({
    x: point.x - inward.y * side * lane.width / 2, y: point.y + inward.x * side * lane.width / 2, outward: { x: -inward.x, y: -inward.y },
  }))).sort((a, b) => Math.atan2(a.y - junction.center.y, a.x - junction.center.x) - Math.atan2(b.y - junction.center.y, b.x - junction.center.x))
  if (corners.length < 3) return clonePoints(junction.polygon)
  const outline: VisualPoint[] = []
  corners.forEach((a, index) => {
    const b = corners[(index + 1) % corners.length]
    outline.push({ x: a.x, y: a.y })
    const sameApproach = a.outward.x * b.outward.x + a.outward.y * b.outward.y > Math.cos(25 * Math.PI / 180)
    const turn = cross(a.outward, b.outward)
    if (sameApproach || distance(a, b) < 0.3 || Math.abs(turn) < 1e-6) return
    // Both kerb lines, extended back into the junction, meet at the corner the rounded kerb bends around.
    const gap = { x: b.x - a.x, y: b.y - a.y }, alongA = cross(gap, b.outward) / turn, alongB = cross(gap, a.outward) / turn
    const meetsInside = alongA < 0 && alongB < 0 && alongA > -25 && alongB > -25
    if (!meetsInside) return
    const control = { x: a.x + a.outward.x * alongA, y: a.y + a.outward.y * alongA }
    for (let step = 1; step < 8; step++) {
      const t = step / 8, u = 1 - t
      outline.push({ x: u * u * a.x + 2 * u * t * control.x + t * t * b.x, y: u * u * a.y + 2 * u * t * control.y + t * t * b.y })
    }
  })
  return outline
}

/** Zebra stripes 0.6–3.6 m inside the junction, so vehicles stop before them; stripes share a junction-wide grid. */
function crosswalkAt(end: LaneEnd, junction: JunctionOutline): SceneCrosswalk {
  const { lane, point, travel, inward } = end, across = { x: -inward.y, y: inward.x }
  const offset = (point.x - junction.center.x) * across.x + (point.y - junction.center.y) * across.y
  const at = (lateral: number, depth: number) => ({ x: point.x + across.x * (lateral - offset) + inward.x * depth, y: point.y + across.y * (lateral - offset) + inward.y * depth })
  const low = offset - lane.width / 2 + ZEBRA.kerbMargin, high = offset + lane.width / 2 - ZEBRA.kerbMargin, phase = (ZEBRA.period - ZEBRA.stripe) / 2
  const stripes: VisualPoint[][] = []
  for (let start = Math.ceil((low - phase) / ZEBRA.period) * ZEBRA.period + phase; start + ZEBRA.stripe <= high + 1e-9; start += ZEBRA.period) {
    stripes.push([at(start, ZEBRA.start), at(start + ZEBRA.stripe, ZEBRA.start), at(start + ZEBRA.stripe, ZEBRA.end), at(start, ZEBRA.end)])
  }
  // Right-hand traffic: the right edge is a kerb; the left edge is one too only without an opposing carriageway.
  const right = { x: travel.y, y: -travel.x }, reach = lane.width / 2 + WALK_SIGNAL_SETBACK, depth = (ZEBRA.start + ZEBRA.end) / 2
  const walkSignals = (lane.centreLine ? [1] : [1, -1]).map((side) => ({ x: point.x + right.x * reach * side + inward.x * depth, y: point.y + right.y * reach * side + inward.y * depth }))
  return { laneId: lane.id, stripes, walkSignals }
}

function middleOf(points: readonly VisualPoint[]) {
  const index = Math.max(0, Math.floor((points.length - 2) / 2))
  return { x: (points[index].x + points[index + 1].x) / 2, y: (points[index].y + points[index + 1].y) / 2 }
}

export function normalizeSceneGeometry(network: VisualNetwork): SceneGeometry {
  const metadata = network as VisualNetwork & { network_id?: string; junctions?: Array<{ id: string; label?: string; name?: string }> }
  const outlines = network.signals.map((signal, index) => {
    const node = metadata.junctions?.find((junction) => junction.id === signal.id)
    return { id: signal.id, label: node?.label || node?.name || `Junction ${index + 1}`, center: { x: signal.x, y: signal.y }, polygon: clonePoints(signal.shape) }
  })
  const lanes: SceneLane[] = []
  const laneById = new Map<string, SceneLane>()
  const collections = [[network.roads, "road"], [network.internal_lanes, "connector"], [network.crossings, "crossing"], [network.walking_areas, "walking"]] as const
  for (const [roads, kind] of collections) for (const road of roads) for (const lane of road.lanes) {
    if (laneById.has(lane.id)) throw new Error(`Duplicate visual lane ID: ${lane.id}`)
    const centerline = clonePoints(lane.shape)
    const width = Number.isFinite(lane.width) && lane.width > 0 ? lane.width : 3.3
    const junctionIds = outlines.filter((junction) => centerline.length > 0 && (
      distance(centerline[0], junction.center) <= junctionRadius(junction) || distance(centerline[centerline.length - 1], junction.center) <= junctionRadius(junction)
    )).map((junction) => junction.id)
    const laneCount = Number.isInteger(lane.lane_count) && (lane.lane_count ?? 0) >= 1 ? lane.lane_count as number : 1
    const normalized: SceneLane = {
      id: lane.id, kind, width, laneCount, dividers: kind === "road" ? laneDividers(centerline, width, laneCount) : [], centreLine: null,
      length: polylineLength(centerline), centerline, polygon: lanePolygon(centerline, width), junctionIds,
    }
    lanes.push(normalized)
    laneById.set(lane.id, normalized)
  }
  const roads = lanes.filter((lane) => lane.kind === "road" && lane.centerline.length > 1)
  const leftEdges = new Map(roads.map((lane) => [lane, lane.polygon.slice(0, lane.centerline.length)]))
  for (const lane of roads) {
    const middle = middleOf(leftEdges.get(lane)!)
    const opposed = roads.some((other) => other !== lane && distanceToPolyline(middle, leftEdges.get(other)!) < 0.3)
    lane.centreLine = opposed ? leftEdges.get(lane)! : null
  }
  const junctions: SceneJunction[] = outlines.map((outline) => {
    const reach = Math.max(...outline.polygon.map((point) => distance(point, outline.center)), 0) + 1
    const ends = roads.filter((lane) => lane.junctionIds.includes(outline.id)).map((lane) => laneEndAt(lane, outline)).filter((end) => distance(end.point, outline.center) <= reach)
    return { ...outline, kerb: junctionKerbOutline(outline, ends), crosswalks: ends.map((end) => crosswalkAt(end, outline)) }
  })
  const signalGroups = network.signal_groups.map((group) => {
    const lane = laneById.get(group.lane_id)
    const candidates = junctions.filter((junction) => lane?.junctionIds.includes(junction.id))
    const nearest = [...(candidates.length ? candidates : junctions)].sort((a, b) => distance(a.center, group.anchor) - distance(b.center, group.anchor))[0]
    return { ...group, anchor: { ...group.anchor }, stop_line: clonePoints(group.stop_line), link_indices: [...group.link_indices], via_lane_ids: [...group.via_lane_ids], junctionId: nearest?.id ?? null }
  })
  const fallbackBounds = boundsOfPoints([...lanes.flatMap((lane) => lane.polygon), ...junctions.flatMap((junction) => junction.polygon)])
  const bounds = network.bounds && Object.values(network.bounds).every(Number.isFinite) && network.bounds.max_x > network.bounds.min_x && network.bounds.max_y > network.bounds.min_y ? { ...network.bounds } : fallbackBounds
  return { networkId: metadata.network_id || network.source_net, bounds, lanes, connectors: lanes.filter((lane) => lane.kind === "connector"), junctions, signalGroups, laneById, junctionById: new Map(junctions.map((junction) => [junction.id, junction])) }
}

/** Clip only the camera fitting sample; the displayed lane geometry remains untouched. */
function immediateApproach(points: readonly VisualPoint[], junction: SceneJunction, distanceMetres: number) {
  if (!points.length) return []
  const ordered = distance(points[0], junction.center) <= distance(points[points.length - 1], junction.center) ? points : [...points].reverse()
  const result = [{ ...ordered[0] }]
  let remaining = distanceMetres
  for (let index = 1; index < ordered.length && remaining > 0; index++) {
    const previous = ordered[index - 1], next = ordered[index], segment = distance(previous, next)
    if (segment <= remaining) { result.push({ ...next }); remaining -= segment }
    else {
      const fraction = remaining / segment
      result.push({ x: previous.x + (next.x - previous.x) * fraction, y: previous.y + (next.y - previous.y) * fraction })
      remaining = 0
    }
  }
  return result
}

export function boundsForJunction(geometry: SceneGeometry, junctionId: string | null | undefined, paddingFraction = 0.2): SceneBounds {
  const junction = junctionId ? geometry.junctionById.get(junctionId) : undefined
  if (!junction) return geometry.bounds
  const approaches = geometry.lanes.filter((lane) => lane.kind === "road" && lane.junctionIds.includes(junction.id))
  const points = [junction.center, ...junction.polygon, ...approaches.flatMap((lane) => lanePolygon(immediateApproach(lane.centerline, junction, 40), lane.width))]
  // An isolated junction still needs a useful camera footprint.
  if (points.length < 3) points.push({ x: junction.center.x - 20, y: junction.center.y - 20 }, { x: junction.center.x + 20, y: junction.center.y + 20 })
  return boundsOfPoints(points, paddingFraction)
}

export function distanceToPolyline(point: VisualPoint, points: readonly VisualPoint[]) {
  let closest = Infinity
  for (let index = 1; index < points.length; index++) {
    const a = points[index - 1], b = points[index], dx = b.x - a.x, dy = b.y - a.y
    const squaredLength = dx * dx + dy * dy
    const fraction = squaredLength > 0 ? Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / squaredLength)) : 0
    closest = Math.min(closest, Math.hypot(point.x - a.x - fraction * dx, point.y - a.y - fraction * dy))
  }
  return closest
}

export function pointInPolygon(point: VisualPoint, polygon: readonly VisualPoint[]) {
  let inside = false
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const a = polygon[index], b = polygon[previous]
    if ((a.y > point.y) !== (b.y > point.y) && point.x < (b.x - a.x) * (point.y - a.y) / (b.y - a.y) + a.x) inside = !inside
  }
  return inside
}

type PickFrame = {
  vehicles: Array<{ id: string; x: number; y: number; angle: number; length: number; width: number }>
  pedestrians: Array<{ id: string; x: number; y: number }>
}
/** Shared native-coordinate hit testing. Dynamic entities win over pavement beneath them. */
export function pickSceneEntity(geometry: SceneGeometry, frame: PickFrame | null, point: VisualPoint, toleranceMetres = 1): Selection | null {
  const people = frame?.pedestrians.filter((person) => distance(point, person) <= Math.max(.5, toleranceMetres))
    .sort((a, b) => distance(point, a) - distance(point, b) || a.id.localeCompare(b.id))[0]
  if (people) return { kind: "pedestrian", id: people.id }
  const vehicles = frame?.vehicles.filter((vehicle) => {
    const forward = forwardAtHeading(vehicle.angle), dx = point.x - vehicle.x, dy = point.y - vehicle.y
    const longitudinal = Math.abs(dx * forward.x + dy * forward.y), lateral = Math.abs(-dx * forward.y + dy * forward.x)
    return longitudinal <= vehicle.length / 2 + toleranceMetres && lateral <= vehicle.width / 2 + toleranceMetres
  }).sort((a, b) => distance(point, a) - distance(point, b) || a.id.localeCompare(b.id))[0]
  if (vehicles) return { kind: "vehicle", id: vehicles.id }
  const junction = geometry.junctions.find((candidate) => pointInPolygon(point, candidate.polygon))
  if (junction) return { kind: "junction", id: junction.id }
  const lane = geometry.lanes.filter((candidate) => candidate.kind !== "connector" && distanceToPolyline(point, candidate.centerline) <= candidate.width / 2 + toleranceMetres)
    .sort((a, b) => distanceToPolyline(point, a.centerline) - distanceToPolyline(point, b.centerline) || a.id.localeCompare(b.id))[0]
  return lane ? { kind: "lane", id: lane.id } : null
}

export type SignalColor = "green" | "yellow" | "red" | "off"
type SignalFrame = {
  traffic_lights?: Record<string, { state: string }>
  junction_controls?: Record<string, { mode: string }>
  ns_state?: string
  ew_state?: string
}

export function hasSignalHead(group: VisualSignalGroup & { junctionId?: string | null }, frame: SignalFrame | null): boolean {
  return frame?.traffic_lights?.[group.signal_id]?.state !== "n" &&
    !(group.junctionId && frame?.junction_controls?.[group.junctionId]?.mode === "first_come")
}

function canonicalSignalColor(state: string | undefined): SignalColor | null {
  const value = state?.toLowerCase()
  if (value === "g" || value === "green") return "green"
  if (value === "y" || value === "yellow") return "yellow"
  if (value === "r" || value === "red") return "red"
  if (value === "o" || value === "off" || value === "all_way_stop") return "off"
  return null
}

export function signalAppearance(group: VisualSignalGroup & { junctionId?: string | null }, frame: SignalFrame | null) {
  if (group.junctionId && frame?.junction_controls?.[group.junctionId]?.mode === "all_way_stop") return { color: "off" as const, lit: false, available: true, label: "All-way stop · unlit" }
  const state = frame?.traffic_lights?.[group.signal_id]?.state
  let resolved: SignalColor | null = null
  if (state) {
    const fullName = canonicalSignalColor(state)
    const links = fullName ? [fullName] : group.link_indices.map((index) => canonicalSignalColor(state[index])).filter((value): value is SignalColor => value !== null)
    resolved = ["green", "yellow", "red", "off"].find((color) => links.includes(color as SignalColor)) as SignalColor | undefined ?? null
  }
  if (!state && frame) {
    const heading = ((group.heading % 180) + 180) % 180
    resolved = canonicalSignalColor(heading >= 45 && heading <= 135 ? frame.ns_state : frame.ew_state)
  }
  const color = resolved ?? "off"
  return { color, lit: color !== "off", available: resolved !== null, label: resolved === null ? "Signal unavailable" : color === "off" ? "Unlit" : color[0].toUpperCase() + color.slice(1) }
}

/**
 * Mast-arm signal for one approach: the pole stands on the right-hand kerb at the stop line and the head hangs
 * just past it, centred over the carriageway. Its lenses face `facing`, back toward the oncoming vehicles.
 */
export function signalHeadPlacement(group: Pick<VisualSignalGroup, "anchor" | "heading" | "width">) {
  const radians = group.heading * Math.PI / 180
  const forward = { x: Math.cos(radians), y: Math.sin(radians) }, right = { x: forward.y, y: -forward.x }
  const kerb = group.width / 2 + WALK_SIGNAL_SETBACK
  return {
    head: { x: group.anchor.x + forward.x * 0.9, y: group.anchor.y + forward.y * 0.9 },
    pole: { x: group.anchor.x + right.x * kerb - forward.x * 0.3, y: group.anchor.y + right.y * kerb - forward.y * 0.3 },
    facing: { x: -forward.x, y: -forward.y },
    right,
  }
}

export type WalkSignal = "walk" | "dont_walk" | "off"
/**
 * The engine runs one exclusive pedestrian phase per junction, so every crossing there shows the same walk state.
 * Its walk phase ends straight in all-red (no pedestrian yellow), so there is no flashing clearance to show.
 */
export function walkSignalState(junctionId: string, frame: { junction_controls?: Record<string, { mode: string; phase?: string }> } | null): WalkSignal | null {
  const control = frame?.junction_controls?.[junctionId]
  if (!control) return null
  if (control.mode === "all_way_stop") return "off"
  return control.phase === "PED_GREEN" ? "walk" : "dont_walk"
}

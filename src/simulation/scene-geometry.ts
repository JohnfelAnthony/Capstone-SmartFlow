import type { VisualNetwork, VisualPoint, VisualSignalGroup } from "@/api/visual-network"

/** Native metres, X east and Y north. Geometry never extends a supplied lane. */
export type SceneBounds = { min_x: number; min_y: number; max_x: number; max_y: number }
export type Selection = { kind: "junction" | "lane" | "vehicle" | "pedestrian"; id: string }
export type VehicleClass = "car" | "motorcycle" | "tricycle" | "bus" | "truck" | "emergency"
export type LaneKind = "road" | "connector" | "crossing" | "walking"
export type SceneLane = {
  id: string
  kind: LaneKind
  width: number
  length: number
  centerline: VisualPoint[]
  polygon: VisualPoint[]
  junctionIds: string[]
}
export type SceneJunction = {
  id: string
  label: string
  center: VisualPoint
  polygon: VisualPoint[]
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
  truck: { length: 8, width: 2.5 }, emergency: { length: 5, width: 2 },
}

export function normalizeVehicleClass(type: string | undefined, emergency = false): VehicleClass {
  if (emergency || type === "emergency") return "emergency"
  return type && Object.hasOwn(VEHICLE_DIMENSIONS, type) ? type as VehicleClass : "car"
}

export function vehicleDimensions(vehicle: { visual_type?: string; emergency?: boolean; length?: number; width?: number }) {
  const defaults = VEHICLE_DIMENSIONS[normalizeVehicleClass(vehicle.visual_type, vehicle.emergency)]
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

/** Flat ends and bounded miter joins keep the road width without overshooting its ends. */
export function lanePolygon(points: readonly VisualPoint[], width: number): VisualPoint[] {
  if (points.length < 2) return []
  const directions = points.slice(1).map((point, index) => {
    const dx = point.x - points[index].x, dy = point.y - points[index].y
    const length = Math.hypot(dx, dy) || 1
    return { x: dx / length, y: dy / length }
  })
  const left: VisualPoint[] = [], right: VisualPoint[] = []
  points.forEach((point, index) => {
    const previous = directions[Math.max(0, index - 1)], next = directions[Math.min(index, directions.length - 1)]
    const normalX = -(previous.y + next.y), normalY = previous.x + next.x
    const normalLength = Math.hypot(normalX, normalY)
    const nx = normalLength > 1e-8 ? normalX / normalLength : -previous.y
    const ny = normalLength > 1e-8 ? normalY / normalLength : previous.x
    const projection = Math.abs(nx * -previous.y + ny * previous.x)
    const offset = Math.min(width * 1.5, width / 2 / Math.max(projection, 1e-8))
    left.push({ x: point.x + nx * offset, y: point.y + ny * offset })
    right.push({ x: point.x - nx * offset, y: point.y - ny * offset })
  })
  return [...left, ...right.reverse()]
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
function junctionRadius(junction: SceneJunction) {
  return Math.max(15, ...junction.polygon.map((point) => distance(point, junction.center))) + 8
}

export function normalizeSceneGeometry(network: VisualNetwork): SceneGeometry {
  const metadata = network as VisualNetwork & { network_id?: string; junctions?: Array<{ id: string; label?: string; name?: string }> }
  const junctions = network.signals.map((signal, index) => {
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
    const junctionIds = junctions.filter((junction) => centerline.length > 0 && (
      distance(centerline[0], junction.center) <= junctionRadius(junction) || distance(centerline[centerline.length - 1], junction.center) <= junctionRadius(junction)
    )).map((junction) => junction.id)
    const normalized: SceneLane = { id: lane.id, kind, width, length: polylineLength(centerline), centerline, polygon: lanePolygon(centerline, width), junctionIds }
    lanes.push(normalized)
    laneById.set(lane.id, normalized)
  }
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

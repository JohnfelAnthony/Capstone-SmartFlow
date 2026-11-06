import type { VisualPoint } from "@/api/visual-network"
import type { SharedRoad } from "@/simulation/frame-types"
import { immediateApproach, signalAppearance, type SceneGeometry, type SceneJunction } from "@/simulation/scene-geometry"

export function junctionShortLabel(geometry: SceneGeometry, junctionId: string) {
  const index = geometry.junctions.findIndex(junction => junction.id === junctionId)
  return index < 0 ? junctionId : `J${index + 1}`
}

export function laneDisplayLabel(geometry: SceneGeometry, laneId: string) {
  const group = geometry.signalGroups.find(candidate => candidate.kind === "vehicle" && candidate.lane_id === laneId)
  if (!group?.junctionId) return laneId
  const approaches = [...new Set(geometry.signalGroups
    .filter(candidate => candidate.kind === "vehicle" && candidate.junctionId === group.junctionId)
    .map(candidate => candidate.lane_id))]
  return `${junctionShortLabel(geometry, group.junctionId)} approach ${approaches.indexOf(laneId) + 1}`
}

/** How far a turn arrow runs along the roads on each side of the junction. */
export const TURN_ARROW_EXTENSION_M = 6.5

/** One readable arrow per allowed turn (connector ids are `incoming->outgoing`). Illustrative: arrows start apart, left turn on the left, and meet the real connector by its end. */
function turnArrows(geometry: SceneGeometry, junction: SceneJunction, laneId: string): { points: VisualPoint[]; target: string }[] {
  const approach = geometry.laneById.get(laneId)
  const tail = approach ? immediateApproach(approach.centerline, junction, TURN_ARROW_EXTENSION_M).reverse() : []
  if (!approach || tail.length < 2) return []
  const stopLine = tail[tail.length - 1], before = tail[tail.length - 2]
  const reach = Math.hypot(stopLine.x - before.x, stopLine.y - before.y) || 1
  const travel = { x: (stopLine.x - before.x) / reach, y: (stopLine.y - before.y) / reach }
  const leftwardTurn = (centerline: readonly VisualPoint[]) => {
    const end = centerline[centerline.length - 1], previous = centerline[centerline.length - 2]
    const dx = end.x - previous.x, dy = end.y - previous.y
    return Math.atan2(travel.x * dy - travel.y * dx, travel.x * dx + travel.y * dy)
  }
  const connectors = geometry.connectors.filter(connector => connector.id.startsWith(`${laneId}->`) && connector.centerline.length > 1)
    .sort((a, b) => leftwardTurn(b.centerline) - leftwardTurn(a.centerline))
  const spacing = Math.max(approach.width * 0.26, 1.4)
  return connectors.map((connector, index) => {
    const leftShift = spacing * ((connectors.length - 1) / 2 - index)
    const shifted = (point: VisualPoint, amount: number) => ({ x: point.x - travel.y * leftShift * amount, y: point.y + travel.x * leftShift * amount })
    const target = connector.id.slice(laneId.length + 2)
    const exit = geometry.laneById.get(target)
    const head = exit ? immediateApproach(exit.centerline, junction, TURN_ARROW_EXTENSION_M) : []
    const last = connector.centerline.length - 1
    return {
      target,
      points: [
        ...tail.map(point => shifted(point, 1)),
        ...connector.centerline.slice(1).map((point, step) => { const t = (step + 1) / last; return shifted(point, 1 - t * t * (3 - 2 * t)) }),
        ...head.slice(1),
      ],
    }
  })
}

/** Each signalled approach of a junction, its own light colour and an arrow for every turn it allows. */
export function signalMovements(geometry: SceneGeometry, junctionId: string, frame: Parameters<typeof signalAppearance>[1]) {
  const junction = geometry.junctionById.get(junctionId)
  if (!junction) return []
  return geometry.signalGroups.filter(group => group.kind === "vehicle" && group.junctionId === junctionId).map(group => {
    const arrows = turnArrows(geometry, junction, group.lane_id)
    return { laneId: group.lane_id, color: signalAppearance(group, frame).color, turns: arrows.map(arrow => arrow.points), turnTargets: arrows.map(arrow => arrow.target) }
  })
}

/** Lanes closed to entry right now: those set from the start and those a scheduled event has closed so far. */
export function closedLaneIds(frame: { visual?: { closed_lanes?: string[] }; lane_metrics?: Record<string, { closed?: boolean }> } | null | undefined) {
  const closed = new Set(frame?.visual?.closed_lanes ?? [])
  for (const [laneId, metrics] of Object.entries(frame?.lane_metrics ?? {})) if (metrics.closed) closed.add(laneId)
  return closed
}

/** Which of this junction's approaches and exits are closed, and every turn that cannot be made because of it. */
export function junctionClosures(geometry: SceneGeometry, junctionId: string, closed: ReadonlySet<string>) {
  const approaches = new Set(geometry.signalGroups.filter(group => group.kind === "vehicle" && group.junctionId === junctionId).map(group => group.lane_id))
  const turns = geometry.connectors.filter(connector => connector.id.includes("->") && approaches.has(connector.id.split("->")[0]))
    .map(connector => { const [from, to] = connector.id.split("->"); return { from, to } })
  return {
    closedApproaches: [...approaches].filter(laneId => closed.has(laneId)),
    closedExits: [...new Set(turns.map(turn => turn.to))].filter(laneId => closed.has(laneId)),
    unavailableTurns: turns.filter(turn => closed.has(turn.from) || closed.has(turn.to)).sort((a, b) => a.from.localeCompare(b.from) || a.to.localeCompare(b.to)),
  }
}

/** The lane keeping its own pavement when `laneId` is the closed, shared direction of its road (ids end in f or r). */
export const keptLaneOf = (laneId: string) => `${laneId.slice(0, -1)}${laneId.endsWith("f") ? "r" : "f"}`

export type SharedStrip = { sharedLane: string; keptLane: string; width: number; lanes: Record<string, VisualPoint[]> }

function nearestPoint(point: VisualPoint, line: readonly VisualPoint[]) {
  let best = line[0], bestDistance = Infinity
  for (let index = 1; index < line.length; index++) {
    const a = line[index - 1], b = line[index], dx = b.x - a.x, dy = b.y - a.y, squared = dx * dx + dy * dy
    const fraction = squared > 0 ? Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / squared)) : 0
    const candidate = { x: a.x + dx * fraction, y: a.y + dy * fraction }, gap = Math.hypot(point.x - candidate.x, point.y - candidate.y)
    if (gap < bestDistance) { best = candidate; bestDistance = gap }
  }
  return best
}

/** Where the two lanes of a road would run if its closed direction shared the opposite pavement: the road's axis lies halfway between the two lane centre lines, the kept lane moves to the middle of its own half and the shared one to the middle of the inner half. Used before a run; a run reports the engine's own geometry. */
export function sharedStripsFromGeometry(geometry: SceneGeometry, sharedLanes: Iterable<string>): SharedStrip[] {
  const strips: SharedStrip[] = []
  for (const sharedLane of sharedLanes) {
    const keptLane = keptLaneOf(sharedLane)
    const closedSide = geometry.laneById.get(sharedLane), keptSide = geometry.laneById.get(keptLane)
    if (!closedSide || !keptSide || keptSide.centerline.length < 2) continue
    const axis = keptSide.centerline.map(point => { const other = nearestPoint(point, closedSide.centerline); return { x: (point.x + other.x) / 2, y: (point.y + other.y) / 2 } })
    const along = (factor: number) => keptSide.centerline.map((point, index) => ({ x: axis[index].x + (point.x - axis[index].x) * factor, y: axis[index].y + (point.y - axis[index].y) * factor }))
    strips.push({ sharedLane, keptLane, width: keptSide.width / 2, lanes: { [keptLane]: along(1.5), [sharedLane]: along(0.5) } })
  }
  return strips
}

/** The engine's own geometry for the roads sharing a pavement right now. */
export function sharedStripsFromFrame(frame: { visual?: { shared_roads?: SharedRoad[] } } | null | undefined): SharedStrip[] {
  return (frame?.visual?.shared_roads ?? []).map(road => ({
    sharedLane: road.shared_lane, keptLane: road.kept_lane, width: road.width,
    lanes: Object.fromEntries(Object.entries(road.lanes).map(([lane, points]) => [lane, points.map(([x, y]) => ({ x, y }))])),
  }))
}

/** Compass side a leaving road heads towards, from the lane's first heading (+y is north). */
export function departureDirection(geometry: SceneGeometry, laneId: string) {
  const points = geometry.laneById.get(laneId)?.centerline ?? []
  if (points.length < 2) return null
  const end = points[points.length - 1], start = points[0]
  const dx = end.x - start.x, dy = end.y - start.y
  if (dx === 0 && dy === 0) return null
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? "To east" : "To west"
  return dy > 0 ? "To north" : "To south"
}

/** Compass side a vehicle approach comes from, using the lane's final travel direction (+y is north). */
export function approachDirection(geometry: SceneGeometry, laneId: string) {
  const points = geometry.laneById.get(laneId)?.centerline ?? []
  if (points.length < 2) return null
  const end = points[points.length - 1], previous = points[points.length - 2]
  const dx = end.x - previous.x, dy = end.y - previous.y
  if (dx === 0 && dy === 0) return null
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? "From west" : "From east"
  return dy > 0 ? "From south" : "From north"
}

/** "J1: Arellano Street / Osmeña Street" → "J1 · Arellano × Osmeña" for compact map tags. */
export function junctionTagText(label: string) {
  const match = /^(J\d+):\s*(.*)$/.exec(label)
  const streets = (match ? match[2] : label).split(" / ").map(street => street.replace(/\s+Street$/i, "")).join(" × ")
  return match ? `${match[1]} · ${streets}` : streets
}

/** Engine phase name ("SOUTH_GREEN", "PED_GREEN", "ALL_RED") → the service it belongs to, or null during all-red. */
export function phaseService(phase: string | undefined) {
  if (!phase || phase === "ALL_RED") return null
  const family = phase.split("_")[0].toLowerCase()
  return family === "ped" ? "pedestrian" : family
}

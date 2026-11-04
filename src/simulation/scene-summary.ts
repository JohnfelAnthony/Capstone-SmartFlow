import type { VisualPoint } from "@/api/visual-network"
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
function turnArrows(geometry: SceneGeometry, junction: SceneJunction, laneId: string) {
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
    const exit = geometry.laneById.get(connector.id.slice(laneId.length + 2))
    const head = exit ? immediateApproach(exit.centerline, junction, TURN_ARROW_EXTENSION_M) : []
    const last = connector.centerline.length - 1
    return [
      ...tail.map(point => shifted(point, 1)),
      ...connector.centerline.slice(1).map((point, step) => { const t = (step + 1) / last; return shifted(point, 1 - t * t * (3 - 2 * t)) }),
      ...head.slice(1),
    ]
  })
}

/** Each signalled approach of a junction, its own light colour and an arrow for every turn it allows. */
export function signalMovements(geometry: SceneGeometry, junctionId: string, frame: Parameters<typeof signalAppearance>[1]) {
  const junction = geometry.junctionById.get(junctionId)
  if (!junction) return []
  return geometry.signalGroups.filter(group => group.kind === "vehicle" && group.junctionId === junctionId).map(group => ({
    laneId: group.lane_id,
    color: signalAppearance(group, frame).color,
    turns: turnArrows(geometry, junction, group.lane_id),
  }))
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

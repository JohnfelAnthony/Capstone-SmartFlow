import type { SceneGeometry } from "@/simulation/scene-geometry"

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

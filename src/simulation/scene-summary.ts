import type { LaneMetrics } from "@/simulation/frame-types"
import type { SceneGeometry } from "@/simulation/scene-geometry"

/** Signal groups identify incoming approaches; lane endpoints also include exits. */
export function longestQueuedApproach(
  geometry: SceneGeometry,
  metrics: Record<string, LaneMetrics> | undefined,
  junctionId: string | null,
) {
  if (!metrics) return null
  const incoming = junctionId === null ? null : new Set(geometry.signalGroups
    .filter(group => group.kind === "vehicle" && group.junctionId === junctionId)
    .map(group => group.lane_id))
  let longest: { id: string; queue: number } | null = null
  for (const [id, metric] of Object.entries(metrics)) {
    if (incoming && !incoming.has(id)) continue
    if (!Number.isFinite(metric.queue)) continue
    if (!longest || metric.queue > longest.queue || metric.queue === longest.queue && id.localeCompare(longest.id) < 0) {
      longest = { id, queue: metric.queue }
    }
  }
  return longest
}

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

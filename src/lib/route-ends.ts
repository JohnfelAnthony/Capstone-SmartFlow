import type { RouteContext, RoutePath, RoutePreview, RouteVehicleClass } from "@/api/routes"
import type { VisualPoint } from "@/api/visual-network"

/** One place where traffic can enter or leave the study area, as a person sees it on the map. */
export type RouteEnd = { key: string; label: string; x: number; y: number; entryId: string | null; destinationId: string | null }
export type EndStep = "start" | "destination"
export type EndRole = "start" | "destination" | "available" | "unavailable"
export type EndAction = { type: "entry"; entryId: string } | { type: "destination"; destinationId: string }

// The two carriageways of a dual road end a few metres apart; separate ends are far more than this.
const SAME_END_METERS = 40
const STUDY_JUNCTION_METERS = 30

const distance = (a: VisualPoint, b: VisualPoint) => Math.hypot(a.x - b.x, a.y - b.y)

/** "Dao Street · south-east, 0–88 m out" becomes "Dao Street (south-east end)". */
function endName(roadLabel: string | undefined, boundaryLabel: string) {
  const [name, where] = roadLabel?.split(" · ") ?? []
  const place = where?.split(",")[0]
  return name && place ? `${name} (${place} end)` : boundaryLabel
}

/** "Dalisay Gante Road · south, 0–145 m out" + "southbound" becomes "Dalisay Gante Road, south part · southbound". */
export function describeRoad(road: RouteContext["roads"][number]) {
  const [name, where] = road.label.split(" · ")
  const place = where?.split(",")[0]
  return `${place ? `${name}, ${place} part` : road.label} · ${road.direction}`
}

export function buildRouteEnds(context: Pick<RouteContext, "entries" | "destinations" | "roads" | "geometry">): RouteEnd[] {
  const shapes = new Map(context.geometry.roads.flatMap(road => road.lanes.map(lane => [lane.id, lane.shape] as const)))
  const roadLabels = new Map(context.roads.map(road => [road.lane_id, road.label]))
  const ends: Array<Omit<RouteEnd, "key"> & { count: number }> = []
  const add = (kind: "entry" | "destination", boundary: { id: string; label: string; lane_ids: string[] }) => {
    const shape = shapes.get(boundary.lane_ids[0])
    const point = kind === "entry" ? shape?.[0] : shape?.at(-1)
    if (!point) return
    const idKey = kind === "entry" ? "entryId" : "destinationId"
    const end = ends.find(item => item[idKey] === null && distance(item, point) <= SAME_END_METERS)
    if (end) {
      end[idKey] = boundary.id
      end.x = (end.x * end.count + point.x) / (end.count + 1)
      end.y = (end.y * end.count + point.y) / (end.count + 1)
      end.count += 1
      return
    }
    ends.push({ label: endName(roadLabels.get(boundary.lane_ids[0]), boundary.label), x: point.x, y: point.y, count: 1,
      entryId: kind === "entry" ? boundary.id : null, destinationId: kind === "destination" ? boundary.id : null })
  }
  context.entries.forEach(entry => add("entry", entry))
  context.destinations.forEach(destination => add("destination", destination))
  return ends.map(({ label, x, y, entryId, destinationId }) => ({ key: `${entryId ?? ""}|${destinationId ?? ""}`, label, x, y, entryId, destinationId }))
}

export function routeLengthMeters(path: RoutePath | null) {
  return path?.segments.reduce((total, { points }) =>
    total + points.slice(1).reduce((sum, point, index) => sum + distance(points[index], point), 0), 0) ?? 0
}

export function passesStudyJunction(path: RoutePath | null, context: Pick<RouteContext, "network_id" | "geometry">) {
  const junction = context.geometry.junctions?.find(item => item.id === `${context.network_id}_j`)
  return !!junction && !!path?.segments.some(segment =>
    segment.kind === "connector" && segment.points.some(point => distance(point, junction) <= STUDY_JUNCTION_METERS))
}

export const formatDistance = (meters: number) =>
  meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters / 10) * 10} m`

const statusWords: Record<RoutePreview["outcome"], string> = {
  unchanged: "Same route", detour: "Detour", alternative_exit: "Other exit",
  waiting_entry: "Waiting", no_route: "No route", invalid_arrangement: "Not usable",
}

export const routeStatus = (preview: RoutePreview | null) => preview ? statusWords[preview.outcome] : "Choose a trip"

export function describeRoute({ vehicle, preview, context, ends, entryId, destinationId, closedCount }: {
  vehicle: RouteVehicleClass; preview: RoutePreview; context: Pick<RouteContext, "network_id" | "geometry">
  ends: readonly RouteEnd[]; entryId: string; destinationId: string; closedCount: number
}) {
  const start = ends.find(end => end.entryId === entryId)?.label ?? "the start"
  const goal = ends.find(end => end.destinationId === destinationId)?.label ?? "the destination"
  const selected = preview.selected
  const exit = ends.find(end => end.destinationId === preview.actual_destination_id)?.label ?? selected?.destination_label ?? "another exit"
  const length = `about ${formatDistance(routeLengthMeters(selected))}`
  const via = passesStudyJunction(selected, context) ? ", through the study junction" : ""
  const closed = closedCount === 1 ? "The closed road does not" : "The closed roads do not"
  switch (preview.outcome) {
    case "unchanged":
      return `A ${vehicle} from ${start} to ${goal}: ${length}${via}.${closedCount ? ` ${closed} change this trip.` : ""}`
    case "detour":
      return `A ${vehicle} from ${start} to ${goal} takes a detour: ${length} instead of ${formatDistance(routeLengthMeters(preview.original))}${via}.`
    case "alternative_exit":
      return `A ${vehicle} from ${start} is sent to ${exit} instead of ${goal}: ${length}${via}.`
    case "waiting_entry":
      return `A ${vehicle} waits outside ${start}, because that road is closed.`
    case "no_route":
      return `A ${vehicle} cannot get from ${start} to ${goal}. ${preview.reason}`
    case "invalid_arrangement":
      return "These closures leave no usable roads. Reopen a road to see a route."
  }
}

const tripAllowed = (pairs: RouteContext["eligible_pairs"], entryId: string, destinationId: string) =>
  pairs.some(pair => pair.entry_id === entryId && pair.destination_id === destinationId)

/** What clicking an end does: fill the active step, then move to the other one. An end that does not fit is ignored. */
export function endAction(end: RouteEnd, picking: EndStep, pairs: RouteContext["eligible_pairs"], entryId: string): { action: EndAction | null; picking: EndStep } {
  if (picking === "start") {
    return end.entryId ? { action: { type: "entry", entryId: end.entryId }, picking: "destination" } : { action: null, picking }
  }
  return end.destinationId && tripAllowed(pairs, entryId, end.destinationId)
    ? { action: { type: "destination", destinationId: end.destinationId }, picking: "start" } : { action: null, picking }
}

export function endRoles(ends: readonly RouteEnd[], picking: EndStep, pairs: RouteContext["eligible_pairs"], entryId: string, destinationId: string) {
  return ends.map((end): { end: RouteEnd; role: EndRole } => {
    if (end.entryId && end.entryId === entryId) return { end, role: "start" }
    if (end.destinationId && end.destinationId === destinationId) return { end, role: "destination" }
    const usable = picking === "start" ? !!end.entryId : !!end.destinationId && tripAllowed(pairs, entryId, end.destinationId)
    return { end, role: usable ? "available" : "unavailable" }
  })
}

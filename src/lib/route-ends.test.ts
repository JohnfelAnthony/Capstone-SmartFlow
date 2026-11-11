import { describe, expect, it } from "vitest"
import type { RouteContext, RoutePath, RoutePreview } from "@/api/routes"
import type { VisualNetwork } from "@/api/visual-network"
import { buildRouteEnds, describeRoad, routeEndsComplete, describeRoute, endAction, endRoles, formatDistance, passesStudyJunction, routeLengthMeters, routeStatus } from "./route-ends"

const lane = (id: string, shape: Array<[number, number]>) => ({ id, shape: shape.map(([x, y]) => ({ x, y })) })
const geometry = {
  junctions: [{ id: "site-a_j", x: 0, y: 0 }],
  roads: [{ lanes: [
    lane("w_in", [[-100, 0], [-20, 0]]), lane("w_out", [[-20, 2], [-100, 2]]),
    lane("hn_in", [[200, -90], [200, -10]]), lane("hn_out", [[205, -10], [205, -88]]),
    lane("s_out", [[0, 10], [0, 150]]),
  ] }],
} as unknown as VisualNetwork
const road = (lane_id: string, label: string) => ({ lane_id, road_id: lane_id, label, direction: "eastbound" })

const context = {
  network_id: "site-a", geometry,
  entries: [
    { id: "b_w", label: "Dao Street (Boundary 1)", lane_ids: ["w_in"] },
    { id: "b_hn_in", label: "Highway (Boundary 4)", lane_ids: ["hn_in"] },
  ],
  destinations: [
    { id: "b_w", label: "Dao Street (Boundary 1)", lane_ids: ["w_out"] },
    { id: "b_hn_out", label: "Highway (Boundary 3)", lane_ids: ["hn_out"] },
    { id: "b_s", label: "Sobrecarey Street (Boundary 2)", lane_ids: ["s_out"] },
  ],
  eligible_pairs: [
    { entry_id: "b_w", destination_id: "b_hn_out" }, { entry_id: "b_w", destination_id: "b_s" },
    { entry_id: "b_hn_in", destination_id: "b_w" }, { entry_id: "b_hn_in", destination_id: "b_s" },
  ],
  roads: [
    road("w_in", "Dao Street · south-east, 0–88 m out"), road("w_out", "Dao Street · south-east, 0–88 m out"),
    road("hn_in", "Davao-Agusan National Highway · north, 0–90 m out"),
    road("hn_out", "Davao-Agusan National Highway · north, 0–90 m out"),
    road("s_out", "Sobrecarey Street · south, 0–140 m out"),
  ],
} as unknown as RouteContext

const path = (destination_label: string, segments: RoutePath["segments"], destination_id = "b_hn_out"): RoutePath =>
  ({ lane_ids: [], destination_id, destination_label, segments })
const straight = path("x", [
  { kind: "lane", lane_id: "a", points: [{ x: 0, y: 0 }, { x: 30, y: 40 }] },
  { kind: "connector", from_lane_id: "a", to_lane_id: "b", points: [{ x: 30, y: 40 }, { x: 30, y: 50 }] },
])

describe("road ends", () => {
  const ends = buildRouteEnds(context)

  it("merges an entry and a destination at the same place into one named end", () => {
    const west = ends.find(end => end.entryId === "b_w")
    expect(west).toMatchObject({ destinationId: "b_w", label: "Dao Street (south-east end)" })
    expect(west!.x).toBeCloseTo(-100, 0)
    const highway = ends.find(end => end.entryId === "b_hn_in")
    expect(highway).toMatchObject({ destinationId: "b_hn_out", label: "Davao-Agusan National Highway (north end)" })
  })

  it("keeps an exit-only end and does not merge ends that are far apart", () => {
    expect(ends).toHaveLength(3)
    expect(ends.find(end => end.destinationId === "b_s")).toMatchObject({ entryId: null, label: "Sobrecarey Street (south end)" })
  })

  it("falls back to the boundary label when a road label has no place", () => {
    const plain = { ...context, roads: [] } as unknown as RouteContext
    expect(buildRouteEnds(plain).find(end => end.entryId === "b_w")!.label).toBe("Dao Street (Boundary 1)")
  })
})

describe("a server that is out of date", () => {
  // Before the "destinations name their lanes" change, the API sent destinations with no lane_ids.
  const stale = {
    ...context,
    destinations: context.destinations.map(({ id, label }) => ({ id, label })),
  } as unknown as RouteContext

  it("does not throw and skips the ends it cannot place", () => {
    const ends = buildRouteEnds(stale)
    expect(ends.map(end => end.entryId)).toEqual(["b_w", "b_hn_in"])
    expect(ends.every(end => end.destinationId === null)).toBe(true)
  })

  it("reports that the ends are incomplete so the page can ask for a restart", () => {
    expect(routeEndsComplete(stale, buildRouteEnds(stale))).toBe(false)
    expect(routeEndsComplete(context, buildRouteEnds(context))).toBe(true)
    const noPlacedEnds = routeEndsComplete(stale, [])
    expect(noPlacedEnds).toBe(false)
    expect(routeEndsComplete({ entries: [], destinations: [] }, [])).toBe(true)
  })
})

describe("road names", () => {
  it("names a road direction by street, part and heading", () => {
    expect(describeRoad({ lane_id: "x", road_id: "x", label: "Dalisay Gante Road · south, 0–145 m out", direction: "southbound" }))
      .toBe("Dalisay Gante Road, south part · southbound")
  })

  it("keeps an unnamed street's label whole", () => {
    expect(describeRoad({ lane_id: "x", road_id: "x", label: "Unnamed road", direction: "northbound" })).toBe("Unnamed road · northbound")
  })
})

describe("route facts", () => {
  it("rounds distances to the nearest 10 m and switches to km from 1000 m", () => {
    expect(formatDistance(424)).toBe("420 m")
    expect(formatDistance(1240)).toBe("1.2 km")
  })

  it("adds lane and junction-connector lengths", () => {
    expect(routeLengthMeters(straight)).toBeCloseTo(60)
    expect(routeLengthMeters(null)).toBe(0)
  })

  it("says whether a route passes through the study junction", () => {
    const near = path("x", [{ kind: "connector", from_lane_id: "a", to_lane_id: "b", points: [{ x: -6, y: 0 }, { x: 6, y: 0 }] }])
    expect(passesStudyJunction(near, context)).toBe(true)
    expect(passesStudyJunction(straight, context)).toBe(false)
    expect(passesStudyJunction(near, { ...context, network_id: "other" } as RouteContext)).toBe(false)
  })
})

const preview = (outcome: RoutePreview["outcome"], parts: Partial<RoutePreview> = {}) => ({
  outcome, original: null, selected: null, reason: "Because.", actual_destination_id: null, ...parts,
}) as RoutePreview
const through = path("Highway", [{ kind: "connector", from_lane_id: "a", to_lane_id: "b", points: [{ x: -5, y: 0 }, { x: 5, y: 0 }] },
  { kind: "lane", lane_id: "b", points: [{ x: 5, y: 0 }, { x: 425, y: 0 }] }])
const input = { vehicle: "car" as const, context, ends: buildRouteEnds(context), entryId: "b_w", destinationId: "b_hn_out" }

describe("plain-language route sentence", () => {
  it("states an unchanged trip with distance and the study junction", () => {
    const text = describeRoute({ ...input, closedCount: 0, preview: preview("unchanged", { original: through, selected: through, actual_destination_id: "b_hn_out" }) })
    expect(text).toBe("A car from Dao Street (south-east end) to Davao-Agusan National Highway (north end): about 430 m, through the study junction.")
  })

  it("adds that a closed road does not change an unchanged trip", () => {
    const text = describeRoute({ ...input, closedCount: 1, preview: preview("unchanged", { original: through, selected: through }) })
    expect(text).toContain("The closed road does not change this trip.")
  })

  it("compares a detour with the original route", () => {
    const longer = path("Highway", [{ kind: "lane", lane_id: "b", points: [{ x: 0, y: 0 }, { x: 900, y: 0 }] }])
    const text = describeRoute({ ...input, closedCount: 1, preview: preview("detour", { original: through, selected: longer }) })
    expect(text).toContain("takes a detour")
    expect(text).toContain("about 900 m instead of 430 m")
  })

  it("names the exit used instead when the destination cannot be reached", () => {
    const other = path("Sobrecarey", [{ kind: "lane", lane_id: "s", points: [{ x: 0, y: 0 }, { x: 100, y: 0 }] }], "b_s")
    const text = describeRoute({ ...input, closedCount: 1, preview: preview("alternative_exit", { original: through, selected: other, actual_destination_id: "b_s" }) })
    expect(text).toContain("is sent to Sobrecarey Street (south end) instead of Davao-Agusan National Highway (north end): about 100 m")
  })

  it("explains waiting, no route and an unusable arrangement without a distance", () => {
    expect(describeRoute({ ...input, closedCount: 1, preview: preview("waiting_entry") })).toMatch(/waits outside .*closed/)
    expect(describeRoute({ ...input, closedCount: 0, preview: preview("no_route", { reason: "Buses cannot use Sobrecarey Street." }) })).toContain("Buses cannot use Sobrecarey Street.")
    expect(describeRoute({ ...input, closedCount: 3, preview: preview("invalid_arrangement") })).toContain("Reopen a road")
  })

  it("uses kilometres from 1000 m and the vehicle's own name", () => {
    const far = path("Highway", [{ kind: "lane", lane_id: "b", points: [{ x: 0, y: 0 }, { x: 1240, y: 0 }] }])
    const text = describeRoute({ ...input, vehicle: "bus", closedCount: 0, preview: preview("unchanged", { original: far, selected: far }) })
    expect(text).toContain("A bus from")
    expect(text).toContain("about 1.2 km")
  })

  it("gives a short status word for the strip", () => {
    expect(routeStatus(null)).toBe("Choose a trip")
    expect(routeStatus(preview("detour"))).toBe("Detour")
    expect(routeStatus(preview("alternative_exit"))).toBe("Other exit")
  })
})

describe("clicking a road end", () => {
  const ends = buildRouteEnds(context)
  const west = ends.find(end => end.entryId === "b_w")!
  const highway = ends.find(end => end.entryId === "b_hn_in")!
  const south = ends.find(end => end.entryId === null)!
  const pairs = context.eligible_pairs

  it("sets the start first, then moves on to the destination", () => {
    expect(endAction(highway, "start", pairs, "b_w")).toEqual({ action: { type: "entry", entryId: "b_hn_in" }, picking: "destination" })
  })

  it("sets the destination only if the trip is allowed, then returns to the start step", () => {
    expect(endAction(south, "destination", pairs, "b_w")).toEqual({ action: { type: "destination", destinationId: "b_s" }, picking: "start" })
    expect(endAction(west, "destination", pairs, "b_w")).toEqual({ action: null, picking: "destination" })
  })

  it("ignores an end that cannot be a start", () => {
    expect(endAction(south, "start", pairs, "b_w")).toEqual({ action: null, picking: "start" })
  })

  const roleOf = (picking: "start" | "destination", entryId: string, destinationId: string, end: typeof west, trips = pairs) =>
    endRoles(ends, picking, trips, entryId, destinationId).find(item => item.end === end)!.role

  it("marks the chosen start and destination whichever step is active", () => {
    for (const picking of ["start", "destination"] as const) {
      expect(roleOf(picking, "b_w", "b_s", west)).toBe("start")
      expect(roleOf(picking, "b_w", "b_s", south)).toBe("destination")
    }
  })

  it("leaves other ends available, and dims those the active step cannot use", () => {
    expect(roleOf("start", "b_w", "b_s", highway)).toBe("available")
    expect(roleOf("start", "b_hn_in", "b_w", south)).toBe("unavailable")
    const onlyHighway = [{ entry_id: "b_w", destination_id: "b_hn_out" }]
    expect(roleOf("destination", "b_w", "b_hn_out", south, onlyHighway)).toBe("unavailable")
    expect(roleOf("destination", "b_hn_in", "b_w", west, pairs)).toBe("destination")
  })
})

import { describe, expect, it } from "vitest"
import type { RoutePath } from "@/api/routes"
import { fitMap, mapToScreen } from "@/simulation/map-navigation"
import { pickPlannerLane, plannerFitBounds, plannerPathLines, type PlannerOverlay } from "@/simulation/route-planner-overlay"
import type { SceneLane } from "@/simulation/scene-geometry"

const bounds = { min_x: -100, min_y: -70, max_x: 300, max_y: 80 }
const empty: PlannerOverlay = { original: null, selected: null, sharedRoads: [], closedLaneIds: [], selectedLaneId: null }

function lane(id: string, y: number, reversed = false): SceneLane {
  const line = [{ x: 0, y }, { x: 100, y }]
  return { id, kind: "road", width: 4, laneCount: 1, dividers: [], centreLine: null,
    centerline: reversed ? line.reverse() : line, length: 100, junctionIds: [],
    polygon: [{ x: 0, y: y - 2 }, { x: 100, y: y - 2 }, { x: 100, y: y + 2 }, { x: 0, y: y + 2 }] }
}

function route(y: number): RoutePath {
  return {
    lane_ids: ["east", "next"], destination_id: "end", destination_label: "End",
    segments: [
      { kind: "lane", lane_id: "east", points: [{ x: 0, y }, { x: 40, y }] },
      { kind: "connector", from_lane_id: "east", to_lane_id: "next", points: [{ x: 40, y }, { x: 50, y }] },
      { kind: "lane", lane_id: "next", points: [{ x: 65, y }, { x: 100, y }] },
    ],
  }
}

describe("planner overlay geometry", () => {
  it("picks the clicked directional lane in world coordinates at different screen sizes", () => {
    const roads = [lane("east", 4), lane("west", 0, true)]
    for (const camera of [fitMap(bounds, 360, 250), fitMap(bounds, 1200, 800)]) {
      expect(pickPlannerLane(roads, mapToScreen({ x: 38, y: 4 }, camera), camera)).toBe("east")
      expect(pickPlannerLane(roads, mapToScreen({ x: 38, y: 0 }, camera), camera)).toBe("west")
      expect(pickPlannerLane(roads, mapToScreen({ x: 38, y: 10 }, camera), camera)).toBeNull()
    }
  })

  it("includes both derived shared directions in the route fit", () => {
    const fit = plannerFitBounds(bounds, { ...empty, selected: route(3), sharedRoads: [
      { road_id: "r", shared_lane: "east", kept_lane: "west", width: 3,
        lanes: { east: [[0, 4], [155, 4]], west: [[155, 7], [0, 7]] } },
    ] })
    expect(fit.max_x).toBeGreaterThan(155)
    expect(fit.max_x).toBeLessThan(bounds.max_x)
    expect(fit.max_y).toBeGreaterThan(7)
  })

  it("falls back to whole-network bounds if no routes are available", () => {
    expect(plannerFitBounds(bounds, empty)).toBe(bounds)
  })

  it("keeps both sets of points when shared geometry keeps the same lane IDs", () => {
    const original = route(3), selected = route(7)
    expect(original.lane_ids).toEqual(selected.lane_ids)
    expect(plannerPathLines(original)).not.toEqual(plannerPathLines(selected))
    const lines = plannerPathLines(selected)
    expect(lines).toHaveLength(3)
    expect(lines[1].at(-1)).toEqual({ x: 50, y: 7 })
    expect(lines[2][0]).toEqual({ x: 65, y: 7 })
  })
})

import type { VisualNetwork } from "@/api/visual-network"
export const bentNetwork = {
  version: 2, network_id: "synthetic-test", source_net: "Synthetic geometry fixture",
  scope: { mode: "connected-network" },
  bounds: { min_x: -200, max_x: 220, min_y: -200, max_y: 220 },
  roads: [{ index: 0, function: "normal", toward_intersection: true, away_from_intersection: true,
    shape: [{ x: -150, y: 0 }, { x: -60, y: 0 }, { x: -12, y: 4 }],
    lanes: [{ id: "lane-west", index: 0, width: 3.3, allow: "passenger", disallow: "",
      source_length: 138, clip_start_position: 0, clip_end_position: 138,
      shape: [{ x: -150, y: 0 }, { x: -60, y: 0 }, { x: -12, y: 4 }] }] }],
  internal_lanes: [], crossings: [], walking_areas: [], polygons: [],
  signals: [{ id: "J1", kind: "traffic_light", x: 0, y: 0,
    shape: [{ x: -12, y: -8 }, { x: 12, y: -8 }, { x: 12, y: 8 }, { x: -12, y: 8 }] }],
  signal_groups: [{ id: "lane-west", signal_id: "lane-west", lane_id: "lane-west",
    from_edge_id: "road-west", kind: "vehicle", width: 3.3, heading: 0,
    anchor: { x: -12, y: 4 }, stop_line: [{ x: -12, y: 2.35 }, { x: -12, y: 5.65 }],
    link_indices: [0], via_lane_ids: [] }],
} satisfies VisualNetwork & { network_id: string }

/** A native-style four-way junction at the origin: two 3.3 m carriageways per arm meeting 9 m from the centre, right-hand traffic. */
export function crossNetwork(armLength = 60): VisualNetwork & { network_id: string } {
  const arms = { east: { x: 1, y: 0 }, north: { x: 0, y: 1 }, west: { x: -1, y: 0 }, south: { x: 0, y: -1 } }
  const lane = (id: string, shape: { x: number; y: number }[]) => ({ index: 0, function: "normal", toward_intersection: true, away_from_intersection: true, shape,
    lanes: [{ id, index: 0, width: 3.3, lane_count: 1, allow: "passenger", disallow: "", source_length: armLength - 9, clip_start_position: 0, clip_end_position: armLength - 9, shape }] })
  const roads = Object.entries(arms).flatMap(([name, out]) => {
    const inRight = { x: -out.y, y: out.x } // right of travel toward the junction (direction -out)
    const at = (distance: number, side: number) => ({ x: out.x * distance + inRight.x * side * 1.65, y: out.y * distance + inRight.y * side * 1.65 })
    return [lane(`${name}-in`, [at(armLength, 1), at(9, 1)]), lane(`${name}-out`, [at(9, -1), at(armLength, -1)])]
  })
  const signalGroups = Object.entries(arms).map(([name, out]) => {
    const inRight = { x: -out.y, y: out.x }, anchor = { x: out.x * 9 + inRight.x * 1.65, y: out.y * 9 + inRight.y * 1.65 }
    return { id: `${name}-in`, signal_id: `${name}-in`, lane_id: `${name}-in`, from_edge_id: `${name}-in`, kind: "vehicle" as const, width: 3.3,
      heading: Math.atan2(-out.y, -out.x) * 180 / Math.PI, anchor,
      stop_line: [{ x: anchor.x + inRight.x * 1.65, y: anchor.y + inRight.y * 1.65 }, { x: anchor.x - inRight.x * 1.65, y: anchor.y - inRight.y * 1.65 }], link_indices: [0], via_lane_ids: [] }
  })
  return {
    version: 2, network_id: "synthetic-cross", source_net: "Synthetic four-way fixture", scope: { mode: "connected-network" },
    bounds: { min_x: -armLength - 20, max_x: armLength + 20, min_y: -armLength - 20, max_y: armLength + 20 },
    roads, internal_lanes: [], crossings: [], walking_areas: [], polygons: [],
    signals: [{ id: "J", kind: "traffic_light", x: 0, y: 0, shape: [{ x: -9, y: -9 }, { x: 9, y: -9 }, { x: 9, y: 9 }, { x: -9, y: 9 }] }],
    signal_groups: signalGroups,
  }
}



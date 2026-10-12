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



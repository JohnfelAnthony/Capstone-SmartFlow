import { apiRequest } from "@/api/client"

export type VisualPoint = {
  x: number
  y: number
}

export type VisualLane = {
  id: string
  index: number
  width: number
  allow: string
  disallow: string
  source_length: number
  clip_start_position: number
  clip_end_position: number
  shape: VisualPoint[]
}

export type VisualRoad = {
  index: number
  function: string
  toward_intersection: boolean
  away_from_intersection: boolean
  shape: VisualPoint[]
  lanes: VisualLane[]
}

export type VisualSignal = {
  id: string
  kind: string
  x: number
  y: number
  shape: VisualPoint[]
}

export type VisualSignalGroup = {
  id: string
  signal_id: string
  lane_id: string
  from_edge_id: string
  kind: "vehicle" | "pedestrian"
  width: number
  heading: number
  anchor: VisualPoint
  stop_line: VisualPoint[]
  link_indices: number[]
  via_lane_ids: string[]
}

export type VisualPolygon = {
  id: string
  color: string
  fill: boolean
  layer: number
  shape: VisualPoint[]
}

export type VisualNetwork = {
  version: number
  source_net: string
  scope: {
    mode: string
  }
  bounds: {
    min_x: number
    min_y: number
    max_x: number
    max_y: number
  }
  roads: VisualRoad[]
  internal_lanes: VisualRoad[]
  crossings: VisualRoad[]
  walking_areas: VisualRoad[]
  signals: VisualSignal[]
  signal_groups: VisualSignalGroup[]
  polygons: VisualPolygon[]
}

export function getVisualNetwork(intersectionId?: string | null) {
  const query = intersectionId ? `?intersection_id=${encodeURIComponent(intersectionId)}` : ""
  return apiRequest<VisualNetwork>(`/api/visual-network${query}`)
}

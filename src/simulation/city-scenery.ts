import type { VisualPoint } from "@/api/visual-network"
import { distanceToPolyline, offsetLine, pointInPolygon, type SceneGeometry } from "@/simulation/scene-geometry"

/**
 * Illustrative city scenery for the 2D map. None of it is surveyed Tagum context: blocks, parks, parking and
 * trees are generated deterministically in the space the engine's roads leave free, and are never pickable.
 */
export const STREET_EDGE = { sidewalk: 3, verge: 1.2 }
/** Paving under the engine's illustrative pedestrian path, so people never wait inside a block. */
export const WALKWAY_HALF_WIDTH = 1.1
const CELL = 6, LOT = 3, REGION = 6, LOT_MARGIN = 1.5

export type SceneryRoof = "flat" | "hip" | "light" | "terrace"
export type SceneryItem =
  | { kind: "building"; corners: VisualPoint[]; center: VisualPoint; angle: number; width: number; depth: number; roof: SceneryRoof; tone: number }
  | { kind: "lawn" | "parking" | "plaza"; corners: VisualPoint[]; center: VisualPoint; angle: number }
  | { kind: "tree"; center: VisualPoint; radius: number; tone: number }

function stableHash(value: string) {
  let hash = 2166136261
  for (const character of value) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619)
  return hash >>> 0
}

/** Road grid direction (mod 90°), so lots line up with the streets. */
function dominantAngle(geometry: SceneGeometry) {
  let x = 0, y = 0
  for (const lane of geometry.lanes) if (lane.kind === "road") for (let index = 1; index < lane.centerline.length; index++) {
    const a = lane.centerline[index - 1], b = lane.centerline[index], length = Math.hypot(b.x - a.x, b.y - a.y), angle = Math.atan2(b.y - a.y, b.x - a.x)
    x += length * Math.cos(4 * angle); y += length * Math.sin(4 * angle)
  }
  return Math.atan2(y, x) / 4
}

/** Metres from the nearest engine pavement (negative inside it); a pedestrian walkway counts as sidewalk. */
export function sceneryClearance(geometry: SceneGeometry, walkways: readonly VisualPoint[][]) {
  const roads = geometry.lanes.filter((lane) => lane.kind === "road"), rings = geometry.junctions.map((junction) => [...junction.kerb, junction.kerb[0]])
  return (point: VisualPoint) => {
    let clearance = Infinity
    for (const lane of roads) clearance = Math.min(clearance, distanceToPolyline(point, lane.centerline) - lane.width / 2)
    for (const ring of rings) {
      if (pointInPolygon(point, ring)) return -1
      clearance = Math.min(clearance, distanceToPolyline(point, ring))
    }
    for (const walkway of walkways) clearance = Math.min(clearance, distanceToPolyline(point, walkway) - WALKWAY_HALF_WIDTH + STREET_EDGE.sidewalk + STREET_EDGE.verge)
    return clearance
  }
}

/** The engine's illustrative pedestrian paths that can be drawn as walkways. */
export function pedestrianWalkways(paths: readonly { shape: VisualPoint[] }[]) {
  return paths.map((path) => path.shape).filter((shape) => shape.length > 1)
}

/** Planting strip behind each kerb's sidewalk; it stops at the carriageway end, leaving corners open. */
export function vergeLines(geometry: SceneGeometry): VisualPoint[][] {
  const reach = STREET_EDGE.sidewalk + STREET_EDGE.verge / 2
  return geometry.lanes.filter((lane) => lane.kind === "road" && lane.centerline.length > 1)
    .flatMap((lane) => (lane.centreLine ? [-1] : [-1, 1]).map((side) => offsetLine(lane.centerline, side * (lane.width / 2 + reach))))
}

export function cityScenery(geometry: SceneGeometry, walkways: readonly VisualPoint[][] = []): SceneryItem[] {
  const angle = dominantAngle(geometry), along = { x: Math.cos(angle), y: Math.sin(angle) }, across = { x: -along.y, y: along.x }
  const origin = geometry.junctions[0]?.center ?? { x: (geometry.bounds.min_x + geometry.bounds.max_x) / 2, y: (geometry.bounds.min_y + geometry.bounds.max_y) / 2 }
  const toMap = (u: number, v: number) => ({ x: origin.x + along.x * u + across.x * v, y: origin.y + along.y * u + across.y * v })
  const rectangle = (u: number, v: number, width: number, depth: number) => [toMap(u - width / 2, v - depth / 2), toMap(u + width / 2, v - depth / 2), toMap(u + width / 2, v + depth / 2), toMap(u - width / 2, v + depth / 2)]
  const edge = STREET_EDGE.sidewalk + STREET_EDGE.verge + LOT_MARGIN, clearance = sceneryClearance(geometry, walkways)
  const clear = (u: number, v: number, halfU: number, halfV = halfU) => [[0, 0], [-1, -1], [1, -1], [1, 1], [-1, 1], [0, -1], [0, 1], [-1, 0], [1, 0]].every(([du, dv]) => clearance(toMap(u + du * halfU, v + dv * halfV)) >= edge)
  const tree = (u: number, v: number, key: string, chance: number) => {
    const hash = stableHash(key)
    if (hash % chance === 0 && clear(u, v, 1.5)) trees.push({ kind: "tree", center: toMap(u + ((hash >>> 3) % 5 - 2) * .4, v + ((hash >>> 6) % 5 - 2) * .4), radius: 1.8 + (hash % 4) * .35, tone: (hash >>> 9) % 3 })
  }

  // Cover the network bounds in the rotated lattice frame.
  const corners = [[geometry.bounds.min_x, geometry.bounds.min_y], [geometry.bounds.max_x, geometry.bounds.min_y], [geometry.bounds.max_x, geometry.bounds.max_y], [geometry.bounds.min_x, geometry.bounds.max_y]]
    .map(([x, y]) => ({ u: (x - origin.x) * along.x + (y - origin.y) * along.y, v: (x - origin.x) * across.x + (y - origin.y) * across.y }))
  const range = (values: number[]) => [Math.floor(Math.min(...values) / CELL / LOT) * LOT, Math.ceil(Math.max(...values) / CELL)]
  const [minI, maxI] = range(corners.map((corner) => corner.u)), [minJ, maxJ] = range(corners.map((corner) => corner.v))
  const items: SceneryItem[] = [], trees: SceneryItem[] = []
  const themes = ["buildings", "buildings", "buildings", "buildings", "park", "park", "parking", "plaza", "plaza"] as const
  const theme = (i: number, j: number) => themes[stableHash(`${geometry.networkId}:${Math.floor(i / REGION)}:${Math.floor(j / REGION)}`) % themes.length]
  const roofs: SceneryRoof[] = ["flat", "hip", "light", "terrace", "flat", "hip"]

  for (let i = minI; i <= maxI; i++) for (let j = minJ; j <= maxJ; j++) {
    const u = (i + 0.5) * CELL, v = (j + 0.5) * CELL, kind = theme(i, j)
    if (kind === "buildings") {
      // One lot per 3 x 3 cells, considered once from its corner cell.
      if (((i % LOT) + LOT) % LOT !== 0 || ((j % LOT) + LOT) % LOT !== 0) continue
      const lotU = (i + LOT / 2) * CELL, lotV = (j + LOT / 2) * CELL, hash = stableHash(`${i}:${j}`)
      const width = 11.5 + (hash % 5) * 1.1, depth = 10.5 + ((hash >>> 4) % 5) * 1.1
      const fits = clear(lotU, lotV, width / 2, depth / 2) ? 1 : clear(lotU, lotV, width / 3, depth / 3) ? 2 / 3 : 0
      if (fits) items.push({ kind: "building", corners: rectangle(lotU, lotV, width * fits, depth * fits), center: toMap(lotU, lotV), angle, width: width * fits, depth: depth * fits, roof: roofs[(hash >>> 8) % roofs.length], tone: (hash >>> 12) % 4 })
      else for (const [du, dv] of [[-1, -1], [1, 1], [1, -1], [-1, 1]]) tree(lotU + du * CELL * .6, lotV + dv * CELL * .6, `t${i}:${j}:${du}:${dv}`, 2)
    } else if (clear(u, v, CELL / 2)) {
      items.push({ kind: kind === "park" ? "lawn" : kind, corners: rectangle(u, v, CELL, CELL), center: toMap(u, v), angle })
      if (kind !== "parking") tree(u, v, `c${i}:${j}`, kind === "park" ? 3 : 7)
    }
  }
  return [...items, ...trees, ...streetTrees(geometry, clearance)]
}

/** A tree row along every verge, kept clear of junction corners and of other streets. */
function streetTrees(geometry: SceneGeometry, clearance: (point: VisualPoint) => number): SceneryItem[] {
  const trees: SceneryItem[] = [], vergeMiddle = STREET_EDGE.sidewalk + STREET_EDGE.verge / 2
  for (const [lineIndex, line] of vergeLines(geometry).entries()) {
    for (let index = 1; index < line.length; index++) {
      const a = line[index - 1], b = line[index], length = Math.hypot(b.x - a.x, b.y - a.y)
      for (let distance = 6; distance < length - 6; distance += 12) {
        const center = { x: a.x + (b.x - a.x) * distance / length, y: a.y + (b.y - a.y) * distance / length }, hash = stableHash(`${lineIndex}:${index}:${distance}`)
        const nearJunction = geometry.junctions.some((junction) => Math.hypot(center.x - junction.center.x, center.y - junction.center.y) < 18)
        if (hash % 4 === 0 || nearJunction || clearance(center) < vergeMiddle - 0.01) continue
        trees.push({ kind: "tree", center, radius: 1.5 + (hash % 3) * .25, tone: hash % 3 })
      }
    }
  }
  return trees
}

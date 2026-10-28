import * as React from "react"
import { LocateFixed, Minus, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { VisualPoint } from "@/api/visual-network"
import type { RenderFrame, RenderPedestrian, RenderVehicle } from "@/simulation/frame-types"
import { cityScenery, pedestrianWalkways, STREET_EDGE, vergeLines, WALKWAY_HALF_WIDTH, type SceneryItem } from "@/simulation/city-scenery"
import { boundsForJunction, headingToCanvasRotation, normalizeVehicleClass, pickSceneEntity, SCENE_PALETTE as palette, signalAppearance, signalHeadPlacement, walkSignalState, type SceneGeometry, type SceneSignalGroup, type Selection, type SignalColor, type WalkSignal } from "@/simulation/scene-geometry"
import type { PresentationState } from "@/simulation/presentation-state"
import { junctionTagText } from "@/simulation/scene-summary"
import { boundMapPan, claimMapLabel, createMapInterpolator, fitMap as fit, mapScale, mapToScreen as screen, resizeMap, screenToMap, zoomMapAt, type LabelRect, type MapCamera as Transform } from "@/simulation/map-navigation"

type Props = { frame: RenderFrame | null; geometry: SceneGeometry; presentation: PresentationState; onSelect: (selection: Selection | null) => void; runKey?: string; onPerformanceSample?: (sample: { fps: number; p95FrameMs: number; drawCalls: number }) => void }
type Theme = "light" | "dark"
/** Flat city-illustration palettes. Scenery stays muted so traffic and signals carry the contrast. */
const CITY = {
  light: {
    ground: "#C8CCCE", plaza: "#D3D6D5", sidewalk: "#DEE0DF", kerb: "#F4F4F0", verge: "#80B36D", lawn: "#8FC27D", parking: "#7B8087", stall: "#E9EAE5",
    asphalt: "#6C7178", marking: "#F7F7F2", centre: "#F3C54F", roofs: [["#60666E", "#747A82"], ["#D8C29C", "#C3AC84"], ["#EEEEEA", "#D5D6D2"], ["#8E98A4", "#7A8591"]],
    fixture: "#D8DBDE", shadow: "rgba(38,46,54,.2)", trees: ["#3F8F4F", "#4FA05B", "#37804A"], highlight: "rgba(255,255,255,.2)", glass: "#2C3B4B",
    housing: "#20252B", rim: "#59616A", arm: "#4A5159", glow: .45, chip: "rgba(250,252,248,.96)", chipText: "#2D493D", chipBorder: "rgba(63,87,74,.14)",
  },
  dark: {
    ground: "#252A31", plaza: "#2B3038", sidewalk: "#363C44", kerb: "#47515A", verge: "#2C5539", lawn: "#30593D", parking: "#20242A", stall: "#7E838A",
    asphalt: "#1D2126", marking: "#C9CCC7", centre: "#C9A13F", roofs: [["#3A3F47", "#444A51"], ["#58513F", "#4A4436"], ["#51565C", "#454A50"], ["#3D4650", "#353D46"]],
    fixture: "#5A6068", shadow: "rgba(0,0,0,.34)", trees: ["#244F36", "#2C5C3F", "#1E4630"], highlight: "rgba(255,255,255,.08)", glass: "#18212B",
    housing: "#0F1215", rim: "#59616A", arm: "#5C646D", glow: .8, chip: "rgba(30,36,42,.94)", chipText: "#DCE6E0", chipBorder: "rgba(255,255,255,.12)",
  },
}
type Palette = (typeof CITY)[Theme]
const FLEET = {
  cars: ["#F2B632", "#E2483D", "#3D7BE0", "#F2F3F5", "#2F3E66", "#F08A3C", "#8E5CC9", "#C3C9D1", "#3FA66B", "#2A2E34"], buses: ["#F2F3F5", "#2F80C9", "#E2533F"],
  tricycle: "#3FA34D", tricycleRoof: "#2F8A3C", cargo: "#DADDE1", rib: "#BBC0C6", tyre: "#1C2025", headlight: "#FFF2C2", brake: "#FF4D4D", tail: "#9C3B3B",
  people: ["#E85D75", "#3D7BE0", "#F2B632", "#3FA66B", "#8E5CC9", "#F08A3C", "#F2F3F5"], hair: "#2B2320", walk: "#E9FFF1", hand: "#FF7A2F",
}
const LAMPS: Record<Exclude<SignalColor, "off">, [lit: string, dim: string]> = { red: ["#FF4B4B", "#4A2525"], yellow: ["#FFC93D", "#4A3D20"], green: ["#36E07A", "#1D3D2A"] }
const geometryPaths = new WeakMap<VisualPoint[], { open: Path2D; closed: Path2D }>()
const occupiedLabels = new WeakMap<CanvasRenderingContext2D, LabelRect[]>()
/** Screen rectangles of the drawn junction tags, so a click on a tag selects its junction. */
const junctionTags = new WeakMap<CanvasRenderingContext2D, Array<{ id: string; rect: LabelRect }>>()
/** Cache immutable native paths once; camera movement only changes the canvas matrix. */
function path(ctx: CanvasRenderingContext2D, points: VisualPoint[], transform: Transform, fill?: string, stroke?: string, width = 1, dashed = false, dashMetres?: [number, number]) {
  if (points.length < 2) return
  let paths = geometryPaths.get(points)
  if (!paths) {
    const open = new Path2D(); points.forEach((point, index) => { if (index === 0) open.moveTo(point.x, point.y); else open.lineTo(point.x, point.y) })
    const closed = new Path2D(open); closed.closePath(); paths = { open, closed }; geometryPaths.set(points, paths)
  }
  ctx.save(); ctx.translate(transform.ox, transform.oy); ctx.scale(transform.scale, -transform.scale)
  if (fill) { ctx.fillStyle = fill; ctx.fill(paths.closed) }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = width / transform.scale; ctx.lineCap = "butt"; ctx.lineJoin = "round"; ctx.setLineDash(dashMetres ?? (dashed ? [5 / transform.scale, 5 / transform.scale] : [])); ctx.stroke(fill ? paths.closed : paths.open) }
  ctx.restore()
}
function label(ctx: CanvasRenderingContext2D, text: string, point: VisualPoint | undefined, transform: Transform, colors: Palette, offset = 0, highlighted = false, align: "center" | "left" | "right" = "center") {
  if (!point) return
  const p = screen(point, transform)
  ctx.font = "600 11px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle"
  const width = ctx.measureText(text).width + 18, height = 23, occupied = occupiedLabels.get(ctx) ?? [], left = align === "left" ? p.x : align === "right" ? p.x - width : p.x - width / 2
  const rect = claimMapLabel([offset, offset - 28, offset + 28].map((dy) => ({ x: left, y: p.y + dy - height / 2, width, height })), occupied, transform.width, transform.height)
  if (!rect) return
  ctx.beginPath(); ctx.roundRect(rect.x, rect.y, width, height, 7); ctx.fillStyle = highlighted ? "#1F7A5A" : colors.chip; ctx.fill(); ctx.strokeStyle = highlighted ? "#1F7A5A" : colors.chipBorder; ctx.lineWidth = 1; ctx.stroke()
  ctx.fillStyle = highlighted ? "#FFFFFF" : colors.chipText; ctx.fillText(text, rect.x + width / 2, rect.y + height / 2)
  return rect
}
function stableIndex(id: string, count: number) { let hash = 0; for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0; return (hash >>> 0) % count }
function roundedBox(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, fill: string, radius = 0) {
  ctx.fillStyle = fill; ctx.beginPath(); ctx.roundRect(x, y, width, height, Math.max(0, Math.min(radius, width / 2, height / 2))); ctx.fill()
}
/** A band across the body from x0 to x1, half-widths w0 and w1: windscreens and rear windows. */
function band(ctx: CanvasRenderingContext2D, x0: number, half0: number, x1: number, half1: number, fill: string) {
  ctx.fillStyle = fill; ctx.beginPath(); ctx.moveTo(x0, -half0); ctx.lineTo(x1, -half1); ctx.lineTo(x1, half1); ctx.lineTo(x0, half0); ctx.closePath(); ctx.fill()
}
/** Top-down sprite at the engine pose and dimensions; +x is the front, +y the vehicle's right. */
function drawVehicle(ctx: CanvasRenderingContext2D, vehicle: RenderVehicle, transform: Transform, selected: boolean, colors: Palette) {
  const p = screen(vehicle, transform), length = Math.max(4, vehicle.length * transform.scale), width = Math.max(2, vehicle.width * transform.scale)
  const type = normalizeVehicleClass(vehicle.visual_type), rotation = headingToCanvasRotation(vehicle.angle), detailed = length >= 9
  const pick = <T,>(values: readonly T[]) => values[stableIndex(vehicle.id, values.length)]
  ctx.save(); ctx.translate(p.x + 1, p.y + 1.4); ctx.rotate(rotation)
  roundedBox(ctx, -length / 2, -width / 2 * (type === "motorcycle" ? .6 : 1), length, width * (type === "motorcycle" ? .6 : 1), colors.shadow, width * .3); ctx.restore()
  ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(rotation)
  if (type === "motorcycle") {
    roundedBox(ctx, -length * .5, -width * .13, length * .26, width * .26, FLEET.tyre, width * .13); roundedBox(ctx, length * .24, -width * .13, length * .26, width * .26, FLEET.tyre, width * .13)
    roundedBox(ctx, -length * .3, -width * .24, length * .62, width * .48, pick(FLEET.cars), width * .2)
    if (detailed) roundedBox(ctx, length * .2, -width * .5, length * .05, width, FLEET.tyre)
    ctx.fillStyle = pick(FLEET.people); ctx.beginPath(); ctx.ellipse(-length * .07, 0, length * .12, width * .44, 0, 0, Math.PI * 2); ctx.fill()
    ctx.fillStyle = FLEET.hair; ctx.beginPath(); ctx.arc(length * .01, 0, width * .22, 0, Math.PI * 2); ctx.fill()
  } else if (type === "tricycle") {
    // Tagum tricycle: motorcycle nose on the left, one green roof over rider and sidecar.
    roundedBox(ctx, length * .3, -width * .4, length * .2, width * .18, FLEET.tyre, width * .09)
    roundedBox(ctx, -length * .5, -width / 2, length * .82, width, FLEET.tricycle, width * .2)
    if (detailed) { roundedBox(ctx, -length * .44, -width * .4, length * .6, width * .8, FLEET.tricycleRoof, width * .14); roundedBox(ctx, -length * .44, -width * .4, length * .6, width * .18, colors.highlight, width * .08); band(ctx, length * .18, width * .42, length * .3, width * .36, colors.glass) }
  } else if (type === "bus") {
    roundedBox(ctx, -length / 2, -width / 2, length, width, pick(FLEET.buses), width * .16)
    if (detailed) {
      roundedBox(ctx, -length * .46, -width * .5, length * .88, width * .09, colors.glass); roundedBox(ctx, -length * .46, width * .41, length * .88, width * .09, colors.glass)
      roundedBox(ctx, -length * .45, -width * .34, length * .86, width * .68, colors.highlight, width * .1)
      roundedBox(ctx, -length * .22, -width * .22, length * .12, width * .44, CITY.light.fixture, 1); roundedBox(ctx, length * .08, -width * .22, length * .12, width * .44, CITY.light.fixture, 1)
      band(ctx, length * .43, width * .44, length * .49, width * .4, colors.glass)
    }
  } else if (type === "truck") {
    roundedBox(ctx, -length * .5, -width * .5, length * .74, width, FLEET.cargo, width * .06)
    if (detailed) for (let rib = 1; rib < 6; rib++) roundedBox(ctx, -length * .5 + rib * length * .74 / 6 - .5, -width * .5, 1, width, FLEET.rib)
    roundedBox(ctx, length * .27, -width * .46, length * .23, width * .92, pick(FLEET.cars), width * .2)
    if (detailed) band(ctx, length * .4, width * .42, length * .47, width * .37, colors.glass)
  } else {
    roundedBox(ctx, -length / 2, -width / 2, length, width, pick(FLEET.cars), Math.min(width * .32, length * .2))
    band(ctx, length * .08, width * .42, length * .26, width * .36, colors.glass)
    if (detailed) { band(ctx, -length * .32, width * .37, -length * .2, width * .42, colors.glass); roundedBox(ctx, -length * .2, -width * .4, length * .28, width * .8, colors.highlight, width * .12) }
  }
  if (width > 4.5 && type !== "motorcycle") {
    const lamp = Math.max(1, length * .045)
    roundedBox(ctx, length * .5 - lamp, -width * .42, lamp, width * .18, FLEET.headlight); roundedBox(ctx, length * .5 - lamp, width * .24, lamp, width * .18, FLEET.headlight)
    roundedBox(ctx, -length * .5, -width * .42, lamp, width * .18, vehicle.stopped ? FLEET.brake : FLEET.tail); roundedBox(ctx, -length * .5, width * .24, lamp, width * .18, vehicle.stopped ? FLEET.brake : FLEET.tail)
  }
  if (selected) { ctx.strokeStyle = palette.selected; ctx.lineWidth = 2; ctx.strokeRect(-length / 2 - 3, -width / 2 - 3, length + 6, width + 6) }
  ctx.restore()
}
/** A small figure seen from above: shoulders across the walking direction, head on top. */
function drawPedestrian(ctx: CanvasRenderingContext2D, person: RenderPedestrian, heading: number, transform: Transform, highlighted: boolean, colors: Palette) {
  const p = screen(person, transform), shoulders = Math.max(5, .56 * transform.scale), depth = Math.max(3, .3 * transform.scale), head = Math.max(1.6, .13 * transform.scale)
  ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(heading)
  ctx.fillStyle = colors.shadow; ctx.beginPath(); ctx.ellipse(1, 1.2, depth / 2, shoulders / 2, 0, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = FLEET.people[stableIndex(person.id, FLEET.people.length)]; ctx.beginPath(); ctx.ellipse(0, 0, depth / 2, shoulders / 2, 0, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = FLEET.hair; ctx.beginPath(); ctx.arc(0, 0, head, 0, Math.PI * 2); ctx.fill()
  if (highlighted) { ctx.strokeStyle = palette.selected; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(0, 0, shoulders / 2 + 2, 0, Math.PI * 2); ctx.stroke() }
  ctx.restore()
}
/** Mast-arm head over the stop line; lamps run red-yellow-green from the drivers' left and face oncoming traffic. */
function drawSignalHead(ctx: CanvasRenderingContext2D, group: SceneSignalGroup, color: SignalColor, transform: Transform, colors: Palette) {
  const placement = signalHeadPlacement(group), scale = transform.scale, head = screen(placement.head, transform), pole = screen(placement.pole, transform)
  // Screen y points down, so both map axes flip their y component.
  const across = { x: placement.right.x, y: -placement.right.y }, facing = { x: placement.facing.x, y: -placement.facing.y }
  const length = Math.max(16, 2.1 * scale), depth = Math.max(6, .8 * scale), lamp = Math.max(2.1, .27 * scale)
  ctx.strokeStyle = colors.arm; ctx.lineWidth = Math.max(1.4, .2 * scale); ctx.lineCap = "round"
  ctx.beginPath(); ctx.moveTo(pole.x, pole.y); ctx.lineTo(head.x + across.x * length / 2, head.y + across.y * length / 2); ctx.stroke()
  ctx.fillStyle = colors.housing; ctx.beginPath(); ctx.arc(pole.x, pole.y, Math.max(2, .25 * scale), 0, Math.PI * 2); ctx.fill()
  ctx.save(); ctx.translate(head.x, head.y); ctx.transform(across.x, across.y, facing.x, facing.y, 0, 0)
  roundedBox(ctx, -length / 2, -depth / 2, length, depth, colors.housing, depth * .35)
  roundedBox(ctx, -length / 2 + 1, depth / 2 - 1.2, length - 2, 1.2, colors.rim, .6)
  for (const [index, state] of (["red", "yellow", "green"] as const).entries()) {
    const x = (index - 1) * length / 3, lit = color === state
    if (lit) {
      const glow = ctx.createRadialGradient(x, depth * .4, 0, x, depth * .4, lamp * 3.4)
      glow.addColorStop(0, LAMPS[state][0]); glow.addColorStop(1, "rgba(0,0,0,0)")
      ctx.globalAlpha = colors.glow; ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(x, depth * .4, lamp * 3.4, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1
    }
    ctx.fillStyle = LAMPS[state][lit ? 0 : 1]; ctx.beginPath(); ctx.arc(x, 0, lamp, 0, Math.PI * 2); ctx.fill()
  }
  ctx.restore()
}
/** Walk / don't-walk head on a crossing's kerb end: a walking figure or a steady hand; dark when unlit or unknown. */
function drawWalkSignal(ctx: CanvasRenderingContext2D, point: VisualPoint, state: WalkSignal | null, transform: Transform, colors: Palette) {
  const p = screen(point, transform), size = Math.max(7, .8 * transform.scale)
  roundedBox(ctx, p.x - size / 2, p.y - size / 2, size, size, colors.housing, size * .22)
  ctx.save(); ctx.translate(p.x, p.y)
  if (state === "walk") {
    ctx.strokeStyle = ctx.fillStyle = FLEET.walk; ctx.lineWidth = Math.max(1, size * .11); ctx.lineCap = "round"
    ctx.beginPath(); ctx.arc(0, -size * .26, size * .1, 0, Math.PI * 2); ctx.fill()
    ctx.beginPath(); ctx.moveTo(0, -size * .12); ctx.lineTo(0, size * .1); ctx.lineTo(-size * .14, size * .32); ctx.moveTo(0, size * .1); ctx.lineTo(size * .14, size * .32)
    ctx.moveTo(-size * .16, size * .02); ctx.lineTo(0, -size * .07); ctx.lineTo(size * .16, size * .04); ctx.stroke()
  } else if (state === "dont_walk") {
    roundedBox(ctx, -size * .2, -size * .04, size * .4, size * .32, FLEET.hand, size * .08)
    for (const x of [-.2, -.1, 0, .1]) roundedBox(ctx, x * size, -size * .32, size * .085, size * .32, FLEET.hand, size * .04)
  }
  ctx.restore()
}
const sceneryPaths = new WeakMap<SceneryItem[], Map<string, Path2D>>()
/** One Path2D per scenery colour role, in native metres, so a camera move redraws scenery in a few fills. */
function sceneryLayers(items: SceneryItem[]) {
  let layers = sceneryPaths.get(items)
  if (layers) return layers
  layers = new Map()
  const layer = (role: string) => { let found = layers!.get(role); if (!found) { found = new Path2D(); layers!.set(role, found) } return found }
  const polygon = (role: string, points: readonly VisualPoint[]) => { const shape = layer(role); points.forEach((point, index) => index ? shape.lineTo(point.x, point.y) : shape.moveTo(point.x, point.y)); shape.closePath() }
  const circle = (role: string, center: VisualPoint, radius: number) => { const shape = layer(role); shape.moveTo(center.x + radius, center.y); shape.arc(center.x, center.y, radius, 0, Math.PI * 2) }
  for (const item of items) {
    if (item.kind === "tree") {
      circle("treeShadow", { x: item.center.x + .6, y: item.center.y - .7 }, item.radius)
      circle(`tree${item.tone}`, item.center, item.radius)
      circle("highlight", { x: item.center.x - item.radius * .3, y: item.center.y + item.radius * .3 }, item.radius * .5)
      continue
    }
    const along = { x: Math.cos(item.angle), y: Math.sin(item.angle) }, across = { x: -along.y, y: along.x }
    const at = (u: number, v: number) => ({ x: item.center.x + along.x * u + across.x * v, y: item.center.y + along.y * u + across.y * v })
    const box = (u: number, v: number, width: number, depth: number) => [at(u - width / 2, v - depth / 2), at(u + width / 2, v - depth / 2), at(u + width / 2, v + depth / 2), at(u - width / 2, v + depth / 2)]
    if (item.kind !== "building") {
      polygon(item.kind, item.corners)
      if (item.kind === "parking") for (const u of [-2, 0, 2]) for (const v of [-1.8, 1.8]) polygon("stall", box(u, v, .14, 2.2))
      continue
    }
    const { width, depth } = item, roof = `roof${item.tone}`, detail = `roofDetail${item.tone}`
    polygon("buildingShadow", item.corners.map((point) => ({ x: point.x + .9, y: point.y - 1.1 })))
    polygon(roof, item.corners)
    if (item.roof === "hip") {
      const [a, b, c, d] = item.corners, middle = item.center
      polygon(detail, [a, b, middle]); polygon(detail, [c, d, middle])
    } else if (item.roof === "terrace") for (const u of [-width / 3, width / 3]) polygon(detail, box(u, 0, width / 3 - .3, depth - .6))
    else {
      polygon(detail, box(0, 0, width - 1.4, depth - 1.4))
      if (item.roof === "flat") { polygon("fixture", box(-width * .18, depth * .12, 1.4, 1.2)); polygon("fixture", box(width * .2, -depth * .15, 1.1, 1.1)) }
    }
  }
  sceneryPaths.set(items, layers)
  return layers
}
function drawScenery(ctx: CanvasRenderingContext2D, items: SceneryItem[], transform: Transform, colors: Palette, roles: string[]) {
  const layers = sceneryLayers(items)
  const fills: Record<string, string> = {
    plaza: colors.plaza, lawn: colors.lawn, parking: colors.parking, stall: colors.stall, buildingShadow: colors.shadow, treeShadow: colors.shadow, fixture: colors.fixture, highlight: colors.highlight,
    ...Object.fromEntries(colors.roofs.flatMap(([base, detail], tone) => [[`roof${tone}`, base], [`roofDetail${tone}`, detail]])),
    ...Object.fromEntries(colors.trees.map((tree, tone) => [`tree${tone}`, tree])),
  }
  ctx.save(); ctx.translate(transform.ox, transform.oy); ctx.scale(transform.scale, -transform.scale)
  for (const role of roles) { const shape = layers.get(role); if (shape) { ctx.fillStyle = fills[role]; ctx.fill(shape) } }
  ctx.restore()
}
const vergeCache = new WeakMap<SceneGeometry, VisualPoint[][]>()
const GROUND_SCENERY = ["plaza", "lawn", "parking", "stall", "buildingShadow", "roof0", "roof1", "roof2", "roof3", "roofDetail0", "roofDetail1", "roofDetail2", "roofDetail3", "fixture"]
const TREE_SCENERY = ["treeShadow", "tree0", "tree1", "tree2", "highlight"]
function staticMap(ctx: CanvasRenderingContext2D, geometry: SceneGeometry, transform: Transform, colors: Palette, scenery: SceneryItem[], walkways: VisualPoint[][]) {
  ctx.fillStyle = colors.ground; ctx.fillRect(0, 0, transform.width, transform.height)
  drawScenery(ctx, scenery, transform, colors, GROUND_SCENERY)
  // Kerbs, sidewalks and verges are illustrative edging around the untouched native pavement.
  const roads = geometry.lanes.filter((lane) => lane.kind === "road"), metres = transform.scale
  const band = (color: string, reach: number) => {
    for (const lane of roads) path(ctx, lane.polygon, transform, color, color, 2 * reach * metres)
    for (const junction of geometry.junctions) path(ctx, junction.kerb, transform, color, color, 2 * reach * metres)
  }
  let verges = vergeCache.get(geometry)
  if (!verges) { verges = vergeLines(geometry); vergeCache.set(geometry, verges) }
  for (const line of verges) path(ctx, line, transform, undefined, colors.verge, STREET_EDGE.verge * metres)
  band(colors.sidewalk, STREET_EDGE.sidewalk)
  // Asphalt covers the crossing itself; the walkway shows only where the path leaves the sidewalk.
  ctx.lineCap = "round"
  for (const walkway of walkways) {
    ctx.beginPath(); walkway.forEach((point, index) => { const p = screen(point, transform); if (index) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y) })
    ctx.strokeStyle = colors.sidewalk; ctx.lineWidth = 2 * WALKWAY_HALF_WIDTH * metres; ctx.stroke()
  }
  band(colors.kerb, .3)
  // A hairline stroke in the fill colour hides the seam where opposing carriageways meet.
  for (const lane of roads) path(ctx, lane.polygon, transform, colors.asphalt, colors.asphalt, 1)
  for (const junction of geometry.junctions) path(ctx, junction.kerb, transform, colors.asphalt, colors.asphalt, 1)
  for (const lane of geometry.lanes) if (lane.kind === "crossing" || lane.kind === "walking") path(ctx, lane.polygon, transform, colors.sidewalk)
  for (const lane of roads) {
    if (lane.centreLine) path(ctx, lane.centreLine, transform, undefined, colors.centre, Math.max(1.2, metres * .15))
    for (const divider of lane.dividers) path(ctx, divider, transform, undefined, colors.marking, Math.max(1, metres * .12), false, [3, 3])
  }
  for (const group of geometry.signalGroups) path(ctx, group.stop_line, transform, undefined, colors.marking, Math.max(1.5, metres * .4))
  for (const junction of geometry.junctions) for (const crosswalk of junction.crosswalks) for (const stripe of crosswalk.stripes) path(ctx, stripe, transform, colors.marking)
  drawScenery(ctx, scenery, transform, colors, TREE_SCENERY)
}
function pointBeforeEnd(points: readonly VisualPoint[], metres: number) {
  let remaining = metres
  for (let index = points.length - 1; index > 0; index--) {
    const b = points[index], a = points[index - 1], segment = Math.hypot(b.x - a.x, b.y - a.y)
    if (segment >= remaining) return { x: b.x + (a.x - b.x) * remaining / segment, y: b.y + (a.y - b.y) * remaining / segment }
    remaining -= segment
  }
  return points[0]
}
/** Drawn signal colours by approach, for read-only browser checks against the engine frame. */
type SignalReport = { approaches: Record<string, SignalColor>; walk: Record<string, WalkSignal | null> }
function dynamicMap(ctx: CanvasRenderingContext2D, geometry: SceneGeometry, frame: RenderFrame | null, presentation: PresentationState, transform: Transform, hover: Selection | null, colors: Palette): SignalReport {
  occupiedLabels.set(ctx, [])
  const report: SignalReport = { approaches: {}, walk: {} }, laneLabels: Array<[string, VisualPoint]> = [], tags: Array<{ id: string; rect: LabelRect }> = []
  const focusedJunction = geometry.junctions.find((junction) => junction.id === presentation.junctionId)
  const orderedJunctions = focusedJunction ? [focusedJunction, ...geometry.junctions.filter((junction) => junction !== focusedJunction)] : geometry.junctions
  for (const junction of orderedJunctions) {
    const focused = junction.id === presentation.junctionId, selected = presentation.selection?.kind === "junction" && presentation.selection.id === junction.id
    if (selected || focused) path(ctx, junction.kerb, transform, "rgba(84,195,156,.1)", selected ? palette.selected : "#8BCDB2", selected ? 2.5 : 1.5)
  }
  if (frame) {
    const closed = new Set(frame.visual.closed_lanes)
    for (const lane of geometry.lanes) {
      if (lane.kind === "connector") { if (presentation.overlays.connectors) path(ctx, lane.centerline, transform, undefined, "#94AAB7", 1, true); continue }
      const metrics = frame.lane_metrics?.[lane.id]
      // Only queued lanes are tinted so clear roads stay plain asphalt; bands match the junction panel. Translucent so markings show through.
      if (presentation.overlays.heatmap && metrics && metrics.queue > 0) {
        const color = metrics.queue >= 10 ? "rgba(206,98,105,.6)" : metrics.queue >= 5 ? "rgba(212,172,99,.55)" : "rgba(134,167,156,.42)"
        path(ctx, lane.centerline, transform, undefined, color, Math.max(2, lane.width * transform.scale * .58))
      }
      // Queue counts sit behind the stop line so they never cover the approach's signal head.
      if (presentation.overlays.queues && metrics && metrics.queue > 0) laneLabels.push([`${metrics.queue}`, pointBeforeEnd(lane.centerline, 12)])
      if (presentation.overlays.arrows && lane.centerline.length > 1) {
        const middle = Math.max(1, Math.floor(lane.centerline.length / 2)), a = screen(lane.centerline[middle - 1], transform), b = screen(lane.centerline[middle], transform)
        ctx.save(); ctx.translate((a.x + b.x) / 2, (a.y + b.y) / 2); ctx.rotate(Math.atan2(b.y - a.y, b.x - a.x)); ctx.strokeStyle = palette.markings; ctx.lineWidth = 1.5
        ctx.beginPath(); ctx.moveTo(-5, -4); ctx.lineTo(3, 0); ctx.lineTo(-5, 4); ctx.stroke(); ctx.restore()
      }
      const isClosed = closed.has(lane.id) || metrics?.closed, factor = frame.visual.slow_lanes[lane.id] ?? metrics?.speed_factor
      if (isClosed || (factor !== undefined && factor < 1)) {
        path(ctx, lane.centerline, transform, undefined, isClosed ? palette.closed : palette.slow, Math.max(2, lane.width * transform.scale * .55), !isClosed)
        const middle = Math.max(1, Math.floor(lane.centerline.length / 2)), a = lane.centerline[middle - 1], b = lane.centerline[middle]
        if (a && b) {
          const marker = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }, p = screen(marker, transform)
          if (isClosed) {
            ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(Math.atan2(-(b.y - a.y), b.x - a.x)); ctx.fillStyle = palette.markings; ctx.fillRect(-2, -Math.max(6, lane.width * transform.scale / 2), 4, Math.max(12, lane.width * transform.scale))
            ctx.strokeStyle = palette.closed; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-5, -5); ctx.lineTo(5, 5); ctx.moveTo(5, -5); ctx.lineTo(-5, 5); ctx.stroke(); ctx.restore()
          } else laneLabels.push([`Slow ×${factor!.toFixed(2)}`, marker])
        }
      }
      if (presentation.selection?.kind === "lane" && presentation.selection.id === lane.id) path(ctx, lane.centerline, transform, undefined, palette.selected, Math.max(2, lane.width * transform.scale * .35), true)
      else if (hover?.kind === "lane" && hover.id === lane.id) path(ctx, lane.centerline, transform, undefined, "rgba(178,229,207,.8)", Math.max(2, lane.width * transform.scale * .25))
    }
    for (const vehicle of frame.vehicles) {
      const p = screen(vehicle, transform), margin = Math.max(vehicle.length, vehicle.width) * transform.scale
      if (p.x + margin < 0 || p.y + margin < 0 || p.x - margin > transform.width || p.y - margin > transform.height) continue
      drawVehicle(ctx, vehicle, transform, (presentation.selection?.kind === "vehicle" && presentation.selection.id === vehicle.id) || (hover?.kind === "vehicle" && hover.id === vehicle.id), colors)
    }
    // People face along their junction's modeled (illustrative) walking path.
    const walkHeadings = new Map((frame.visual.pedestrian_paths ?? []).filter((corridor) => corridor.shape.length > 1).map((corridor) => {
      const first = corridor.shape[0], last = corridor.shape[corridor.shape.length - 1]
      return [corridor.junction_id, Math.atan2(-(last.y - first.y), last.x - first.x)] as const
    }))
    for (const pedestrian of frame.pedestrians) {
      const highlighted = (presentation.selection?.kind === "pedestrian" && presentation.selection.id === pedestrian.id) || (hover?.kind === "pedestrian" && hover.id === pedestrian.id)
      drawPedestrian(ctx, pedestrian, walkHeadings.get(pedestrian.lane_id) ?? 0, transform, highlighted, colors)
    }
  }
  if (presentation.overlays.signals) {
    for (const group of geometry.signalGroups) {
      const { color } = signalAppearance(group, frame)
      drawSignalHead(ctx, group, color, transform, colors); report.approaches[group.lane_id] = color
    }
    for (const junction of geometry.junctions) {
      const state = walkSignalState(junction.id, frame); report.walk[junction.id] = state
      for (const crosswalk of junction.crosswalks) for (const point of crosswalk.walkSignals) drawWalkSignal(ctx, point, state, transform, colors)
    }
  }
  // Junction tags claim label space before lane labels; they sit off the north-east kerb corner (north-west near
  // the right edge), clear of the signal heads.
  if (presentation.overlays.labels) for (const junction of orderedJunctions) {
    const highlighted = junction.id === presentation.junctionId || (presentation.selection?.kind === "junction" && presentation.selection.id === junction.id)
    const reach = Math.max(...junction.kerb.map((point) => Math.max(point.x - junction.center.x, point.y - junction.center.y)), 0) + 2, text = junctionTagText(junction.label)
    const rect = label(ctx, text, { x: junction.center.x + reach, y: junction.center.y + reach }, transform, colors, -14, highlighted, "left")
      ?? label(ctx, text, { x: junction.center.x - reach, y: junction.center.y + reach }, transform, colors, -14, highlighted, "right")
    if (rect) tags.push({ id: junction.id, rect })
  }
  for (const [text, point] of laneLabels) label(ctx, text, point, transform, colors)
  junctionTags.set(ctx, tags)
  return report
}

export function SimulationCanvas2D({ frame, geometry, presentation, onSelect, runKey = "", onPerformanceSample }: Props) {
  const navigationHintId = React.useId()
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null), drawRef = React.useRef<() => void>(() => undefined)
  const controlsRef = React.useRef<(action: "in" | "out" | "reset") => void>(() => undefined)
  const tooltipRef = React.useRef<HTMLDivElement | null>(null), scaleRef = React.useRef<HTMLDivElement | null>(null), hintRef = React.useRef<HTMLSpanElement | null>(null)
  const latestRef = React.useRef({ frame, presentation, onSelect, runKey, onPerformanceSample })
  React.useEffect(() => { latestRef.current = { frame, presentation, onSelect, runKey, onPerformanceSample }; drawRef.current() }, [frame, presentation, onSelect, runKey, onPerformanceSample])
  React.useEffect(() => {
    const canvas = canvasRef.current, parent = canvas?.parentElement, context = canvas?.getContext("2d", { alpha: false })
    if (!canvas || !parent || !context) return
    const ctx = context
    const cache = document.createElement("canvas"), cached = cache.getContext("2d", { alpha: false })
    const stream = createMapInterpolator()
    let width = 1, height = 1, dpr = 1, transform = fit(geometry.bounds, width, height), previousFocus = "", cacheKey = ""
    let animationId = 0, displayedFrame: RenderFrame | null = null, pointerPosition: VisualPoint | null = null, hover: Selection | null = null, followSuspended = false
    let lastDrawAt = 0, sampleStarted = performance.now(), drawnFrames = 0, totalPaints = 0, frameIntervals: number[] = []
    let previousPathSource: RenderFrame["visual"]["pedestrian_paths"] = undefined, pathsKey = "", previousScaleLabel = ""
    let walkways: VisualPoint[][] = [], scenery = cityScenery(geometry, walkways), sceneryPathsKey = "[]"
    const currentTheme = (): Theme => document.documentElement.classList.contains("dark") ? "dark" : "light"
    let theme = currentTheme()
    // The app theme is a class on <html>; follow it without re-rendering React.
    const themeObserver = new MutationObserver(() => { if (currentTheme() !== theme) { theme = currentTheme(); schedule() } })
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] })
    const pointers = new Map<number, { x: number; y: number; startX: number; startY: number; moved: boolean }>()
    const boundPan = () => { transform = boundMapPan(transform, geometry.bounds) }
    const schedule = () => { if (!animationId && !document.hidden) animationId = requestAnimationFrame(draw) }
    const updateHint = () => { if (hintRef.current) hintRef.current.textContent = followSuspended && latestRef.current.presentation.focus === "follow" ? "Follow paused · Reset to resume" : "Drag to explore · Scroll to zoom" }
    const manualNavigation = () => { followSuspended = true; hover = null; pointerPosition = null; updateHint() }
    const pick = (point: VisualPoint): Selection | null => {
      const tag = junctionTags.get(ctx)?.find(({ rect }) => point.x >= rect.x && point.x <= rect.x + rect.width && point.y >= rect.y && point.y <= rect.y + rect.height)
      return tag ? { kind: "junction", id: tag.id } : pickSceneEntity(geometry, displayedFrame, screenToMap(point, transform), 4 / transform.scale)
    }
    const updateTooltip = () => {
      const tooltip = tooltipRef.current
      if (!tooltip) return
      if (!hover || !pointerPosition || pointers.size) { tooltip.hidden = true; return }
      let text = ""
      if (hover.kind === "junction") text = geometry.junctionById.get(hover.id)?.label ?? "Junction"
      else if (hover.kind === "lane") {
        const metrics = displayedFrame?.lane_metrics?.[hover.id]
        text = metrics ? `Lane · ${metrics.vehicles} vehicles · Queue ${metrics.queue}` : "Lane · Click to inspect"
      } else if (hover.kind === "vehicle") {
        const vehicle = displayedFrame?.vehicles.find((candidate) => candidate.id === hover?.id)
        if (vehicle) { const name = normalizeVehicleClass(vehicle.visual_type); text = `${name === "tricycle" ? "Tagum tricycle" : name[0].toUpperCase() + name.slice(1)} · ${vehicle.stopped ? "Stopped" : `${(vehicle.speed * 3.6).toFixed(0)} km/h`}` }
      } else {
        const person = displayedFrame?.pedestrians.find((candidate) => candidate.id === hover?.id)
        text = person ? `Pedestrian · ${person.stopped ? "Waiting" : "Moving"}` : ""
      }
      tooltip.textContent = text; tooltip.hidden = !text
      if (text) { tooltip.style.left = `${Math.max(8, Math.min(width - tooltip.offsetWidth - 8, pointerPosition.x + 15))}px`; tooltip.style.top = `${Math.max(8, Math.min(height - tooltip.offsetHeight - 8, pointerPosition.y + 18))}px` }
    }
    function draw(now: number) {
      animationId = 0
      const paintStarted = performance.now()
      const current = latestRef.current, focus = `${current.presentation.focus}:${current.presentation.junctionId}:${current.presentation.revision}`
      stream.set(current.frame, `${current.runKey}:${current.presentation.revision}`, now)
      displayedFrame = stream.sample(now)
      if (focus !== previousFocus) {
        transform = fit(current.presentation.focus === "network" ? geometry.bounds : boundsForJunction(geometry, current.presentation.junctionId), width, height)
        previousFocus = focus; followSuspended = false; updateHint()
      }
      if (current.presentation.focus === "follow" && !followSuspended && current.presentation.selection?.kind === "vehicle") {
        const vehicle = displayedFrame?.vehicles.find((entity) => entity.id === current.presentation.selection?.id)
        if (vehicle) { transform.ox = width / 2 - vehicle.x * transform.scale; transform.oy = height / 2 + vehicle.y * transform.scale }
      }
      if (current.frame?.visual.pedestrian_paths !== previousPathSource) { previousPathSource = current.frame?.visual.pedestrian_paths; pathsKey = JSON.stringify(previousPathSource ?? []) }
      if (pathsKey !== sceneryPathsKey) { walkways = pedestrianWalkways(previousPathSource ?? []); scenery = cityScenery(geometry, walkways); sceneryPathsKey = pathsKey }
      const colors = CITY[theme], key = `${width}:${height}:${dpr}:${transform.scale}:${transform.ox}:${transform.oy}:${pathsKey}:${theme}`
      if (cached && cacheKey !== key) {
        cached.setTransform(dpr, 0, 0, dpr, 0, 0); staticMap(cached, geometry, transform, colors, scenery, walkways); cacheKey = key
      }
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      if (cached) ctx.drawImage(cache, 0, 0)
      else { ctx.setTransform(dpr, 0, 0, dpr, 0, 0); staticMap(ctx, geometry, transform, colors, scenery, walkways) }
      if (pointerPosition && !pointers.size) hover = pick(pointerPosition)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const signals = dynamicMap(ctx, geometry, displayedFrame, current.presentation, transform, hover, colors)
      // Read-only diagnostics support browser checks without a renderer control backdoor.
      canvas!.dataset.signals = JSON.stringify({ time: displayedFrame?.time ?? null, ...signals })
      canvas!.dataset.theme = theme
      canvas!.dataset.mapCamera = JSON.stringify({ scale: transform.scale, ox: transform.ox, oy: transform.oy, width, height })
      canvas!.dataset.paintCount = String(++totalPaints)
      canvas!.dataset.interpolating = String(stream.moving(now))
      const firstVehicle = displayedFrame?.vehicles[0], firstPerson = displayedFrame?.pedestrians[0]
      canvas!.dataset.displayVehicle = firstVehicle ? JSON.stringify({ id: firstVehicle.id, x: firstVehicle.x, y: firstVehicle.y }) : ""
      canvas!.dataset.displayPedestrian = firstPerson ? JSON.stringify({ id: firstPerson.id, x: firstPerson.x, y: firstPerson.y }) : ""
      canvas!.dataset.paintMs = (performance.now() - paintStarted).toFixed(2)
      updateTooltip()
      if (!pointers.size) canvas!.style.cursor = hover ? "pointer" : "grab"
      const scale = mapScale(transform.scale), scaleLabel = `${scale.label}:${scale.pixels}`
      if (scaleRef.current && scaleLabel !== previousScaleLabel) { scaleRef.current.style.setProperty("--map-scale-width", `${scale.pixels}px`); scaleRef.current.setAttribute("aria-label", `Map scale ${scale.label}`); const label = scaleRef.current.querySelector("span"); if (label) label.textContent = scale.label; previousScaleLabel = scaleLabel }
      // Report active animation/navigation cadence only. Idle/paused maps do not burn frames.
      if (lastDrawAt > 0 && now - lastDrawAt < 150) frameIntervals.push(now - lastDrawAt)
      else { frameIntervals = []; sampleStarted = now; drawnFrames = 0 }
      lastDrawAt = now; drawnFrames++
      if (now - sampleStarted >= 1000 && frameIntervals.length >= 5) {
        const sorted = [...frameIntervals].sort((a, b) => a - b)
        current.onPerformanceSample?.({ fps: drawnFrames * 1000 / (now - sampleStarted), p95FrameMs: sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * .95))], drawCalls: 0 })
        sampleStarted = now; drawnFrames = 0; frameIntervals = []
      }
      if (stream.moving(now)) schedule()
    }
    const resize = () => {
      const nextWidth = Math.max(1, parent.clientWidth), nextHeight = Math.max(1, parent.clientHeight), nextDpr = Math.min(window.devicePixelRatio || 1, latestRef.current.presentation.quality === "laptop" ? 1.5 : 2)
      if (width === nextWidth && height === nextHeight && dpr === nextDpr) return
      const current = latestRef.current.presentation
      transform = followSuspended
        ? resizeMap(transform, nextWidth, nextHeight)
        : fit(current.focus === "network" ? geometry.bounds : boundsForJunction(geometry, current.junctionId), nextWidth, nextHeight)
      width = nextWidth; height = nextHeight; dpr = nextDpr
      canvas.width = cache.width = Math.max(1, Math.round(width * dpr)); canvas.height = cache.height = Math.max(1, Math.round(height * dpr)); cacheKey = ""; schedule()
    }
    drawRef.current = () => { resize(); schedule() }
    const position = (event: PointerEvent | WheelEvent) => { const rect = canvas.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top } }
    const zoomAt = (point: VisualPoint, factor: number) => { transform = zoomMapAt(transform, point, factor, fit(geometry.bounds, width, height).scale * .65); boundPan(); schedule() }
    const reset = () => { previousFocus = ""; followSuspended = false; schedule() }
    controlsRef.current = (action) => { if (action === "reset") reset(); else { manualNavigation(); zoomAt({ x: width / 2, y: height / 2 }, action === "in" ? 1.3 : 1 / 1.3) } }
    const wheel = (event: WheelEvent) => {
      event.preventDefault(); manualNavigation()
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? height : 1)
      zoomAt(position(event), Math.exp(-Math.max(-250, Math.min(250, delta)) * .002))
    }
    const pointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return
      const p = position(event); pointers.set(event.pointerId, { ...p, startX: p.x, startY: p.y, moved: false }); canvas.setPointerCapture(event.pointerId); canvas.focus({ preventScroll: true }); canvas.style.cursor = "grabbing"; parent.dataset.navigating = "true"
      if (pointers.size > 1) for (const pointer of pointers.values()) pointer.moved = true
      hover = null; updateTooltip()
    }
    const pointerMove = (event: PointerEvent) => {
      const p = position(event), pointer = pointers.get(event.pointerId)
      if (!pointer) { pointerPosition = p; schedule(); return }
      const before = [...pointers.values()].slice(0, 2).map((value) => ({ x: value.x, y: value.y }))
      pointer.moved ||= Math.hypot(p.x - pointer.startX, p.y - pointer.startY) > 4
      const dx = p.x - pointer.x, dy = p.y - pointer.y; pointer.x = p.x; pointer.y = p.y
      if (pointers.size > 1) {
        manualNavigation()
        const after = [...pointers.values()].slice(0, 2), beforeCenter = { x: (before[0].x + before[1].x) / 2, y: (before[0].y + before[1].y) / 2 }, afterCenter = { x: (after[0].x + after[1].x) / 2, y: (after[0].y + after[1].y) / 2 }
        const previousDistance = Math.hypot(before[0].x - before[1].x, before[0].y - before[1].y), distance = Math.hypot(after[0].x - after[1].x, after[0].y - after[1].y)
        transform = zoomMapAt(transform, beforeCenter, previousDistance > 1 ? distance / previousDistance : 1, fit(geometry.bounds, width, height).scale * .65)
        transform.ox += afterCenter.x - beforeCenter.x; transform.oy += afterCenter.y - beforeCenter.y; boundPan(); schedule()
      } else if (pointer.moved) { manualNavigation(); transform.ox += dx; transform.oy += dy; boundPan(); schedule() }
    }
    const release = (event: PointerEvent, allowPick: boolean) => {
      const pointer = pointers.get(event.pointerId)
      if (!pointer) return
      if (allowPick && !pointer.moved && pointers.size === 1) latestRef.current.onSelect(pick(position(event)))
      pointers.delete(event.pointerId)
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
      if (!pointers.size) { delete parent.dataset.navigating; canvas.style.cursor = "grab" }
      schedule()
    }
    const pointerUp = (event: PointerEvent) => release(event, true)
    const pointerCancel = (event: PointerEvent) => release(event, false)
    const pointerLeave = () => { pointerPosition = null; hover = null; updateTooltip(); schedule() }
    const doubleClick = (event: MouseEvent) => { manualNavigation(); const rect = canvas.getBoundingClientRect(); zoomAt({ x: event.clientX - rect.left, y: event.clientY - rect.top }, 1.5) }
    const keyDown = (event: KeyboardEvent) => {
      if (["+", "=", "-", "_"].includes(event.key)) { event.preventDefault(); manualNavigation(); zoomAt({ x: width / 2, y: height / 2 }, event.key === "-" || event.key === "_" ? 1 / 1.3 : 1.3) }
      else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault(); manualNavigation(); const step = event.shiftKey ? 100 : 40; transform.ox += event.key === "ArrowLeft" ? step : event.key === "ArrowRight" ? -step : 0; transform.oy += event.key === "ArrowUp" ? step : event.key === "ArrowDown" ? -step : 0; boundPan(); schedule()
      } else if (event.key === "Home" || event.key === "0") { event.preventDefault(); reset() }
      else if (event.key === "Escape") latestRef.current.onSelect(null)
    }
    const visibility = () => {
      if (document.hidden) {
        cancelAnimationFrame(animationId); animationId = 0
        // Resume from the newest authoritative frame, not a long hidden-tab journey.
        stream.set(null, "", performance.now())
      } else { lastDrawAt = 0; schedule() }
    }
    canvas.addEventListener("wheel", wheel, { passive: false }); canvas.addEventListener("pointerdown", pointerDown); canvas.addEventListener("pointermove", pointerMove); canvas.addEventListener("pointerup", pointerUp); canvas.addEventListener("pointercancel", pointerCancel); canvas.addEventListener("lostpointercapture", pointerCancel); canvas.addEventListener("pointerleave", pointerLeave); canvas.addEventListener("keydown", keyDown); canvas.addEventListener("dblclick", doubleClick); document.addEventListener("visibilitychange", visibility)
    const observer = new ResizeObserver(resize); observer.observe(parent); resize()
    return () => {
      observer.disconnect(); themeObserver.disconnect(); if (animationId) cancelAnimationFrame(animationId)
      canvas.removeEventListener("wheel", wheel); canvas.removeEventListener("pointerdown", pointerDown); canvas.removeEventListener("pointermove", pointerMove); canvas.removeEventListener("pointerup", pointerUp); canvas.removeEventListener("pointercancel", pointerCancel); canvas.removeEventListener("lostpointercapture", pointerCancel); canvas.removeEventListener("pointerleave", pointerLeave); canvas.removeEventListener("keydown", keyDown); canvas.removeEventListener("dblclick", doubleClick); document.removeEventListener("visibilitychange", visibility)
      for (const id of pointers.keys()) if (canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id)
      drawRef.current = () => undefined; controlsRef.current = () => undefined; pointers.clear(); delete parent.dataset.navigating
    }
  }, [geometry])
  return <div className="sf-canvas2d-shell">
    <canvas ref={canvasRef} className="sf-canvas2d" tabIndex={0} aria-label="Simulation map with illustrative city scenery" aria-describedby={navigationHintId} style={{ cursor: "grab", touchAction: "none" }} />
    <div className="sf-canvas2d-navigation" role="group" aria-label="Map navigation">
      <Button variant="outline" size="icon" aria-label="Zoom in map" title="Zoom in (+)" onClick={() => controlsRef.current("in")}><Plus /></Button>
      <Button variant="outline" size="icon" aria-label="Zoom out map" title="Zoom out (−)" onClick={() => controlsRef.current("out")}><Minus /></Button>
      <Button variant="outline" size="icon" aria-label="Reset map view" title="Reset view (Home)" onClick={() => controlsRef.current("reset")}><LocateFixed /></Button>
    </div>
    <div ref={scaleRef} className="sf-canvas2d-scale" aria-label="Map scale"><b aria-hidden="true">↑ N</b><i aria-hidden="true" /><span /></div>
    <span ref={hintRef} className="sf-canvas2d-gesture-hint" aria-hidden="true">Drag to explore · Scroll to zoom</span>
    <div ref={tooltipRef} className="sf-canvas2d-tooltip" hidden aria-hidden="true" />
    <span id={navigationHintId} className="sr-only">Drag to pan. Scroll, pinch, or use plus and minus keys to zoom. Double-click to zoom toward a location. Arrow keys pan, Home restores camera focus, and Escape clears selection. Use the labeled object picker beside the map to inspect objects with a keyboard.</span>
  </div>
}

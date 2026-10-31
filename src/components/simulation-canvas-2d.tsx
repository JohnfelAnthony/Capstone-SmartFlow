import * as React from "react"
import { LocateFixed, Minus, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { VisualPoint } from "@/api/visual-network"
import type { RenderFrame, RenderVehicle } from "@/simulation/frame-types"
import { boundsForJunction, hasSignalHead, headingToCanvasRotation, normalizeVehicleClass, pickSceneEntity, SCENE_PALETTE as palette, signalAppearance, type SceneGeometry, type Selection } from "@/simulation/scene-geometry"
import type { PresentationState } from "@/simulation/presentation-state"
import { junctionTagText } from "@/simulation/scene-summary"
import { boundMapPan, claimMapLabel, createMapInterpolator, fitMap as fit, mapScale, mapToScreen as screen, resizeMap, screenToMap, zoomMapAt, type LabelRect, type MapCamera as Transform } from "@/simulation/map-navigation"

type Props = { frame: RenderFrame | null; geometry: SceneGeometry; presentation: PresentationState; onSelect: (selection: Selection | null) => void; runKey?: string; onPerformanceSample?: (sample: { fps: number; p95FrameMs: number; drawCalls: number }) => void }
const geometryPaths = new WeakMap<VisualPoint[], { open: Path2D; closed: Path2D }>()
const occupiedLabels = new WeakMap<CanvasRenderingContext2D, LabelRect[]>()
/** Cache immutable native paths once; camera movement only changes the canvas matrix. */
function path(ctx: CanvasRenderingContext2D, points: VisualPoint[], transform: Transform, fill?: string, stroke?: string, width = 1, dashed = false) {
  if (points.length < 2) return
  let paths = geometryPaths.get(points)
  if (!paths) {
    const open = new Path2D(); points.forEach((point, index) => { if (index === 0) open.moveTo(point.x, point.y); else open.lineTo(point.x, point.y) })
    const closed = new Path2D(open); closed.closePath(); paths = { open, closed }; geometryPaths.set(points, paths)
  }
  ctx.save(); ctx.translate(transform.ox, transform.oy); ctx.scale(transform.scale, -transform.scale)
  if (fill) { ctx.fillStyle = fill; ctx.fill(paths.closed) }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = width / transform.scale; ctx.lineCap = "butt"; ctx.lineJoin = "round"; ctx.setLineDash(dashed ? [5 / transform.scale, 5 / transform.scale] : []); ctx.stroke(fill ? paths.closed : paths.open) }
  ctx.restore()
}
function label(ctx: CanvasRenderingContext2D, text: string, point: VisualPoint | undefined, transform: Transform, offset = 0, highlighted = false) {
  if (!point) return
  const p = screen(point, transform)
  ctx.font = "600 11px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle"
  const width = ctx.measureText(text).width + 18, height = 23, occupied = occupiedLabels.get(ctx) ?? []
  const rect = claimMapLabel([offset, offset - 28, offset + 28].map((dy) => ({ x: p.x - width / 2, y: p.y + dy - height / 2, width, height })), occupied, transform.width, transform.height)
  if (!rect) return
  ctx.beginPath(); ctx.roundRect(rect.x, rect.y, width, height, 7); ctx.fillStyle = highlighted ? "#1F7A5A" : "rgba(250,252,248,.96)"; ctx.fill(); ctx.strokeStyle = highlighted ? "#1F7A5A" : "rgba(63,87,74,.14)"; ctx.lineWidth = 1; ctx.stroke()
  ctx.fillStyle = highlighted ? "#FFFFFF" : "#2D493D"; ctx.fillText(text, rect.x + width / 2, rect.y + height / 2)
}
function hashIndex(id: string) { let hash = 0; for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0; return (hash >>> 0) % palette.cars.length }
function drawVehicle(ctx: CanvasRenderingContext2D, vehicle: RenderVehicle, transform: Transform, selected: boolean) {
  const p = screen(vehicle, transform), length = Math.max(3, vehicle.length * transform.scale), width = Math.max(1.6, vehicle.width * transform.scale)
  const type = normalizeVehicleClass(vehicle.visual_type), color = palette.cars[hashIndex(vehicle.id)]
  ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(headingToCanvasRotation(vehicle.angle))
  ctx.fillStyle = "rgba(13,24,28,.26)"; ctx.fillRect(-length / 2 + 1, -width / 2 + 1, length, width)
  ctx.fillStyle = type === "tricycle" ? palette.tricycle : type === "bus" ? "#BE9B6C" : type === "truck" ? "#9B9FA2" : color
  if (type === "motorcycle") {
    ctx.fillStyle = palette.tyre; ctx.fillRect(-length / 2, -width * .23, length, width * .46)
    ctx.fillStyle = color; ctx.fillRect(-length * .25, -width * .48, length * .55, width * .96)
    ctx.fillStyle = palette.glass; ctx.fillRect(length * .24, -width / 2, length * .12, width)
  } else if (type === "tricycle") {
    ctx.fillRect(-length / 2, -width / 2, length * .75, width)
    ctx.fillStyle = palette.glass; ctx.fillRect(-length * .3, -width * .37, length * .45, width * .74)
    ctx.fillStyle = palette.tricycle; ctx.fillRect(length * .2, -width * .22, length * .22, width * .44)
    ctx.fillStyle = palette.tyre
    ctx.fillRect(length * .39, -width * .15, length * .11, width * .3)
    ctx.fillRect(-length * .37, -width * .52, length * .14, width * .18); ctx.fillRect(-length * .37, width * .34, length * .14, width * .18)
  } else {
    ctx.beginPath(); ctx.roundRect(-length / 2, -width / 2, length, width, Math.min(2, width * .2)); ctx.fill(); ctx.fillStyle = palette.glass
    if (type === "bus") for (let index = 0; index < 5; index++) ctx.fillRect(-length * .4 + index * length * .15, -width * .32, length * .1, width * .64)
    else if (type === "truck") {
      ctx.fillRect(length * .24, -width * .35, length * .16, width * .7); ctx.strokeStyle = "#CFD3D1"; ctx.lineWidth = 1; ctx.strokeRect(-length * .46, -width * .41, length * .65, width * .82)
    } else ctx.fillRect(-length * .25, -width * .36, length * .52, width * .72)
  }
  if (width > 4 && type !== "motorcycle") {
    ctx.fillStyle = "#F9EBC1"; ctx.fillRect(length * .43, -width * .4, Math.max(1, length * .05), width * .2); ctx.fillRect(length * .43, width * .2, Math.max(1, length * .05), width * .2)
    ctx.fillStyle = vehicle.stopped ? "#F57872" : "#A85D59"; ctx.fillRect(-length * .5, -width * .4, Math.max(1, length * .05), width * .2); ctx.fillRect(-length * .5, width * .2, Math.max(1, length * .05), width * .2)
  }
  if (selected) { ctx.strokeStyle = palette.selected; ctx.lineWidth = 2; ctx.strokeRect(-length / 2 - 3, -width / 2 - 3, length + 6, width + 6) }
  ctx.restore()
}
function staticMap(ctx: CanvasRenderingContext2D, geometry: SceneGeometry, transform: Transform) {
  const ground = ctx.createLinearGradient(0, 0, transform.width, transform.height); ground.addColorStop(0, "#EAF0E8"); ground.addColorStop(1, "#E1E9E2")
  ctx.fillStyle = ground; ctx.fillRect(0, 0, transform.width, transform.height)
  const gridSpacing = 25 * transform.scale
  if (gridSpacing > 14) {
    ctx.fillStyle = "rgba(80,109,90,.12)"
    for (let x = ((transform.ox % gridSpacing) + gridSpacing) % gridSpacing; x < transform.width; x += gridSpacing) for (let y = ((transform.oy % gridSpacing) + gridSpacing) % gridSpacing; y < transform.height; y += gridSpacing) ctx.fillRect(x, y, 1.5, 1.5)
  }
  // Curb borders are illustrative edging only: native pavement vertices stay untouched.
  for (const lane of geometry.lanes) if (lane.kind !== "connector") path(ctx, lane.polygon, transform, "#C2CDC5", "#C2CDC5", Math.max(2, transform.scale * 1.05))
  for (const lane of geometry.lanes) if (lane.kind !== "connector") path(ctx, lane.polygon, transform, lane.kind === "road" ? "#48575D" : "#C8D0C5", "rgba(232,238,228,.52)", Math.max(.6, transform.scale * .12))
  for (const lane of geometry.lanes) for (const divider of lane.dividers) path(ctx, divider, transform, undefined, palette.markings, Math.max(1, transform.scale * .12), true)
  for (const junction of geometry.junctions) path(ctx, junction.polygon, transform, "#48575D")
  for (const group of geometry.signalGroups) path(ctx, group.stop_line, transform, undefined, palette.markings, Math.max(1, transform.scale * .25))
}
function dynamicMap(ctx: CanvasRenderingContext2D, geometry: SceneGeometry, frame: RenderFrame | null, presentation: PresentationState, transform: Transform, hover: Selection | null) {
  occupiedLabels.set(ctx, [])
  if (presentation.overlays.signals) for (const group of geometry.signalGroups) {
    if (!hasSignalHead(group, frame)) continue
    const appearance = signalAppearance(group, frame), anchor = screen(group.anchor, transform), heading = group.heading * Math.PI / 180
    const x = anchor.x - Math.sin(heading) * (group.width / 2 * transform.scale + 7), y = anchor.y - Math.cos(heading) * (group.width / 2 * transform.scale + 7)
    ctx.fillStyle = "#293238"; ctx.fillRect(x - 4, y - 10, 8, 20)
    for (const [index, state] of (["red", "yellow", "green"] as const).entries()) {
      ctx.beginPath(); ctx.arc(x, y - 6 + index * 6, 2.3, 0, Math.PI * 2); ctx.fillStyle = appearance.color === state ? palette[state] : "#576067"; ctx.fill()
    }
    if (appearance.color === "off") { ctx.strokeStyle = "#9AABA6"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x - 3, y + 9); ctx.lineTo(x + 3, y - 9); ctx.stroke() }
  }
  const focusedJunction = geometry.junctions.find((junction) => junction.id === presentation.junctionId)
  const orderedJunctions = focusedJunction ? [focusedJunction, ...geometry.junctions.filter((junction) => junction !== focusedJunction)] : geometry.junctions
  for (const junction of orderedJunctions) {
    const focused = junction.id === presentation.junctionId, selected = presentation.selection?.kind === "junction" && presentation.selection.id === junction.id
    if (selected || focused) path(ctx, junction.polygon, transform, "rgba(84,195,156,.1)", selected ? palette.selected : "#8BCDB2", selected ? 2.5 : 1.5)
    if (presentation.overlays.labels) label(ctx, junctionTagText(junction.label), junction.center, transform, -35, focused || selected)
  }
  if (!frame) return
  const closed = new Set(frame.visual.closed_lanes)
  for (const lane of geometry.lanes) {
    if (lane.kind === "connector") { if (presentation.overlays.connectors) path(ctx, lane.centerline, transform, undefined, "#94AAB7", 1, true); continue }
    const metrics = frame.lane_metrics?.[lane.id]
    // Only queued lanes are tinted so clear roads stay plain asphalt; bands match the junction panel.
    if (presentation.overlays.heatmap && metrics && metrics.queue > 0) {
      const color = metrics.queue >= 10 ? "#CE6269" : metrics.queue >= 5 ? "#D4AC63" : "#86A79C"
      path(ctx, lane.centerline, transform, undefined, color, Math.max(2, lane.width * transform.scale * .58))
    }
    if (presentation.overlays.queues && metrics && metrics.queue > 0) label(ctx, `${metrics.queue}`, lane.centerline[Math.floor(lane.centerline.length / 2)], transform)
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
        } else label(ctx, `Slow ×${factor!.toFixed(2)}`, marker, transform)
      }
    }
    if (presentation.selection?.kind === "lane" && presentation.selection.id === lane.id) path(ctx, lane.centerline, transform, undefined, palette.selected, Math.max(2, lane.width * transform.scale * .35), true)
    else if (hover?.kind === "lane" && hover.id === lane.id) path(ctx, lane.centerline, transform, undefined, "rgba(178,229,207,.8)", Math.max(2, lane.width * transform.scale * .25))
  }
  // Zebra crossing look: a wide stroke dashed every 0.6 m reads as stripes across the walking path.
  for (const corridor of frame.visual.pedestrian_paths ?? []) {
    if (corridor.shape.length < 2) continue
    ctx.save(); ctx.beginPath()
    corridor.shape.forEach((point, index) => { const p = screen(point, transform); if (index === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y) })
    ctx.strokeStyle = "rgba(244,246,240,.85)"; ctx.lineWidth = Math.max(3, transform.scale * 3); ctx.lineCap = "butt"
    ctx.setLineDash([Math.max(1.5, transform.scale * .6), Math.max(1.5, transform.scale * .6)]); ctx.stroke(); ctx.restore()
  }
  for (const vehicle of frame.vehicles) {
    const p = screen(vehicle, transform), margin = Math.max(vehicle.length, vehicle.width) * transform.scale
    if (p.x + margin < 0 || p.y + margin < 0 || p.x - margin > transform.width || p.y - margin > transform.height) continue
    drawVehicle(ctx, vehicle, transform, (presentation.selection?.kind === "vehicle" && presentation.selection.id === vehicle.id) || (hover?.kind === "vehicle" && hover.id === vehicle.id))
  }
  for (const pedestrian of frame.pedestrians) {
    const p = screen(pedestrian, transform), radius = Math.max(2.5, transform.scale * .35)
    ctx.fillStyle = pedestrian.stopped ? palette.yellow : palette.pedestrian; ctx.beginPath(); ctx.arc(p.x, p.y, radius, 0, Math.PI * 2); ctx.fill()
    ctx.strokeStyle = (presentation.selection?.kind === "pedestrian" && presentation.selection.id === pedestrian.id) || (hover?.kind === "pedestrian" && hover.id === pedestrian.id) ? palette.selected : "#FFF8EF"; ctx.lineWidth = 1.5; ctx.stroke()
    if (pedestrian.stopped) { ctx.fillStyle = "#80553E"; ctx.fillRect(p.x - .8, p.y - 1.8, 1.6, 3.6) }
  }
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
    const pointers = new Map<number, { x: number; y: number; startX: number; startY: number; moved: boolean }>()
    const boundPan = () => { transform = boundMapPan(transform, geometry.bounds) }
    const schedule = () => { if (!animationId && !document.hidden) animationId = requestAnimationFrame(draw) }
    const updateHint = () => { if (hintRef.current) hintRef.current.textContent = followSuspended && latestRef.current.presentation.focus === "follow" ? "Follow paused · Reset to resume" : "Drag to explore · Scroll to zoom" }
    const manualNavigation = () => { followSuspended = true; hover = null; pointerPosition = null; updateHint() }
    const pick = (point: VisualPoint) => pickSceneEntity(geometry, displayedFrame, screenToMap(point, transform), 4 / transform.scale)
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
      const key = `${width}:${height}:${dpr}:${transform.scale}:${transform.ox}:${transform.oy}:${pathsKey}`
      if (cached && cacheKey !== key) {
        cached.setTransform(dpr, 0, 0, dpr, 0, 0); staticMap(cached, geometry, transform); cacheKey = key
      }
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      if (cached) ctx.drawImage(cache, 0, 0)
      else { ctx.setTransform(dpr, 0, 0, dpr, 0, 0); staticMap(ctx, geometry, transform) }
      if (pointerPosition && !pointers.size) hover = pick(pointerPosition)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); dynamicMap(ctx, geometry, displayedFrame, current.presentation, transform, hover)
      // Read-only diagnostics support browser checks without a renderer control backdoor.
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
      observer.disconnect(); if (animationId) cancelAnimationFrame(animationId)
      canvas.removeEventListener("wheel", wheel); canvas.removeEventListener("pointerdown", pointerDown); canvas.removeEventListener("pointermove", pointerMove); canvas.removeEventListener("pointerup", pointerUp); canvas.removeEventListener("pointercancel", pointerCancel); canvas.removeEventListener("lostpointercapture", pointerCancel); canvas.removeEventListener("pointerleave", pointerLeave); canvas.removeEventListener("keydown", keyDown); canvas.removeEventListener("dblclick", doubleClick); document.removeEventListener("visibilitychange", visibility)
      for (const id of pointers.keys()) if (canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id)
      drawRef.current = () => undefined; controlsRef.current = () => undefined; pointers.clear(); delete parent.dataset.navigating
    }
  }, [geometry])
  return <div className="sf-canvas2d-shell" style={{ background: palette.ground }}>
    <canvas ref={canvasRef} className="sf-canvas2d" tabIndex={0} aria-label="Analytical simulation map" aria-describedby={navigationHintId} style={{ cursor: "grab", touchAction: "none" }} />
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

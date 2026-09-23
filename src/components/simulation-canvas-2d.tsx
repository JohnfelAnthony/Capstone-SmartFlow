import * as React from "react"

import { getVisualNetwork, type VisualLane, type VisualNetwork, type VisualPoint, type VisualRoad, type VisualSignalGroup } from "@/api/visual-network"
import type { RenderFrame, RenderPedestrian, RenderVehicle } from "@/simulation/frame-types"

type CanvasTransform = {
  scale: number
  ox: number
  oy: number
  width: number
  height: number
}

type SignalColor = "red" | "yellow" | "green" | "off"

const colors = {
  grass: "#2e8b00",
  road: "#333333",
  internalRoad: "#3e3e3e",
  sidewalk: "#999999",
  lane: "#ffffff",
  curb: "#cccccc",
  crosswalk: "#ffffff",
  vehicle: "#ffd700",
  pedestrian: "#ff8c00",
  emergency: "#ffffff",
  emergencyMark: "#00ff00",
  emergencyRed: "#ff0000",
  emergencyBlue: "#0000ff",
  red: "#ff0000",
  yellow: "#ffd84d",
  green: "#00ff00",
  off: "#333333",
  constraint: "#ff0000",
}

const carPalette = [
  "#ffd21f",
  "#f97316",
  "#ef4444",
  "#22c55e",
  "#38bdf8",
  "#2563eb",
  "#f8fafc",
  "#a3a3a3",
]

function hashIndex(value: string, modulo: number) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0
  }
  return Math.abs(hash) % modulo
}

function vehicleColor(vehicle: RenderVehicle) {
  if (vehicle.emergency || vehicle.visual_type === "emergency") return colors.emergency
  return carPalette[hashIndex(vehicle.id, carPalette.length)]
}

function toCanvas(point: VisualPoint, transform: CanvasTransform) {
  return {
    x: point.x * transform.scale + transform.ox,
    y: -point.y * transform.scale + transform.oy,
  }
}

function configureTransform(network: VisualNetwork, width: number, height: number): CanvasTransform {
  let minX = network.bounds?.min_x ?? -50
  let maxX = network.bounds?.max_x ?? 50
  let minY = network.bounds?.min_y ?? -50
  let maxY = network.bounds?.max_y ?? 50

  const signalShape = network.signals[0]?.shape
  if (network.scope.mode !== "connected-network" && signalShape?.length) {
    minX = Math.min(...signalShape.map((point) => point.x)) - 15
    maxX = Math.max(...signalShape.map((point) => point.x)) + 15
    minY = Math.min(...signalShape.map((point) => point.y)) - 15
    maxY = Math.max(...signalShape.map((point) => point.y)) + 15
  }

  const spanX = Math.max(maxX - minX, 1)
  const spanY = Math.max(maxY - minY, 1)
  const scale = Math.min((width * 0.9) / spanX, (height * 0.9) / spanY)
  const centerX = (minX + maxX) / 2
  const centerY = (minY + maxY) / 2

  return {
    scale,
    ox: width / 2 - centerX * scale,
    oy: height / 2 + centerY * scale,
    width,
    height,
  }
}

function drawPolygon(ctx: CanvasRenderingContext2D, shape: VisualPoint[], transform: CanvasTransform, fillColor: string, strokeColor?: string, lineWidth = 1) {
  if (shape.length < 3) return
  const first = toCanvas(shape[0], transform)
  ctx.beginPath()
  ctx.moveTo(first.x, first.y)
  shape.slice(1).forEach((point) => {
    const next = toCanvas(point, transform)
    ctx.lineTo(next.x, next.y)
  })
  ctx.closePath()
  ctx.fillStyle = fillColor
  ctx.fill()
  if (strokeColor) {
    ctx.strokeStyle = strokeColor
    ctx.lineWidth = lineWidth
    ctx.stroke()
  }
}

function drawPolyline(ctx: CanvasRenderingContext2D, shape: VisualPoint[], transform: CanvasTransform, color: string, width: number, dashed = false) {
  if (shape.length < 2) return
  const first = toCanvas(shape[0], transform)
  ctx.beginPath()
  ctx.moveTo(first.x, first.y)
  shape.slice(1).forEach((point) => {
    const next = toCanvas(point, transform)
    ctx.lineTo(next.x, next.y)
  })
  ctx.strokeStyle = color
  ctx.lineWidth = width
  ctx.lineCap = "butt"
  ctx.lineJoin = "miter"
  if (dashed) ctx.setLineDash([transform.scale * 2, transform.scale * 2])
  ctx.stroke()
  ctx.setLineDash([])
}

function expandLaneToPolygon(shape: VisualPoint[], width: number) {
  if (shape.length < 2) return []
  const halfWidth = width / 2
  const leftEdge: VisualPoint[] = []
  const rightEdge: VisualPoint[] = []

  shape.forEach((point, index) => {
    let dx: number
    let dy: number
    if (index === 0) {
      dx = shape[1].x - point.x
      dy = shape[1].y - point.y
    } else if (index === shape.length - 1) {
      dx = point.x - shape[index - 1].x
      dy = point.y - shape[index - 1].y
    } else {
      const dx1 = point.x - shape[index - 1].x
      const dy1 = point.y - shape[index - 1].y
      const dx2 = shape[index + 1].x - point.x
      const dy2 = shape[index + 1].y - point.y
      const len1 = Math.hypot(dx1, dy1) || 1
      const len2 = Math.hypot(dx2, dy2) || 1
      dx = dx1 / len1 + dx2 / len2
      dy = dy1 / len1 + dy2 / len2
    }

    const length = Math.hypot(dx, dy)
    if (length <= 0) return
    const nx = -dy / length
    const ny = dx / length
    leftEdge.push({ x: point.x + nx * halfWidth, y: point.y + ny * halfWidth })
    rightEdge.unshift({ x: point.x - nx * halfWidth, y: point.y - ny * halfWidth })
  })

  return leftEdge.concat(rightEdge)
}

function isPedestrianLane(lane: VisualLane) {
  return String(lane.allow || "").includes("pedestrian")
}

function extrapolateLaneShape(shape: VisualPoint[], road: VisualRoad, distance = 1000) {
  if (shape.length < 2) return shape
  const nextShape = [...shape]

  if (road.toward_intersection) {
    const first = shape[0]
    const second = shape[1]
    const dx = first.x - second.x
    const dy = first.y - second.y
    const length = Math.hypot(dx, dy)
    if (length > 0) nextShape[0] = { x: first.x + (dx / length) * distance, y: first.y + (dy / length) * distance }
  }

  if (road.away_from_intersection) {
    const last = shape[shape.length - 1]
    const beforeLast = shape[shape.length - 2]
    const dx = last.x - beforeLast.x
    const dy = last.y - beforeLast.y
    const length = Math.hypot(dx, dy)
    if (length > 0) nextShape[nextShape.length - 1] = { x: last.x + (dx / length) * distance, y: last.y + (dy / length) * distance }
  }

  return nextShape
}

function drawCrosswalk(ctx: CanvasRenderingContext2D, lane: VisualLane, transform: CanvasTransform) {
  const shape = lane.shape
  if (shape.length < 2) return
  const start = toCanvas(shape[0], transform)
  const end = toCanvas(shape[shape.length - 1], transform)
  const dx = end.x - start.x
  const dy = end.y - start.y
  const pixelLength = Math.hypot(dx, dy)
  if (pixelLength < 1) return

  const sumoDx = shape[shape.length - 1].x - shape[0].x
  const sumoDy = shape[shape.length - 1].y - shape[0].y
  const sumoLength = Math.hypot(sumoDx, sumoDy)
  if (sumoLength < 1) return

  const barWidth = 0.5
  const gap = 0.5
  const count = Math.floor(sumoLength / (barWidth + gap))
  const pixelWidth = (lane.width || 4) * transform.scale
  const pixelBarWidth = barWidth * transform.scale

  ctx.fillStyle = colors.crosswalk
  for (let index = 0; index < count; index += 1) {
    const t = (index * (barWidth + gap) + barWidth / 2) / sumoLength
    if (t > 1) break
    const x = start.x + dx * t
    const y = start.y + dy * t
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(Math.atan2(dy, dx))
    ctx.fillRect(-pixelBarWidth / 2, -pixelWidth / 2, pixelBarWidth, pixelWidth)
    ctx.restore()
  }
}

function drawDashPolygons(ctx: CanvasRenderingContext2D, network: VisualNetwork, transform: CanvasTransform) {
  network.polygons
    .slice()
    .sort((first, second) => first.layer - second.layer)
    .forEach((polygon) => {
      if (polygon.shape.length < 3) return
      ctx.save()
      ctx.translate(transform.scale * 0.45, transform.scale * 0.55)
      drawPolygon(ctx, polygon.shape, transform, "rgba(9, 18, 24, 0.24)")
      ctx.restore()

      let color = polygon.color
      if (!color || color === "#808080" || color === "red") {
        const palette = ["#526b7a", "#7a8f55", "#9b7352", "#a26455", "#1f5f7a", "#8b6f9f", "#4b6b5a", "#8c7d55"]
        color = palette[hashIndex(polygon.id, palette.length)]
      }
      drawPolygon(ctx, polygon.shape, transform, color, "rgba(8, 18, 24, 0.55)", Math.max(1, transform.scale * 0.08))

      const centroid = polygon.shape.reduce(
        (accumulator, point) => ({ x: accumulator.x + point.x, y: accumulator.y + point.y }),
        { x: 0, y: 0 }
      )
      const center = { x: centroid.x / polygon.shape.length, y: centroid.y / polygon.shape.length }
      const roofShape = polygon.shape.map((point) => ({
        x: center.x + (point.x - center.x) * 0.82,
        y: center.y + (point.y - center.y) * 0.82,
      }))
      drawPolygon(ctx, roofShape, transform, "rgba(0, 0, 0, 0.35)", "rgba(255, 255, 255, 0.16)", Math.max(1, transform.scale * 0.06))
    })
}

function drawStaticNetwork(ctx: CanvasRenderingContext2D, network: VisualNetwork, transform: CanvasTransform) {
  ctx.fillStyle = colors.grass
  ctx.fillRect(0, 0, transform.width, transform.height)
  drawDashPolygons(ctx, network, transform)

  network.roads.forEach((road) => {
    road.lanes.forEach((lane) => {
      if (!isPedestrianLane(lane)) return
      const polygon = expandLaneToPolygon(extrapolateLaneShape(lane.shape, road), lane.width || 2)
      drawPolygon(ctx, polygon, transform, colors.sidewalk, colors.curb, 1.5)
    })

    let previousVehicleShape: VisualPoint[] | null = null
    road.lanes.forEach((lane) => {
      if (isPedestrianLane(lane)) return
      const shape = extrapolateLaneShape(lane.shape, road)
      const polygon = expandLaneToPolygon(shape, lane.width || 3.2)
      drawPolygon(ctx, polygon, transform, colors.road)
      if (previousVehicleShape) {
        const previousShape = previousVehicleShape
        const separator = shape.slice(0, Math.min(shape.length, previousShape.length)).map((point, index) => ({
          x: (point.x + previousShape[index].x) / 2,
          y: (point.y + previousShape[index].y) / 2,
        }))
        drawPolyline(ctx, separator, transform, colors.lane, Math.max(1, transform.scale * 0.15), true)
      }
      previousVehicleShape = shape
    })
  })

  network.internal_lanes.forEach((road) => {
    road.lanes.forEach((lane) => {
      const polygon = expandLaneToPolygon(lane.shape, lane.width || (isPedestrianLane(lane) ? 2 : 3))
      drawPolygon(ctx, polygon, transform, isPedestrianLane(lane) ? colors.sidewalk : colors.internalRoad)
    })
  })

  network.signals.forEach((signal) => {
    drawPolygon(ctx, signal.shape, transform, colors.road)
  })

  network.walking_areas.forEach((area) => {
    area.lanes.forEach((lane) => {
      drawPolygon(ctx, lane.shape, transform, colors.sidewalk, colors.curb, 1.5)
    })
  })

  network.crossings.forEach((crossing) => {
    crossing.lanes.forEach((lane) => {
      drawCrosswalk(ctx, lane, transform)
    })
  })
}

function canonicalSignalColor(state: string | undefined): SignalColor {
  const normalized = String(state || "").toLowerCase()
  if (normalized.includes("green") || normalized.includes("g")) return "green"
  if (normalized.includes("yellow") || normalized.includes("y")) return "yellow"
  if (normalized.includes("red") || normalized.includes("r")) return "red"
  return "off"
}

function colorForSignalHeading(heading: number, frame: RenderFrame | null): SignalColor {
  if (!frame) return "red"
  const normalizedHeading = ((heading % 360) + 360) % 360
  const isNorthSouth = normalizedHeading <= 45 || normalizedHeading >= 315 || (normalizedHeading >= 135 && normalizedHeading <= 225)
  return canonicalSignalColor(isNorthSouth ? frame.ns_state : frame.ew_state)
}

function resolveSignalColor(group: VisualSignalGroup, frame: RenderFrame | null): SignalColor {
  const trafficLightState = frame?.traffic_lights?.[group.signal_id]
  if (trafficLightState?.state && group.link_indices.length > 0) {
    let bestState = "r"
    group.link_indices.forEach((index) => {
      const character = trafficLightState.state[index]?.toLowerCase()
      if (character === "g") bestState = "g"
      else if (character === "y" && bestState !== "g") bestState = "y"
    })
    if (bestState === "g") return "green"
    if (bestState === "y") return "yellow"
    return "red"
  }

  return colorForSignalHeading(group.heading, frame)
}

function drawSignals(ctx: CanvasRenderingContext2D, network: VisualNetwork, transform: CanvasTransform, frame: RenderFrame | null) {
  network.signal_groups.forEach((group) => {
    if (group.kind === "pedestrian" || group.stop_line.length < 2) return
    const signalColor = resolveSignalColor(group, frame)
    drawPolyline(ctx, group.stop_line, transform, colors[signalColor], Math.max(3, 1.2 * transform.scale))
  })
}

function drawRoundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  const safeRadius = Math.min(radius, Math.abs(width) / 2, Math.abs(height) / 2)
  ctx.beginPath()
  ctx.moveTo(x + safeRadius, y)
  ctx.lineTo(x + width - safeRadius, y)
  ctx.quadraticCurveTo(x + width, y, x + width, y + safeRadius)
  ctx.lineTo(x + width, y + height - safeRadius)
  ctx.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height)
  ctx.lineTo(x + safeRadius, y + height)
  ctx.quadraticCurveTo(x, y + height, x, y + height - safeRadius)
  ctx.lineTo(x, y + safeRadius)
  ctx.quadraticCurveTo(x, y, x + safeRadius, y)
  ctx.closePath()
}

function drawVehicle(ctx: CanvasRenderingContext2D, vehicle: RenderVehicle, transform: CanvasTransform) {
  const position = toCanvas({ x: vehicle.x, y: vehicle.y }, transform)
  const length = Math.max(3.6, Number(vehicle.length || 4.5)) * transform.scale
  const width = Math.max(1.4, Number(vehicle.width || 1.8)) * transform.scale
  const angle = ((Number(vehicle.angle || 0) - 90) * Math.PI) / 180
  const isEmergency = vehicle.emergency || vehicle.visual_type === "ambulance" || vehicle.visual_type === "emergency"

  ctx.save()
  ctx.translate(position.x, position.y)
  ctx.rotate(angle)

  if (isEmergency) {
    ctx.fillStyle = colors.emergency
    ctx.fillRect(-length, -width / 2, length, width)
    ctx.fillStyle = colors.emergencyMark
    const crossWidth = width * 0.4
    const crossHeight = crossWidth * 0.3
    const crossX = -length / 2
    ctx.fillRect(crossX - crossHeight / 2, -crossWidth / 2, crossHeight, crossWidth)
    ctx.fillRect(crossX - crossWidth / 2, -crossHeight / 2, crossWidth, crossHeight)
    ctx.fillStyle = Math.floor(Date.now() / 250) % 2 === 0 ? colors.emergencyRed : colors.emergencyBlue
    ctx.fillRect(-length * 0.25 - (length * 0.15) / 2, -(width * 0.8) / 2, length * 0.15, width * 0.8)
  } else {
    const bodyTop = -width * 0.5
    const bodyBottom = width * 0.5
    const rearX = -length
    const noseX = 0
    const shoulderX = -length * 0.18
    const tailInset = Math.max(1.2, width * 0.12)
    const noseInset = Math.max(1.4, width * 0.18)

    ctx.beginPath()
    ctx.moveTo(rearX + tailInset, bodyTop)
    ctx.lineTo(shoulderX, bodyTop)
    ctx.quadraticCurveTo(noseX - noseInset, bodyTop, noseX, -width * 0.2)
    ctx.lineTo(noseX, width * 0.2)
    ctx.quadraticCurveTo(noseX - noseInset, bodyBottom, shoulderX, bodyBottom)
    ctx.lineTo(rearX + tailInset, bodyBottom)
    ctx.quadraticCurveTo(rearX, bodyBottom, rearX, bodyBottom - tailInset)
    ctx.lineTo(rearX, bodyTop + tailInset)
    ctx.quadraticCurveTo(rearX, bodyTop, rearX + tailInset, bodyTop)
    ctx.closePath()
    ctx.fillStyle = vehicleColor(vehicle)
    ctx.fill()
    ctx.lineWidth = Math.max(1, transform.scale * 0.12)
    ctx.strokeStyle = vehicle.stopped ? colors.red : "rgba(82, 61, 0, 0.75)"
    ctx.stroke()

    const wheelRadius = Math.max(1.1, width * 0.13)
    ctx.fillStyle = "rgba(20,20,20,0.86)"
    ;[-length * 0.78, -length * 0.26].forEach((wheelX) => {
      ctx.beginPath()
      ctx.arc(wheelX, bodyTop + wheelRadius * 0.35, wheelRadius, 0, Math.PI * 2)
      ctx.arc(wheelX, bodyBottom - wheelRadius * 0.35, wheelRadius, 0, Math.PI * 2)
      ctx.fill()
    })

    ctx.fillStyle = "rgba(26, 50, 70, 0.72)"
    drawRoundedRect(ctx, -length * 0.36, -width * 0.36, length * 0.16, width * 0.72, Math.max(1, width * 0.1))
    ctx.fill()
    drawRoundedRect(ctx, -length * 0.64, -width * 0.32, length * 0.16, width * 0.64, Math.max(1, width * 0.1))
    ctx.fill()

    ctx.fillStyle = "rgba(255,255,190,0.85)"
    ctx.fillRect(-length * 0.05, -width * 0.28, Math.max(1, length * 0.035), width * 0.18)
    ctx.fillRect(-length * 0.05, width * 0.1, Math.max(1, length * 0.035), width * 0.18)
  }

  ctx.restore()
}

function drawPedestrian(ctx: CanvasRenderingContext2D, pedestrian: RenderPedestrian, transform: CanvasTransform) {
  const center = toCanvas({ x: pedestrian.x, y: pedestrian.y }, transform)
  const radius = Math.max(2.5, 0.5 * transform.scale)
  ctx.fillStyle = pedestrian.stopped ? colors.yellow : colors.pedestrian
  ctx.beginPath()
  ctx.arc(center.x, center.y, radius, 0, Math.PI * 2)
  ctx.fill()
}

function drawConstraint(ctx: CanvasRenderingContext2D, frame: RenderFrame, transform: CanvasTransform) {
  const marker = frame.visual.constraint_marker
  if (!marker?.active) return
  const center = toCanvas({ x: marker.x, y: marker.y }, transform)
  ctx.strokeStyle = colors.constraint
  ctx.lineWidth = 3
  ctx.beginPath()
  ctx.moveTo(center.x - 12, center.y - 12)
  ctx.lineTo(center.x + 12, center.y + 12)
  ctx.moveTo(center.x + 12, center.y - 12)
  ctx.lineTo(center.x - 12, center.y + 12)
  ctx.stroke()
}

function drawDynamicEntities(ctx: CanvasRenderingContext2D, frame: RenderFrame | null, transform: CanvasTransform) {
  if (!frame) return
  frame.vehicles.forEach((vehicle) => drawVehicle(ctx, vehicle, transform))
  frame.pedestrians.forEach((pedestrian) => drawPedestrian(ctx, pedestrian, transform))
  drawConstraint(ctx, frame, transform)
}

export function SimulationCanvas2D({
  frame,
  intersectionId,
}: {
  frame: RenderFrame | null
  intersectionId: string | null
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null)
  const [network, setNetwork] = React.useState<VisualNetwork | null>(null)
  const [message, setMessage] = React.useState("Loading 2D map...")
  const [resizeTick, setResizeTick] = React.useState(0)

  React.useEffect(() => {
    let isMounted = true
    /* eslint-disable react-hooks/set-state-in-effect */
    setMessage("Loading 2D map...")
    getVisualNetwork(intersectionId)
      .then((payload) => {
        if (!isMounted) return
        setNetwork(payload)
        setMessage("")
      })
      .catch((error) => {
        if (!isMounted) return
        setNetwork(null)
        setMessage(error instanceof Error ? error.message : "Unable to load 2D map.")
      })
    return () => {
      isMounted = false
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [intersectionId])

  React.useEffect(() => {
    const canvas = canvasRef.current
    const parent = canvas?.parentElement
    if (!parent) return undefined

    const observer = new ResizeObserver(() => {
      setResizeTick((current) => current + 1)
    })
    observer.observe(parent)
    return () => observer.disconnect()
  }, [])

  React.useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !network) return
    const parent = canvas.parentElement
    const width = Math.max(parent?.clientWidth ?? 640, 320)
    const height = Math.max(parent?.clientHeight ?? 410, 280)
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)

    canvas.width = Math.floor(width * dpr)
    canvas.height = Math.floor(height * dpr)
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`

    const ctx = canvas.getContext("2d")
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    const transform = configureTransform(network, width, height)
    drawStaticNetwork(ctx, network, transform)
    drawSignals(ctx, network, transform, frame)
    drawDynamicEntities(ctx, frame, transform)
  }, [frame, network, resizeTick])

  return (
    <div className="sf-canvas2d-shell">
      <canvas ref={canvasRef} className="sf-canvas2d" aria-label="2D simulation renderer" />
      {message ? <div className="sf-canvas2d-message">{message}</div> : null}
    </div>
  )
}

import * as React from "react"

import { apiWebSocketUrl } from "@/api/client"
import type { RenderFrame } from "@/simulation/frame-types"

type SimulationSocketStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed" | "error"

const RECONNECT_BASE_DELAY_MS = 500
const RECONNECT_MAX_DELAY_MS = 5000
const RECONNECT_JITTER_MS = 250

function reconnectDelay(attempt: number) {
  const exponentialDelay = RECONNECT_BASE_DELAY_MS * 2 ** Math.max(attempt - 1, 0)
  return Math.min(exponentialDelay, RECONNECT_MAX_DELAY_MS) + Math.round(Math.random() * RECONNECT_JITTER_MS)
}

function validFrame(value: unknown): value is RenderFrame {
  if (!value || typeof value !== "object") return false
  const frame = value as Partial<RenderFrame>
  const vehicles = frame.vehicles
  const pedestrians = frame.pedestrians
  const visual = frame.visual
  if (!Number.isFinite(frame.time) || !Number.isFinite(frame.render_ts) || !Number.isFinite(frame.step_length) ||
    typeof frame.status !== "string" || typeof frame.flow_state !== "string" ||
    typeof frame.intersection_id !== "string" || typeof frame.phase !== "string" ||
    !Number.isSafeInteger(frame.vehicle_count) || !Number.isSafeInteger(frame.pedestrian_count) ||
    !Array.isArray(vehicles) || !Array.isArray(pedestrians) ||
    vehicles.length > 1000 || pedestrians.length > 1000 ||
    !visual || !Array.isArray(visual.closed_lanes) || !visual.closed_lanes.every((lane) => typeof lane === "string") ||
    !visual.slow_lanes || typeof visual.slow_lanes !== "object" || Array.isArray(visual.slow_lanes) ||
    !Object.values(visual.slow_lanes).every(Number.isFinite) ||
    !frame.traffic_lights || typeof frame.traffic_lights !== "object" ||
    !frame.junction_controls || typeof frame.junction_controls !== "object") return false
  return vehicles.every((vehicle) => vehicle && typeof vehicle.id === "string" &&
    Number.isFinite(vehicle.x) && Number.isFinite(vehicle.y) && Number.isFinite(vehicle.angle) &&
    Number.isFinite(vehicle.length) && Number.isFinite(vehicle.width)) &&
    pedestrians.every((pedestrian) => pedestrian && typeof pedestrian.id === "string" &&
      Number.isFinite(pedestrian.x) && Number.isFinite(pedestrian.y)) &&
    Object.values(frame.traffic_lights).every((signal) => signal && typeof signal.state === "string")
}

export function useSimulationSocket({ enabled }: { enabled: boolean }) {
  const [status, setStatus] = React.useState<SimulationSocketStatus>("idle")
  const [latestFrame, setLatestFrame] = React.useState<RenderFrame | null>(null)
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null)
  const [reconnectAttempt, setReconnectAttempt] = React.useState(0)
  const [nextRetryMs, setNextRetryMs] = React.useState<number | null>(null)
  const reconnectAttemptRef = React.useRef(0)

  React.useEffect(() => {
    const socketUrl = apiWebSocketUrl("/ws/simulation")
    let closedByEffect = false
    let reconnectTimer: number | null = null
    let socket: WebSocket | null = null

    function clearReconnectTimer() {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    function closeCurrentSocket() {
      if (socket && socket.readyState !== WebSocket.CLOSED) {
        socket.close()
      }
      socket = null
    }

    function scheduleReconnect() {
      if (closedByEffect) return
      clearReconnectTimer()
      const attempt = reconnectAttemptRef.current + 1
      const delayMs = reconnectDelay(attempt)
      reconnectAttemptRef.current = attempt
      setReconnectAttempt(attempt)
      setNextRetryMs(delayMs)
      setStatus("reconnecting")
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null
        connect()
      }, delayMs)
    }

    function connect() {
      if (closedByEffect) return
      closeCurrentSocket()
      setStatus(reconnectAttemptRef.current > 0 ? "reconnecting" : "connecting")
      setErrorMessage(null)
      socket = new WebSocket(socketUrl)

      socket.addEventListener("open", () => {
        if (closedByEffect) return
        reconnectAttemptRef.current = 0
        setReconnectAttempt(0)
        setNextRetryMs(null)
        setStatus("open")
      })

      socket.addEventListener("message", (event) => {
        try {
          const frame: unknown = JSON.parse(event.data)
          if (!validFrame(frame)) throw new Error("Invalid simulation frame")
          setLatestFrame(frame)
          setErrorMessage(null)
        } catch {
          setErrorMessage("Simulation stream sent an unreadable frame.")
          socket?.close(1011, "Invalid frame")
        }
      })

      socket.addEventListener("close", (event) => {
        if (closedByEffect) return
        socket = null

        if (event.code === 1000) {
          setStatus("closed")
          setNextRetryMs(null)
          setErrorMessage(null)
          return
        }

        if (event.code === 1008) {
          setStatus("error")
          setNextRetryMs(null)
          setErrorMessage("Simulation stream permission expired. Sign in again to continue streaming.")
          return
        }

        scheduleReconnect()
      })

      socket.addEventListener("error", () => {
        if (closedByEffect) return
        setStatus("error")
      })
    }

    if (!enabled) {
      reconnectAttemptRef.current = 0
      queueMicrotask(() => {
        if (closedByEffect) return
        setStatus("idle")
        setLatestFrame(null)
        setErrorMessage(null)
        setReconnectAttempt(0)
        setNextRetryMs(null)
      })
      return () => { closedByEffect = true }
    }

    connect()

    return () => {
      closedByEffect = true
      clearReconnectTimer()
      closeCurrentSocket()
    }
  }, [enabled])

  return { latestFrame, status, errorMessage, reconnectAttempt, nextRetryMs }
}

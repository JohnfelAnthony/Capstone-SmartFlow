import * as React from "react"

import { ApiError } from "@/api/client"
import { listScenarios, type ApiScenario } from "@/api/scenarios"
import { getNativeScenarioOptions, resolveNativeScenario, type NativeScenarioConfig, type NativeScenarioOptions } from "@/api/native-scenario"
import { listRLModels, type RLModelRecord } from "@/api/rl"
import {
  getSimulationState,
  listSimulationRuns,
  loadPlayback,
  pauseSimulation,
  resetSimulation,
  resumeSimulation,
  seekPlayback,
  setSimulationSpeed,
  startSimulation,
  startPlayback,
  stopSimulation,
  type SimulationRunRecord,
  type SimulationStatePayload,
} from "@/api/simulation"
import { SetupCard, SignalControlCard, SimControlBar } from "@/components/dashboard-controls"
import { DashboardKpis } from "@/components/dashboard-kpis"
import { DashboardTrends, type TrendPoint } from "@/components/dashboard-trends"
import { SimulationVisualization } from "@/simulation/simulation-visualization"
import { renderFrameFromSimulation, mergeRenderFrame } from "@/simulation/render-frame-adapter"
import { useSimulationSocket } from "@/hooks/useSimulationSocket"
import type { RenderFrame } from "@/simulation/frame-types"
import type { VisualizationMode } from "@/simulation/visualization-mode"
import { NO_SIGNAL_LABEL } from "@/lib/control-labels"
import { pickReferenceRun, type ReferenceRun } from "@/lib/reference-run"
import { metricCatalog, metricEngineVersion, metricValue } from "@/lib/metrics"

function compactNumber(value: number, digits = 0) {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

function buildChartPoint(simulation: SimulationStatePayload): TrendPoint & { bucket: number } {
  const time = Math.max(0, Math.floor(Number(simulation.state.time ?? 0)))
  const metrics = simulation.state.metrics
  return {
    bucket: time,
    timeLabel: `${time}s`,
    avgWait: metricValue(metrics, "avg_wait"),
    avgQueue: metricValue(metrics, "avg_queue"),
  }
}

function apiMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "Unable to reach the SMARTFLOW API."
}

export function DashboardPage({
  currentUserId,
  isAdmin,
  canRunSimulation,
  visualizationMode,
  onVisualizationModeChange,
}: {
  currentUserId: number
  isAdmin: boolean
  canRunSimulation: boolean
  visualizationMode: VisualizationMode
  onVisualizationModeChange: (mode: VisualizationMode) => void
}) {
  const [scenarios, setScenarios] = React.useState<ApiScenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = React.useState("")
  const [durationSeconds, setDurationSeconds] = React.useState("300")
  const [scenarioResolution, setScenarioResolution] = React.useState<{ id: string; config: NativeScenarioConfig | null } | null>(null)
  const [nativeOptions, setNativeOptions] = React.useState<NativeScenarioOptions | null>(null)
  const [models, setModels] = React.useState<RLModelRecord[]>([])
  const [controlMode, setControlMode] = React.useState("fixed-time")
  const [seed, setSeed] = React.useState("42")
  const [simulation, setSimulation] = React.useState<SimulationStatePayload | null>(null)
  const [renderFrame, setRenderFrame] = React.useState<RenderFrame | null>(null)
  const [seekRevision, setSeekRevision] = React.useState(0)
  const [renderPerformance, setRenderPerformance] = React.useState<{ mode: VisualizationMode; fps: number; p95FrameMs: number; drawCalls: number } | null>(null)
  const handleRenderPerformance = React.useCallback((sample: { fps: number; p95FrameMs: number; drawCalls: number }) => {
    setRenderPerformance({ ...sample, mode: visualizationMode })
  }, [visualizationMode])
  const showPerformance = new URLSearchParams(window.location.search).has("perf")
  const [recordedRuns, setRecordedRuns] = React.useState<SimulationRunRecord[]>([])
  const [selectedRecordedRunId, setSelectedRecordedRunId] = React.useState("")
  const [chartHistory, setChartHistory] = React.useState<TrendPoint[]>([])
  const [reference, setReference] = React.useState<ReferenceRun | null>(null)
  const [notice, setNotice] = React.useState("Loading simulation workspace...")
  const [isBusy, setIsBusy] = React.useState(false)
  const lastStateRefreshAt = React.useRef(0)
  const stateRefreshInFlight = React.useRef(false)
  const lastChartBucket = React.useRef<number | null>(null)

  const canConfigure = Boolean(selectedScenarioId)
  const canOperate = canRunSimulation && (simulation?.owner_user_id == null || simulation.owner_user_id === currentUserId)
  const scenarioConfig = scenarioResolution?.id === selectedScenarioId ? scenarioResolution.config : null
  const selectedScenario = scenarios.find((scenario) => String(scenario.id) === selectedScenarioId) ?? null
  const streamEnabled = simulation?.status === "running" || simulation?.status === "paused"
  const {
    latestFrame,
    status: streamStatus,
    errorMessage: streamErrorMessage,
    reconnectAttempt,
    nextRetryMs,
  } = useSimulationSocket({ enabled: streamEnabled })
  const streamNotice = React.useMemo(() => {
    if (streamErrorMessage) return streamErrorMessage
    if (streamStatus !== "reconnecting" || reconnectAttempt < 3) return null
    const retrySeconds = nextRetryMs ? Math.max(1, Math.ceil(nextRetryMs / 1000)) : 1
    return `Simulation stream is reconnecting. Attempt ${reconnectAttempt}, retrying in ${retrySeconds}s.`
  }, [nextRetryMs, reconnectAttempt, streamErrorMessage, streamStatus])

  const applySimulationSnapshot = React.useCallback((nextSimulation: SimulationStatePayload, replaceRenderFrame = true) => {
    setSimulation(nextSimulation)
    if (nextSimulation.render_frame_error) {
      setRenderFrame(null)
      setNotice(nextSimulation.render_frame_error)
      return false
    }
    if (replaceRenderFrame) setRenderFrame(renderFrameFromSimulation(nextSimulation))
    return true
  }, [])

  React.useEffect(() => {
    const metadataBudgetRejected = streamErrorMessage?.startsWith("Render metadata exceeds ") ||
      streamErrorMessage?.startsWith("Simulation render frame exceeded the stream budget.")
    if (!metadataBudgetRejected) return
    let active = true
    queueMicrotask(() => { if (active) setRenderFrame(null) })
    return () => { active = false }
  }, [streamErrorMessage])

  const applySimulationAction = React.useCallback(
    async (action: () => Promise<{ message: string; simulation: SimulationStatePayload }>, successMessage?: string) => {
      setIsBusy(true)
      try {
        const response = await action()
        if (applySimulationSnapshot(response.simulation)) setNotice(successMessage ?? response.message)
      } catch (error) {
        setNotice(apiMessage(error))
      } finally {
        setIsBusy(false)
      }
    },
    [applySimulationSnapshot]
  )

  const loadRecordedRuns = React.useCallback(async () => {
    const response = await listSimulationRuns({ runMode: "pre-record", limit: 30 })
    setRecordedRuns(response.runs)
    setSelectedRecordedRunId((current) => {
      if (current && response.runs.some((run) => String(run.id) === current)) return current
      const firstCompleted = response.runs.find((run) => run.status === "completed")
      return firstCompleted ? String(firstCompleted.id) : ""
    })
  }, [])

  React.useEffect(() => {
    let isMounted = true

    async function loadDashboard() {
      setIsBusy(true)
      try {
        const [scenarioResponse, simulationResponse, runsResponse, modelResponse, optionsResponse] = await Promise.all([
          listScenarios(),
          getSimulationState(),
          listSimulationRuns({ runMode: "pre-record", limit: 30 }),
          listRLModels(),
          getNativeScenarioOptions(),
        ])
        if (!isMounted) return

        const nextScenarios = [...scenarioResponse.scenarios].sort((a, b) => Number(b.engine_config.traffic_density === "single") - Number(a.engine_config.traffic_density === "single"))
        setScenarios(nextScenarios)
        const presentationAvailable = applySimulationSnapshot(simulationResponse)
        setRecordedRuns(runsResponse.runs)
        setModels(modelResponse.models)
        setNativeOptions(optionsResponse)
        const firstCompletedRun = runsResponse.runs.find((run) => run.status === "completed")
        setSelectedRecordedRunId(firstCompletedRun ? String(firstCompletedRun.id) : "")
        const activeScenarioId =
          simulationResponse.selected_scenario_id !== null
            ? String(simulationResponse.selected_scenario_id)
            : nextScenarios[0]
              ? String(nextScenarios[0].id)
              : ""
        setSelectedScenarioId(activeScenarioId)
        setSeed(String(simulationResponse.seed))
        setControlMode(simulationResponse.control_mode === "playback" ? "fixed-time" : simulationResponse.control_mode)
        if (presentationAvailable) setNotice("Simulation controls are connected to FastAPI.")
      } catch (error) {
        if (isMounted) setNotice(apiMessage(error))
      } finally {
        if (isMounted) setIsBusy(false)
      }
    }

    loadDashboard()
    return () => {
      isMounted = false
    }
  }, [applySimulationSnapshot])

  React.useEffect(() => {
    const scenarioId = Number(selectedScenarioId)
    if (!scenarioId) return
    let cancelled = false
    void resolveNativeScenario(scenarioId).then((response) => {
      if (!cancelled) setScenarioResolution({ id: selectedScenarioId, config: response.engine_config })
    }).catch((error) => {
      if (!cancelled) {
        setScenarioResolution({ id: selectedScenarioId, config: null })
        setNotice(apiMessage(error))
      }
    })
    return () => { cancelled = true }
  }, [selectedScenarioId])

  React.useEffect(() => {
    const hasGeneratingRun = recordedRuns.some((run) => run.status === "running")
    if (!hasGeneratingRun) return
    const intervalId = window.setInterval(() => {
      loadRecordedRuns().catch((error) => setNotice(apiMessage(error)))
    }, 3000)
    return () => window.clearInterval(intervalId)
  }, [loadRecordedRuns, recordedRuns])

  React.useEffect(() => {
    const intervalId = window.setInterval(() => {
      if (stateRefreshInFlight.current) return
      stateRefreshInFlight.current = true
      getSimulationState().then((nextSimulation) => {
        applySimulationSnapshot(nextSimulation, streamStatus !== "open")
      }).catch((error) => setNotice(apiMessage(error)))
        .finally(() => { stateRefreshInFlight.current = false })
    }, 2000)
    return () => window.clearInterval(intervalId)
  }, [applySimulationSnapshot, streamStatus])

  React.useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!latestFrame) return

    setRenderFrame(latestFrame)
    setSimulation((current) => mergeRenderFrame(current, latestFrame))

    const now = Date.now()
    const shouldRefreshFullState = now - lastStateRefreshAt.current >= 1000
    if (!shouldRefreshFullState || stateRefreshInFlight.current) return

    lastStateRefreshAt.current = now
    stateRefreshInFlight.current = true
    getSimulationState()
      .then((nextSimulation) => {
        applySimulationSnapshot(nextSimulation, streamStatus !== "open")
      })
      .catch((error) => setNotice(apiMessage(error)))
      .finally(() => {
        stateRefreshInFlight.current = false
      })
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [applySimulationSnapshot, latestFrame, streamStatus])

  React.useEffect(() => {
    if (!simulation) return
    const nextPoint = buildChartPoint(simulation)
    if (lastChartBucket.current === nextPoint.bucket) return
    lastChartBucket.current = nextPoint.bucket
    setChartHistory((current) => [...current, { timeLabel: nextPoint.timeLabel, avgWait: nextPoint.avgWait, avgQueue: nextPoint.avgQueue }].slice(-240))
  }, [simulation])

  const activeRunId = simulation?.active_run_id ?? null
  const currentExperiment = simulation?.state.experiment
  // Recompute only when the run's identity changes, not on every streamed frame.
  const currentIdentity = React.useMemo(() => JSON.stringify(currentExperiment ?? {}), [currentExperiment])
  React.useEffect(() => {
    const scenarioId = Number(selectedScenarioId)
    if (!scenarioId) return
    let cancelled = false
    listSimulationRuns({ scenarioId, status: "completed", limit: 50 }).then((response) => {
      // A reference must come from the current engine and share the complete experiment identity (network, seed, duration,
      // measurement window, demand and settings); the newest no-signal run is preferred, a matching fixed-time run is the fallback.
      const readable = response.runs.filter((run) => metricEngineVersion(run.metrics) === metricCatalog.engine_version)
      if (!cancelled) setReference(pickReferenceRun(readable, { experiment: JSON.parse(currentIdentity) as Record<string, unknown>, activeRunId }))
    }).catch(() => { if (!cancelled) setReference(null) })
    return () => { cancelled = true }
  }, [selectedScenarioId, currentIdentity, activeRunId])

  function handleScenarioChange(scenarioId: string) {
    setSelectedScenarioId(scenarioId)
    setControlMode("fixed-time")
  }

  const handleThreeUnavailable = React.useCallback(
    (message: string) => {
      setNotice(message)
      onVisualizationModeChange("2d")
    },
    [onVisualizationModeChange]
  )

  function handleStart() {
    if (!canConfigure) {
      setNotice("Select and apply a scenario before starting.")
      return
    }
    const parsedSeed = Number(seed)
    if (!Number.isInteger(parsedSeed) || parsedSeed < 0 || parsedSeed > 4294967295 || seed.trim() === "") {
      setNotice("Run seed must be a whole number from 0 to 4294967295.")
      return
    }
    applySimulationAction(() =>
      startSimulation({
        scenario_id: Number(selectedScenarioId),
        duration_seconds: Number(durationSeconds),
        seed: parsedSeed,
        control_mode: controlMode,
      })
    )
  }

  function handlePauseOrResume() {
    if (simulation?.status === "paused") {
      applySimulationAction(resumeSimulation)
      return
    }
    applySimulationAction(pauseSimulation)
  }

  function handleLoadRecording() {
    if (!selectedRecordedRunId) {
      setNotice("Select a completed recording first.")
      return
    }
    applySimulationAction(() => loadPlayback(Number(selectedRecordedRunId)))
  }

  function handleStartPlayback() {
    applySimulationAction(startPlayback)
  }

  async function handleSeekPlayback(frameIndex: number) {
    try {
      const response = await seekPlayback(frameIndex)
      if (applySimulationSnapshot(response.simulation)) {
        setSeekRevision(revision => revision + 1)
        setNotice(response.message)
      }
    } catch (error) {
      setNotice(apiMessage(error))
    }
  }

  const restrictedLanes = [
    ...(renderFrame?.visual.closed_lanes ?? []).map((id) => ({ id, detail: "closed to new entry" })),
    ...Object.entries(renderFrame?.visual.slow_lanes ?? {}).filter(([, factor]) => factor < 1).map(([id, factor]) => ({ id, detail: `${Math.round(factor * 100)}% speed` })),
  ]
  const ownershipNote = !canRunSimulation ? "Your role has view access only." : canOperate ? "" : "Controls are read-only until the owner resets the session."
  const hasConfiguredScenario = simulation?.selected_scenario_id != null && typeof simulation.state.dashboard?.current_scenario_name === "string"
  const scenarioTitle = hasConfiguredScenario ? String(simulation.state.dashboard?.current_scenario_name) : selectedScenario?.name ?? "No scenario selected"
  const statusLine = [scenarioTitle, streamNotice ?? notice, ownershipNote, streamEnabled && streamStatus !== "open" ? `Live stream ${streamStatus}; positions may be delayed.` : ""].filter(Boolean).join(" · ")
  const intersectionId = renderFrame?.intersection_id ??
    (typeof simulation?.state.scenario?.intersection_id === "string" ? simulation.state.scenario.intersection_id : null)
  const frozenConfig = simulation?.state.experiment?.config
  const recordedJunction = frozenConfig && typeof frozenConfig === "object" && "controlled_junction" in frozenConfig && typeof frozenConfig.controlled_junction === "string" ? frozenConfig.controlled_junction : null
  const isIdle = !["running", "paused"].includes(simulation?.status ?? "") && simulation?.control_mode !== "playback"
  const laneStreets = React.useMemo(() => Object.fromEntries((nativeOptions?.lanes ?? []).map((lane) => [lane.id, lane.road_name])), [nativeOptions])
  const selectedModel = models.find((model) => `${model.algorithm.toLowerCase()}:${model.id}` === controlMode)
  const controllerLabel = selectedModel ? `${selectedModel.algorithm} model #${selectedModel.id}` : controlMode === "no-signal" ? NO_SIGNAL_LABEL : "Fixed-time plan"

  return (
    <div className="flex flex-col gap-4 p-4 lg:p-6">
      <DashboardKpis metrics={simulation?.state.metrics} reference={reference} isReferenceRun={simulation?.control_mode === "no-signal"} />
      <SimulationVisualization frame={renderFrame} networkId={intersectionId}
        controlledJunction={Object.entries(renderFrame?.junction_controls ?? {}).find(([, control]) => control.selected_for_rl)?.[0] ?? recordedJunction ?? scenarioConfig?.controlled_junction}
        mode={visualizationMode} runKey={String(simulation?.active_run_id ?? "idle")} seekRevision={seekRevision} laneStreets={laneStreets}
        onUnavailable={handleThreeUnavailable} onPerformanceSample={showPerformance ? handleRenderPerformance : undefined}
        controlBar={<SimControlBar simulation={simulation} elapsedSeconds={renderFrame?.time ?? Number(simulation?.state.time ?? 0)} isBusy={isBusy} canOperate={canOperate} canStart={canConfigure}
          onStart={handleStart} onStartPlayback={handleStartPlayback} onPause={handlePauseOrResume} onStop={() => applySimulationAction(stopSimulation)} onReset={() => applySimulationAction(resetSimulation)}
          onSpeedChange={(value) => { void applySimulationAction(() => setSimulationSpeed(value)) }} onSeekPlayback={(frameIndex) => void handleSeekPlayback(frameIndex)} />}
        overlay={isIdle ? <SetupCard scenarios={scenarios} selectedScenarioId={selectedScenarioId} durationSeconds={durationSeconds} seed={seed} controllerLabel={controllerLabel}
          recordedRuns={recordedRuns} selectedRecordedRunId={selectedRecordedRunId} isBusy={isBusy} canOperate={canOperate} canTakeOver={!canOperate && isAdmin}
          onScenarioChange={handleScenarioChange} onDurationChange={setDurationSeconds} onSeedChange={setSeed} onStart={handleStart}
          onRecordedRunChange={setSelectedRecordedRunId} onLoadRecording={handleLoadRecording}
          onTakeOver={() => void applySimulationAction(() => resetSimulation(true), "Shared session released. The prior run was saved as stopped.")} /> : null}
        sidePanel={<SignalControlCard simulation={simulation} models={models} controlMode={controlMode} scenarioConfig={scenarioConfig} nativeOptions={nativeOptions}
          isLocked={isBusy || !canOperate} onControlModeChange={setControlMode} />} />
      <p className="text-xs text-muted-foreground" role="status">{statusLine}</p>
      <DashboardTrends history={chartHistory} />
      <section className="sr-only" aria-label="Live road and controller state">
        <h2>Road and junction state at {compactNumber(renderFrame?.time ?? 0, 1)}s</h2>
        <p>Shared session: {simulation?.owner_name ? `${simulation.owner_name} controls ${simulation.run_mode}${simulation.active_run_id ? ` run #${simulation.active_run_id}` : " configuration"}` : "available"}. Speed {simulation?.speed_multiplier ?? 1}×.</p>
        <p>Showing {renderFrame?.vehicles.length ?? 0} of {renderFrame?.vehicle_count ?? simulation?.state.vehicle_count ?? 0} vehicles and {renderFrame?.pedestrians.length ?? 0} of {renderFrame?.pedestrian_count ?? simulation?.state.pedestrian_count ?? 0} pedestrians in the renderer.</p>
        <h3>Affected directed lanes</h3>
        {restrictedLanes.length ? <ul>{restrictedLanes.map(({ id, detail }) =>
          <li key={`${id}-${detail}`}>{nativeOptions?.lanes.find((lane) => lane.id === id)?.label ?? id}: {detail}</li>)}</ul> : <p>No active lane restriction.</p>}
        <h3>Actual junction controllers</h3>
        <ul>{Object.entries(renderFrame?.junction_controls ?? {}).map(([id, control]) => (
          <li key={id}>{nativeOptions?.junctions.find((junction) => junction.id === id)?.label ?? id}: {control.controller} · {control.phase}</li>
        ))}</ul>
      </section>
      {showPerformance && renderPerformance?.mode === visualizationMode &&
        <p role="status" className="text-xs text-muted-foreground">{visualizationMode.toUpperCase()} renderer: {compactNumber(renderPerformance.fps, 1)} fps; p95 frame interval {compactNumber(renderPerformance.p95FrameMs, 1)} ms{visualizationMode === "3d" ? `; ${renderPerformance.drawCalls} draw calls` : " (active rendering)"}.</p>}
    </div>
  )
}

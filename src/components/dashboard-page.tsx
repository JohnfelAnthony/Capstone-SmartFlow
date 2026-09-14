import * as React from "react"
import {
  AreaChartIcon,
  BarChart3Icon,
  BrainIcon,
  CheckIcon,
  CircleDotIcon,
  GaugeIcon,
  HourglassIcon,
  ListIcon,
  PersonStandingIcon,
  SlidersHorizontalIcon,
  TrafficConeIcon,
  TruckIcon,
} from "lucide-react"
import { FaGamepad, FaPause, FaPlay, FaRotateRight, FaSquare } from "react-icons/fa6"
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ApiError } from "@/api/client"
import { listScenarios, type ApiScenario } from "@/api/scenarios"
import {
  configureSimulation,
  getSimulationState,
  listSimulationRuns,
  loadPlayback,
  pauseSimulation,
  resetSimulation,
  resumeSimulation,
  seekPlayback,
  startSimulation,
  startPlayback,
  stopSimulation,
  type SimulationRunRecord,
  type SimulationStatePayload,
} from "@/api/simulation"
import { SimulationCanvas2D } from "@/components/simulation-canvas-2d"
import { useSimulationSocket } from "@/hooks/useSimulationSocket"
import type { RenderFrame } from "@/simulation/frame-types"
import { SimulationScene3D } from "@/simulation/SimulationScene3D"
import type { VisualizationMode } from "@/simulation/visualization-mode"

type SelectOption = {
  label: string
  value: string
}

type ScenarioSettings = {
  trafficDensity: string
  pedestrianDensity: string
  emergencyMode: string
  roadConstraint: string
}

type ChartHistoryPoint = {
  bucket: number
  timeLabel: string
  avgWait: number
  avgQueue: number
  throughput: number
  vehicles: number
  pedestrians: number
}

type ChartSeries = {
  key: keyof ChartHistoryPoint
  name: string
  color: string
}

const durationOptions: SelectOption[] = [
  { label: "5 Minutes (300s)", value: "300" },
  { label: "10 Minutes (600s)", value: "600" },
  { label: "15 Minutes (900s)", value: "900" },
]

const trafficDensityOptions = ["Low", "Medium", "High", "Very High"]
const pedestrianDensityOptions = ["Low", "None", "Medium", "High"]
const emergencyModeOptions = ["Disabled", "Enabled (1 Ambulance)", "Enabled (2 Vehicles)"]
const roadConstraintOptions = ["None", "Lane Closure", "Construction", "Accident", "Flooding", "Temporary Blockage"]

const defaultSettings: ScenarioSettings = {
  trafficDensity: "Medium",
  pedestrianDensity: "Medium",
  emergencyMode: "Disabled",
  roadConstraint: "None",
}

function metricNumber(metrics: Record<string, number> | undefined, key: string) {
  const value = metrics?.[key]
  return typeof value === "number" && Number.isFinite(value) ? value : 0
}

function compactNumber(value: number, digits = 0) {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

function statusText(value: string | null | undefined) {
  return String(value || "unknown").replaceAll("_", " ").replaceAll("-", " ")
}

function buildChartPoint(simulation: SimulationStatePayload): ChartHistoryPoint {
  const time = Number(simulation.state.time ?? 0)
  const metrics = simulation.state.metrics
  return {
    bucket: Math.max(0, Math.floor(time)),
    timeLabel: `${Math.max(0, Math.floor(time))}s`,
    avgWait: metricNumber(metrics, "avg_wait"),
    avgQueue: metricNumber(metrics, "avg_queue"),
    throughput: metricNumber(metrics, "throughput"),
    vehicles: Number(simulation.state.vehicle_count ?? 0),
    pedestrians: Number(simulation.state.pedestrian_count ?? 0),
  }
}

function playbackInfo(simulation: SimulationStatePayload | null) {
  const playback = simulation?.state.playback
  const frameIndex = Number(playback?.frame_index ?? 0)
  const frameCount = Number(playback?.frame_count ?? 0)
  const progress = Number(playback?.progress_percent ?? 0)
  return {
    frameIndex: Number.isFinite(frameIndex) ? frameIndex : 0,
    frameCount: Number.isFinite(frameCount) ? frameCount : 0,
    progress: Number.isFinite(progress) ? progress : 0,
  }
}

function scenarioSettings(scenario: ApiScenario | undefined): ScenarioSettings {
  if (!scenario) return defaultSettings
  return {
    trafficDensity: scenario.traffic_density || defaultSettings.trafficDensity,
    pedestrianDensity: scenario.pedestrian_density || defaultSettings.pedestrianDensity,
    emergencyMode: scenario.emergency_mode || defaultSettings.emergencyMode,
    roadConstraint: scenario.road_constraint || defaultSettings.roadConstraint,
  }
}

function apiMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "Unable to reach the SMARTFLOW API."
}

function liveIndicatorForFrame(frame: RenderFrame) {
  if (frame.flow_state === "LIVE_RUNNING") return "LIVE"
  if (frame.flow_state === "PAUSED") return "PAUSED"
  if (frame.flow_state === "COMPLETED") return "DONE"
  if (frame.flow_state === "ERROR") return "ERROR"
  return frame.flow_state || "IDLE"
}

function signalStatesForPhase(phase: string | undefined) {
  const normalized = String(phase || "ALL_RED").toUpperCase()
  if (normalized.includes("NS") && normalized.includes("GREEN")) return { ns: "green", ew: "red" }
  if (normalized.includes("EW") && normalized.includes("GREEN")) return { ns: "red", ew: "green" }
  if (normalized.includes("NS") && normalized.includes("YELLOW")) return { ns: "yellow", ew: "red" }
  if (normalized.includes("EW") && normalized.includes("YELLOW")) return { ns: "red", ew: "yellow" }
  return { ns: "red", ew: "red" }
}

function renderFrameFromSimulation(simulation: SimulationStatePayload | null): RenderFrame | null {
  if (!simulation) return null
  const state = simulation.state
  const phase = String(state.phase ?? "ALL_RED")
  const signalStates = signalStatesForPhase(phase)
  const intersectionId =
    typeof state.scenario?.intersection_id === "string"
      ? state.scenario.intersection_id
      : "tagum_1"

  return {
    time: Number(state.time ?? 0),
    render_ts: Date.now() / 1000,
    step_length: Number(state.step_length ?? 0.1),
    status: state.status ?? simulation.status,
    flow_state: String(state.flow?.state ?? "IDLE"),
    intersection_id: intersectionId,
    phase,
    ns_state: signalStates.ns,
    ew_state: signalStates.ew,
    render_mode: simulation.control_mode === "playback" ? "playback" : simulation.status === "running" ? "live" : "idle",
    playback: {
      active: Boolean(state.playback),
      frame_index: Number(state.playback?.frame_index ?? 0),
      frame_count: Number(state.playback?.frame_count ?? 0),
    },
    vehicles: state.vehicles ?? [],
    pedestrians: state.pedestrians ?? [],
    visual: {
      constraint_marker: {
        active: Boolean(state.visual?.constraint_marker?.active),
        x: Number(state.visual?.constraint_marker?.x ?? 0),
        y: Number(state.visual?.constraint_marker?.y ?? 0),
      },
    },
    traffic_lights: state.traffic_lights ?? {},
  }
}

function mergeRenderFrame(simulation: SimulationStatePayload | null, frame: RenderFrame) {
  if (!simulation) return simulation
  return {
    ...simulation,
    status: frame.status,
    state: {
      ...simulation.state,
      time: frame.time,
      step_length: frame.step_length,
      status: frame.status,
      phase: frame.phase,
      traffic_lights: frame.traffic_lights,
      vehicles: frame.vehicles,
      pedestrians: frame.pedestrians,
      visual: frame.visual,
      scenario: {
        ...(simulation.state.scenario ?? {}),
        intersection_id: frame.intersection_id,
      },
      flow: {
        ...(simulation.state.flow ?? {}),
        state: frame.flow_state,
        live_indicator_label: liveIndicatorForFrame(frame),
      },
    },
  }
}

function CardTitle({
  children,
  icon: Icon,
}: {
  children: React.ReactNode
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
}) {
  return (
    <h2 className="sf-card-title">
      <Icon />
      <span>{children}</span>
    </h2>
  )
}

function SelectField({
  label,
  options,
  value,
  disabled,
  onChange,
}: {
  label: string
  options: SelectOption[]
  value: string
  disabled?: boolean
  onChange: (value: string) => void
}) {
  return (
    <label className="sf-setting-group">
      <span>{label}</span>
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function SimulationView({
  scenarios,
  selectedScenarioId,
  durationSeconds,
  simulation,
  renderFrame,
  visualizationMode,
  isBusy,
  onScenarioChange,
  onDurationChange,
  onConfigure,
  onThreeUnavailable,
}: {
  scenarios: ApiScenario[]
  selectedScenarioId: string
  durationSeconds: string
  simulation: SimulationStatePayload | null
  renderFrame: RenderFrame | null
  visualizationMode: VisualizationMode
  isBusy: boolean
  onScenarioChange: (scenarioId: string) => void
  onDurationChange: (duration: string) => void
  onConfigure: () => void
  onThreeUnavailable: (message: string) => void
}) {
  const state = simulation?.state
  const dashboard = state?.dashboard
  const selectedScenarioName =
    typeof dashboard?.current_scenario_name === "string"
      ? dashboard.current_scenario_name
      : scenarios.find((scenario) => String(scenario.id) === selectedScenarioId)?.name ?? "Select a scenario"
  const phase = String(state?.phase ?? "ALL_RED").replaceAll("_", " ")
  const phaseRemaining = Number(state?.phase_remaining ?? 0)
  const statusLabel = simulation?.state.flow?.live_indicator_label ?? "IDLE"
  const intersectionId =
    renderFrame?.intersection_id ??
    (typeof state?.scenario?.intersection_id === "string" ? state.scenario.intersection_id : null)
  const showSetupCard = !["running", "paused"].includes(simulation?.status ?? "") && simulation?.control_mode !== "playback"
  const showLiveCanvas = !showSetupCard

  return (
    <section className="sf-card sf-simulation-card">
      <div className="sf-sim-viewport">
        {showLiveCanvas && visualizationMode === "2d" ? (
          <SimulationCanvas2D frame={renderFrame} intersectionId={intersectionId} />
        ) : showLiveCanvas ? (
          <SimulationScene3D onUnavailable={onThreeUnavailable} />
        ) : (
          <div className="sf-sim-grid" aria-hidden="true" />
        )}
        {showSetupCard ? (
          <div className="sf-setup-card">
            <h3>Simulation Setup</h3>
            <SelectField
              label="Select Scenario"
              options={scenarios.map((scenario) => ({ label: scenario.name, value: String(scenario.id) }))}
              value={selectedScenarioId}
              disabled={isBusy || scenarios.length === 0}
              onChange={onScenarioChange}
            />
            <SelectField
              label="Run Mode"
              options={[{ label: "Live Scenario", value: "live" }]}
              value="live"
              disabled
              onChange={() => undefined}
            />
            <SelectField
              label="Duration Limit"
              options={durationOptions}
              value={durationSeconds}
              disabled={isBusy}
              onChange={onDurationChange}
            />
            <button className="sf-primary-btn" type="button" disabled={isBusy || !selectedScenarioId} onClick={onConfigure}>
              {isBusy ? "Applying..." : "Apply Configuration"}
            </button>
          </div>
        ) : null}

        <div className="sf-sim-overlay top-left">
          <span>{statusLabel}</span>
          <strong>{selectedScenarioName}</strong>
        </div>
        <div className="sf-sim-overlay bottom-left">
          <span>Signal Phase</span>
          <strong className="phase-red">
            <CircleDotIcon />
            {phase}
          </strong>
        </div>
        <div className="sf-sim-overlay bottom-right">
          <span>Phase Timer</span>
          <strong className="timer">{compactNumber(Math.max(phaseRemaining, 0), 1)}s</strong>
        </div>
      </div>
    </section>
  )
}

function ControlPanel({
  settings,
  simulation,
  recordedRuns,
  selectedRecordedRunId,
  isBusy,
  canStart,
  onSettingChange,
  onApplyScenario,
  onRecordedRunChange,
  onRefreshRecordings,
  onLoadRecording,
  onStartPlayback,
  onSeekPlayback,
  onStart,
  onPause,
  onStop,
  onReset,
}: {
  settings: ScenarioSettings
  simulation: SimulationStatePayload | null
  recordedRuns: SimulationRunRecord[]
  selectedRecordedRunId: string
  isBusy: boolean
  canStart: boolean
  onSettingChange: (key: keyof ScenarioSettings, value: string) => void
  onApplyScenario: () => void
  onRecordedRunChange: (runId: string) => void
  onRefreshRecordings: () => void
  onLoadRecording: () => void
  onStartPlayback: () => void
  onSeekPlayback: (frameIndex: number) => void
  onStart: () => void
  onPause: () => void
  onStop: () => void
  onReset: () => void
}) {
  const status = simulation?.status ?? "stopped"
  const isRunning = status === "running"
  const isPaused = status === "paused"
  const playback = playbackInfo(simulation)
  const selectedRecordedRun = recordedRuns.find((run) => String(run.id) === selectedRecordedRunId)
  const canLoadRecording = Boolean(selectedRecordedRunId && selectedRecordedRun?.status === "completed")
  const isPlayback = simulation?.control_mode === "playback"

  return (
    <aside className="sf-right-panel">
      <section className="sf-card sf-control-card">
        <h2 className="sf-card-title">
          <FaGamepad />
          <span>Simulation Controls</span>
        </h2>
        <div className="sf-control-buttons">
          <button
            className="start"
            type="button"
            disabled={isBusy || (!isPlayback && !canStart) || isRunning}
            onClick={isPlayback ? onStartPlayback : isPaused ? onPause : onStart}
          >
            <FaPlay />
            {isPlayback ? "Play Recording" : isPaused ? "Resume Simulation" : "Start Simulation"}
          </button>
          <button className="pause" type="button" disabled={isBusy || !isRunning} onClick={onPause}>
            <FaPause />
            Pause
          </button>
          <button className="stop" type="button" disabled={isBusy || (!isRunning && !isPaused)} onClick={onStop}>
            <FaSquare />
            Stop Simulation
          </button>
          <button className="reset" type="button" disabled={isBusy} onClick={onReset}>
            <FaRotateRight />
            Reset Simulation
          </button>
        </div>
      </section>

      <section className="sf-card sf-settings-card">
        <CardTitle icon={SlidersHorizontalIcon}>Scenario Settings</CardTitle>
        <SelectField
          label="Traffic Density"
          options={trafficDensityOptions.map((option) => ({ label: option, value: option }))}
          value={settings.trafficDensity}
          disabled={isBusy || isRunning || isPaused}
          onChange={(value) => onSettingChange("trafficDensity", value)}
        />
        <SelectField
          label="Pedestrian Density"
          options={pedestrianDensityOptions.map((option) => ({ label: option, value: option }))}
          value={settings.pedestrianDensity}
          disabled={isBusy || isRunning || isPaused}
          onChange={(value) => onSettingChange("pedestrianDensity", value)}
        />
        <SelectField
          label="Emergency Vehicle"
          options={emergencyModeOptions.map((option) => ({ label: option, value: option }))}
          value={settings.emergencyMode}
          disabled={isBusy || isRunning || isPaused}
          onChange={(value) => onSettingChange("emergencyMode", value)}
        />
        <SelectField
          label="Road Constraint"
          options={roadConstraintOptions.map((option) => ({ label: option, value: option }))}
          value={settings.roadConstraint}
          disabled={isBusy || isRunning || isPaused}
          onChange={(value) => onSettingChange("roadConstraint", value)}
        />
        <button className="sf-apply-btn" type="button" disabled={isBusy || isRunning || isPaused || !canStart} onClick={onApplyScenario}>
          <CheckIcon />
          Apply Scenario
        </button>
      </section>

      <section className="sf-card sf-playback-card">
        <CardTitle icon={AreaChartIcon}>Recorded Playback</CardTitle>
        <label className="sf-setting-group">
          <span>Recording</span>
          <select value={selectedRecordedRunId} disabled={isBusy || recordedRuns.length === 0} onChange={(event) => onRecordedRunChange(event.target.value)}>
            <option value="">Select recording</option>
            {recordedRuns.map((run) => (
              <option key={run.id} value={run.id} disabled={run.status !== "completed"}>
                #{run.id} {run.scenario_name ?? "Recorded run"} ({statusText(run.status)})
              </option>
            ))}
          </select>
        </label>
        <div className="sf-playback-buttons">
          <button type="button" disabled={isBusy} onClick={onRefreshRecordings}>
            Refresh
          </button>
          <button type="button" disabled={isBusy || !canLoadRecording} onClick={onLoadRecording}>
            Load
          </button>
          <button type="button" disabled={isBusy || !isPlayback || isRunning} onClick={onStartPlayback}>
            <FaPlay />
            Play
          </button>
        </div>
        <div className="sf-playback-scrubber">
          <div>
            <span>Frame</span>
            <strong>
              {playback.frameCount > 0 ? `${playback.frameIndex + 1}/${playback.frameCount}` : "0/0"}
            </strong>
          </div>
          <input
            type="range"
            min="0"
            max={Math.max(playback.frameCount - 1, 0)}
            value={Math.min(playback.frameIndex, Math.max(playback.frameCount - 1, 0))}
            disabled={isBusy || !isPlayback || playback.frameCount <= 1}
            onChange={(event) => onSeekPlayback(Number(event.target.value))}
          />
          <span>{compactNumber(playback.progress)}%</span>
        </div>
      </section>
    </aside>
  )
}

function KpiRow({ simulation }: { simulation: SimulationStatePayload | null }) {
  const metrics = simulation?.state.metrics
  const dashboard = simulation?.state.dashboard
  const emergencyCount =
    typeof dashboard?.emergency_active_count === "number" ? dashboard.emergency_active_count : 0
  const kpis = [
    {
      label: "Avg. Waiting Time",
      value: compactNumber(metricNumber(metrics, "avg_wait"), 1),
      unit: "s",
      color: "#00e676",
      icon: HourglassIcon,
    },
    {
      label: "Avg. Queue Length",
      value: compactNumber(metricNumber(metrics, "avg_queue"), 1),
      unit: "veh",
      color: "#42a5f5",
      icon: BarChart3Icon,
    },
    {
      label: "Throughput",
      value: compactNumber(metricNumber(metrics, "throughput")),
      unit: "veh",
      color: "#ab47bc",
      icon: GaugeIcon,
    },
    {
      label: "Pedestrians Crossed",
      value: compactNumber(metricNumber(metrics, "total_pedestrians_completed")),
      unit: "",
      color: "#ffa726",
      icon: PersonStandingIcon,
    },
    {
      label: "Emergency Vehicles",
      value: compactNumber(emergencyCount),
      unit: "active",
      color: "#ef5350",
      icon: TruckIcon,
    },
  ]

  return (
    <section className="sf-kpi-row">
      {kpis.map((kpi) => {
        const Icon = kpi.icon

        return (
          <article className="sf-kpi-card" key={kpi.label}>
            <div className="sf-kpi-icon" style={{ "--kpi-color": kpi.color } as React.CSSProperties}>
              <Icon />
            </div>
            <div>
              <span className="sf-kpi-label">{kpi.label}</span>
              <strong className="sf-kpi-value">
                {kpi.value}
                {kpi.unit && <span>{kpi.unit}</span>}
              </strong>
            </div>
          </article>
        )
      })}
    </section>
  )
}

function EmptyChart({ title }: { title: string }) {
  return (
    <div className="sf-empty-chart">
      <div className="sf-chart-grid" />
      <div className="sf-empty-chart-message">
        <AreaChartIcon />
        <span>{title}</span>
        <small>No live history yet.</small>
      </div>
    </div>
  )
}

function MetricChart({
  title,
  history,
  series,
  mode = "area",
}: {
  title: string
  history: ChartHistoryPoint[]
  series: ChartSeries[]
  mode?: "area" | "line"
}) {
  if (history.length < 2) return <EmptyChart title={title} />

  const commonProps = {
    data: history,
    margin: { top: 12, right: 8, bottom: 0, left: -22 },
  }

  return (
    <div className="sf-live-chart">
      <ResponsiveContainer width="100%" height="100%">
        {mode === "area" ? (
          <AreaChart {...commonProps}>
            <CartesianGrid stroke="rgba(148, 163, 184, 0.14)" strokeDasharray="3 3" />
            <XAxis dataKey="timeLabel" tick={{ fill: "#94a3b8", fontSize: 10 }} minTickGap={18} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} width={34} />
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(148, 163, 184, 0.25)", borderRadius: 6 }} />
            {series.map((item) => (
              <Area
                key={item.key}
                type="monotone"
                dataKey={item.key}
                name={item.name}
                stroke={item.color}
                fill={item.color}
                fillOpacity={0.18}
                strokeWidth={2}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        ) : (
          <LineChart {...commonProps}>
            <CartesianGrid stroke="rgba(148, 163, 184, 0.14)" strokeDasharray="3 3" />
            <XAxis dataKey="timeLabel" tick={{ fill: "#94a3b8", fontSize: 10 }} minTickGap={18} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} width={34} />
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(148, 163, 184, 0.25)", borderRadius: 6 }} />
            {series.map((item) => (
              <Line
                key={item.key}
                type="monotone"
                dataKey={item.key}
                name={item.name}
                stroke={item.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

function TimePills() {
  return (
    <div className="sf-time-pills">
      <button className="active" type="button">5m</button>
      <button type="button">15m</button>
      <button type="button">1h</button>
    </div>
  )
}

function AnalyticsSection({
  simulation,
  chartHistory,
}: {
  simulation: SimulationStatePayload | null
  chartHistory: ChartHistoryPoint[]
}) {
  const events = (simulation?.state.events ?? []).slice(-4).reverse()
  const status = simulation?.state.flow?.status_label ?? "Standby"

  return (
    <section className="sf-analytics-row">
      <article className="sf-card sf-analytics-card">
        <div className="sf-analytics-header">
          <CardTitle icon={AreaChartIcon}>Traffic Flow</CardTitle>
          <TimePills />
        </div>
        <MetricChart
          title="Traffic Flow"
          history={chartHistory}
          series={[
            { key: "throughput", name: "Throughput", color: "#00e676" },
            { key: "vehicles", name: "Vehicles", color: "#42a5f5" },
          ]}
        />
      </article>

      <article className="sf-card sf-analytics-card">
        <div className="sf-analytics-header">
          <CardTitle icon={BarChart3Icon}>Avg. Waiting Time</CardTitle>
          <TimePills />
        </div>
        <MetricChart
          title="Avg. Waiting Time"
          history={chartHistory}
          mode="line"
          series={[
            { key: "avgWait", name: "Wait Time", color: "#ffa726" },
            { key: "avgQueue", name: "Queue Length", color: "#ef5350" },
          ]}
        />
      </article>

      <article className="sf-card sf-analytics-card">
        <div className="sf-analytics-header">
          <CardTitle icon={BrainIcon}>RL Agent Status</CardTitle>
          <span className="sf-agent-badge">{status}</span>
        </div>
        <div className="sf-rl-stats">
          <div className="sf-rl-progress">
            <span>Learning Progress</span>
            <div><span style={{ width: "0%" }} /></div>
            <strong>0%</strong>
          </div>
          <div className="sf-rl-progress">
            <span>Epsilon (Exploration)</span>
            <div><span style={{ width: "0%" }} /></div>
            <strong>0.00</strong>
          </div>
          <div className="sf-rl-metric-grid">
            <div><span>Total Episodes</span><strong>0</strong></div>
            <div><span>Total Reward</span><strong>0.0</strong></div>
            <div><span>Algorithm</span><strong>{simulation?.control_mode ?? "Standby"}</strong></div>
            <div><span>Runtime</span><strong>{simulation?.status ?? "idle"}</strong></div>
          </div>
        </div>
      </article>

      <article className="sf-card sf-analytics-card">
        <div className="sf-analytics-header">
          <CardTitle icon={ListIcon}>Recent Events</CardTitle>
          <button className="sf-clear-btn" type="button">Clear</button>
        </div>
        <div className="sf-events-feed">
          {events.length > 0 ? (
            events.map((event, index) => (
              <div className="sf-event-item" key={`${event.id ?? index}-${event.message ?? "event"}`}>
                <span>{typeof event.time === "number" ? `${event.time.toFixed(1)}s` : "--:--"}</span>
                <TrafficConeIcon />
                <p>{String(event.message ?? "Simulation event")}</p>
              </div>
            ))
          ) : (
            <div className="sf-event-item">
              <span>--:--</span>
              <TrafficConeIcon />
              <p>No live events yet</p>
            </div>
          )}
        </div>
      </article>
    </section>
  )
}

export function DashboardPage({
  visualizationMode,
  onVisualizationModeChange,
}: {
  visualizationMode: VisualizationMode
  onVisualizationModeChange: (mode: VisualizationMode) => void
}) {
  const [scenarios, setScenarios] = React.useState<ApiScenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = React.useState("")
  const [durationSeconds, setDurationSeconds] = React.useState("300")
  const [settings, setSettings] = React.useState<ScenarioSettings>(defaultSettings)
  const [simulation, setSimulation] = React.useState<SimulationStatePayload | null>(null)
  const [renderFrame, setRenderFrame] = React.useState<RenderFrame | null>(null)
  const [recordedRuns, setRecordedRuns] = React.useState<SimulationRunRecord[]>([])
  const [selectedRecordedRunId, setSelectedRecordedRunId] = React.useState("")
  const [chartHistory, setChartHistory] = React.useState<ChartHistoryPoint[]>([])
  const [notice, setNotice] = React.useState("Loading simulation workspace...")
  const [isBusy, setIsBusy] = React.useState(false)
  const lastStateRefreshAt = React.useRef(0)
  const stateRefreshInFlight = React.useRef(false)
  const lastChartBucket = React.useRef<number | null>(null)

  const canConfigure = Boolean(selectedScenarioId)
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

  const applySimulationAction = React.useCallback(
    async (action: () => Promise<{ message: string; simulation: SimulationStatePayload }>, successMessage?: string) => {
      setIsBusy(true)
      try {
        const response = await action()
        setSimulation(response.simulation)
        setRenderFrame(renderFrameFromSimulation(response.simulation))
        setNotice(successMessage ?? response.message)
      } catch (error) {
        setNotice(apiMessage(error))
      } finally {
        setIsBusy(false)
      }
    },
    []
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

  const configureSelectedScenario = React.useCallback(() => {
    if (!canConfigure) {
      setNotice("Select a scenario before applying configuration.")
      return
    }
    return applySimulationAction(() =>
      configureSimulation({
        scenario_id: Number(selectedScenarioId),
        duration_seconds: Number(durationSeconds),
        traffic_density: settings.trafficDensity,
        pedestrian_density: settings.pedestrianDensity,
        emergency_mode: settings.emergencyMode,
        road_constraint: settings.roadConstraint,
      })
    )
  }, [applySimulationAction, canConfigure, durationSeconds, selectedScenarioId, settings])

  React.useEffect(() => {
    let isMounted = true

    async function loadDashboard() {
      setIsBusy(true)
      try {
        const [scenarioResponse, simulationResponse, runsResponse] = await Promise.all([
          listScenarios(),
          getSimulationState(),
          listSimulationRuns({ runMode: "pre-record", limit: 30 }),
        ])
        if (!isMounted) return

        const nextScenarios = scenarioResponse.scenarios
        setScenarios(nextScenarios)
        setSimulation(simulationResponse)
        setRenderFrame(renderFrameFromSimulation(simulationResponse))
        setRecordedRuns(runsResponse.runs)
        const firstCompletedRun = runsResponse.runs.find((run) => run.status === "completed")
        setSelectedRecordedRunId(firstCompletedRun ? String(firstCompletedRun.id) : "")
        const activeScenarioId =
          simulationResponse.selected_scenario_id !== null
            ? String(simulationResponse.selected_scenario_id)
            : nextScenarios[0]
              ? String(nextScenarios[0].id)
              : ""
        setSelectedScenarioId(activeScenarioId)
        setSettings(scenarioSettings(nextScenarios.find((scenario) => String(scenario.id) === activeScenarioId)))
        setNotice("Simulation controls are connected to FastAPI.")
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
  }, [])

  React.useEffect(() => {
    const hasGeneratingRun = recordedRuns.some((run) => run.status === "running")
    if (!hasGeneratingRun) return
    const intervalId = window.setInterval(() => {
      loadRecordedRuns().catch((error) => setNotice(apiMessage(error)))
    }, 3000)
    return () => window.clearInterval(intervalId)
  }, [loadRecordedRuns, recordedRuns])

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
        setSimulation(nextSimulation)
        setRenderFrame(renderFrameFromSimulation(nextSimulation))
      })
      .catch((error) => setNotice(apiMessage(error)))
      .finally(() => {
        stateRefreshInFlight.current = false
      })
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [latestFrame])

  React.useEffect(() => {
    if (!simulation) return
    const nextPoint = buildChartPoint(simulation)
    if (lastChartBucket.current === nextPoint.bucket) return
    lastChartBucket.current = nextPoint.bucket
    setChartHistory((current) => [...current, nextPoint].slice(-240))
  }, [simulation])

  function handleScenarioChange(scenarioId: string) {
    setSelectedScenarioId(scenarioId)
    setSettings(scenarioSettings(scenarios.find((scenario) => String(scenario.id) === scenarioId)))
  }

  function handleSettingChange(key: keyof ScenarioSettings, value: string) {
    setSettings((current) => ({ ...current, [key]: value }))
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
    applySimulationAction(() =>
      startSimulation({
        scenario_id: Number(selectedScenarioId),
        duration_seconds: Number(durationSeconds),
        control_mode: "fixed-time",
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
      setSimulation(response.simulation)
      setRenderFrame(renderFrameFromSimulation(response.simulation))
      setNotice(response.message)
    } catch (error) {
      setNotice(apiMessage(error))
    }
  }

  return (
    <div className="sf-dashboard-page">
      <div className="sf-top-row">
        <SimulationView
          scenarios={scenarios}
          selectedScenarioId={selectedScenarioId}
          durationSeconds={durationSeconds}
          simulation={simulation}
          renderFrame={renderFrame}
          visualizationMode={visualizationMode}
          isBusy={isBusy}
          onScenarioChange={handleScenarioChange}
          onDurationChange={setDurationSeconds}
          onConfigure={configureSelectedScenario}
          onThreeUnavailable={handleThreeUnavailable}
        />
        <ControlPanel
          settings={settings}
          simulation={simulation}
          recordedRuns={recordedRuns}
          selectedRecordedRunId={selectedRecordedRunId}
          isBusy={isBusy}
          canStart={canConfigure}
          onSettingChange={handleSettingChange}
          onApplyScenario={configureSelectedScenario}
          onRecordedRunChange={setSelectedRecordedRunId}
          onRefreshRecordings={() => void loadRecordedRuns().catch((error) => setNotice(apiMessage(error)))}
          onLoadRecording={handleLoadRecording}
          onStartPlayback={handleStartPlayback}
          onSeekPlayback={(frameIndex) => void handleSeekPlayback(frameIndex)}
          onStart={handleStart}
          onPause={handlePauseOrResume}
          onStop={() => applySimulationAction(stopSimulation)}
          onReset={() => applySimulationAction(resetSimulation)}
        />
      </div>
      <KpiRow simulation={simulation} />
      <AnalyticsSection simulation={simulation} chartHistory={chartHistory} />
      <footer className="sf-dashboard-footer">
        <span>{streamNotice ?? notice}</span>
        <strong>{streamEnabled ? `Stream ${streamStatus}` : "FastAPI bridge"}</strong>
      </footer>
    </div>
  )
}

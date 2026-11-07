import * as React from "react"
import {
  ArrowDownIcon,
  ArrowLeftRightIcon,
  ArrowUpIcon,
  ChevronDownIcon,
  GitCompareArrowsIcon,
  MinusIcon,
  PauseIcon,
  PlayIcon,
  RefreshCcwIcon,
  TriangleAlertIcon,
} from "lucide-react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { metricDefinition, metricDescription, metricValue, formatMetric } from "@/lib/metrics"
import { MetricDefinitions } from "@/components/metric-definitions"
import { ApiError } from "@/api/client"
import {
  getComparePair,
  getComparePairFrames,
  listCompareRuns,
  listCompatibleCompareRuns,
  type ComparePairFramesResponse,
  type ComparePairResponse,
  type CompareRunBundle,
  type CompareRunOption,
} from "@/api/compare"
import { getVisualNetwork } from "@/api/visual-network"
import { CompareMap } from "@/components/compare-map"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { advancePlayback, frameAtTime, frameWindow, kpiChange, studyJunctionId, studyQueue } from "@/lib/compare-view"
import { controlLabel, isRlControl } from "@/lib/control-labels"
import { EMPTY_VALUE } from "@/lib/display-format"
import { normalizeSceneGeometry, type SceneGeometry } from "@/simulation/scene-geometry"
import type { RenderFrame } from "@/simulation/frame-types"
import "@/styles/compare-runs.css"

const noSelection = "none"
// Each frame is about 30 KB per run, so the page asks for 10 s at a time (the server allows up to 60 s).
const WINDOW_SECONDS = 10
const PREFETCH_SECONDS = 5
const MIN_STEP_MS = 66
const CHART_POINTS = 400
const kpiRows = ["avg_wait", "avg_queue", "max_queue", "throughput", "avg_travel_time", "avg_ped_delay",
  "requested_vehicles", "total_vehicles_spawned", "pending_demand", "dropped_vehicles", "unfinished_vehicles",
  "boundary_wait_seconds", "avg_admitted_boundary_wait",
  "measurement_start", "measurement_seconds"].map((key) => {
    const definition = metricDefinition(key)!
    const neutral = ["requested_vehicles", "total_vehicles_spawned", "measurement_start", "measurement_seconds"].includes(key)
    return { key, label: definition.label, unit: definition.unit,
      lowerIsBetter: neutral ? null : !["throughput"].includes(key) }
  })
const chartTabs = {
  wait: { label: "Wait", title: "Mean stopped wait (s)", left: "leftWait", right: "rightWait" },
  queue: { label: "Queue", title: "Mean incoming-lane queue (vehicles)", left: "leftQueue", right: "rightQueue" },
  throughput: { label: "Throughput", title: "Completed network trips", left: "leftThroughput", right: "rightThroughput" },
} as const
type ChartTab = keyof typeof chartTabs
type FrameWindows = { ids: string | null; byStart: Record<number, ComparePairFramesResponse> }

function compareErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return fallback
}

function formatNumber(value: number | null | undefined, digits = 1) {
  return formatMetric(value, digits)
}

function kpiDigits(key: string) {
  return key.includes("vehicles") || key === "throughput" ? 0 : 2
}

/** The controller leads, so two runs of one scenario are told apart at a glance. */
function runTitle(option: CompareRunOption) {
  const { run } = option
  const modelId = option.provenance.model_id ?? run.rl_model_id
  return `${controlLabel(run.control_mode)}${isRlControl(run.control_mode) && modelId ? ` #${modelId}` : ""}`
}

function runOptionLabel(option: CompareRunOption) {
  const { run } = option
  return `${runTitle(option)} · run #${run.id} · ${run.scenario_name ?? "Unknown scenario"} · seed ${run.seed ?? "none"}`
}

function networkIdOf(pair: ComparePairResponse) {
  const rawMetrics = pair.left.metrics.raw_metrics as { experiment?: { network_id?: string } } | undefined
  return rawMetrics?.experiment?.network_id ?? pair.left.option.timeline.intersection_id ?? null
}

function matchSummary(pair: ComparePairResponse) {
  const { run, timeline } = pair.left.option
  const same = `Same scenario (${run.scenario_name ?? "unknown"}), seed ${run.seed ?? "none"}, ${formatNumber(timeline.actual_duration_seconds, 0)} s`
  const differs = pair.comparison_type === "signal" ? "signal controller differs"
    : pair.comparison_type === "routing" ? "routing differs" : "repeat of the same setup"
  return `${same}; ${differs}`
}

/** The frame pair for `time`, taken only from the window that holds `time`, never from a neighbouring window. */
function framesAt(byStart: Record<number, ComparePairFramesResponse>, time: number): { left: RenderFrame; right: RenderFrame } | null {
  const { start } = frameWindow(time, WINDOW_SECONDS)
  const loaded = byStart[start]
  if (!loaded) return null
  const index = frameAtTime(loaded.times, time)
  if (index >= 0) return { left: loaded.left[index], right: loaded.right[index] }
  const before = byStart[start - WINDOW_SECONDS]
  const last = before ? before.times.length - 1 : -1
  return before && last >= 0 ? { left: before.left[last], right: before.right[last] } : null
}

function RunSelect({
  value,
  onChange,
  options,
  placeholder,
  disabled,
  label,
}: {
  value: string
  onChange: (value: string) => void
  options: CompareRunOption[]
  placeholder: string
  disabled?: boolean
  label: string
}) {
  return (
    <Select items={[{ value: noSelection, label: placeholder }, ...options.map((option) => ({ value: String(option.run.id), label: runOptionLabel(option) }))]} value={value} onValueChange={(nextValue) => onChange(nextValue ?? noSelection)} disabled={disabled}>
      <SelectTrigger className="w-full" aria-label={label}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem value={noSelection}>{placeholder}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.run.id} value={String(option.run.id)}>
              {runOptionLabel(option)}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

function RunMetaCard({ bundle, role }: { bundle: CompareRunBundle; role: "Baseline" | "Compared" }) {
  const { run, timeline } = bundle.option
  const provenance = bundle.option.provenance
  return (
    <Card className="compare-run-card">
      <CardHeader>
        <CardTitle>{role}: {runTitle(bundle.option)}</CardTitle>
        <CardDescription>Run #{run.id} · {run.scenario_name ?? "Unknown scenario"}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="compare-meta-grid">
          <div><span>Controller</span><strong>{controlLabel(run.control_mode)}</strong></div>
          <div><span>Model</span><strong>{provenance.model_id ? `#${provenance.model_id}` : "Fixed-time / none"}</strong></div>
          <div><span>Model SHA-256</span><strong>{provenance.model_sha256 ?? EMPTY_VALUE}</strong></div>
          <div><span>Demand</span><strong>{provenance.demand_source ?? "Unknown"}: {provenance.demand_description ?? EMPTY_VALUE}</strong></div>
          <div><span>Demand SHA-256</span><strong>{provenance.demand_sha256 ?? EMPTY_VALUE}</strong></div>
          <div><span>Network SHA-256</span><strong>{provenance.network_sha256 ?? EMPTY_VALUE}</strong></div>
          <div><span>Seed</span><strong>{run.seed ?? "None"}</strong></div>
          <div><span>Duration</span><strong>{formatNumber(timeline.actual_duration_seconds, 1)}s</strong></div>
          <div><span>Step</span><strong>{formatNumber(timeline.step_length_seconds, 2)}s</strong></div>
        </div>
      </CardContent>
    </Card>
  )
}

function KpiCards({ pair }: { pair: ComparePairResponse }) {
  return (
    <Card className="compare-kpi-card">
      <CardHeader>
        <CardTitle>What changed</CardTitle>
        <CardDescription>Baseline value → compared value, per metric. The arrow shows the change from the baseline and whether it helps for that metric; there is no overall winner. Unavailable values are not zero. Average waits exclude pending arrivals, so read completion, pedestrians and unfinished demand together.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="compare-kpi-grid">
          {kpiRows.map((row) => {
            const left = metricValue(pair.left.metrics, row.key)
            const right = metricValue(pair.right.metrics, row.key)
            const change = kpiChange(left, right, row.lowerIsBetter)
            const digits = kpiDigits(row.key)
            const { delta } = change
            // A change that rounds to zero on screen is shown as no change, not as "-0 Better".
            const roundsToZero = delta !== null && Number(Math.abs(delta).toFixed(digits)) === 0
            const tone = roundsToZero ? "neutral" : change.tone
            const Icon = delta === null || roundsToZero ? MinusIcon : delta > 0 ? ArrowUpIcon : ArrowDownIcon
            return (
              <div className="compare-kpi-card-item" data-tone={tone} key={row.key} title={metricDescription(row.key)}>
                <span className="compare-kpi-label">{row.label}</span>
                <span className="compare-kpi-values">
                  {left === null ? EMPTY_VALUE : formatNumber(left, digits)} → {right === null ? EMPTY_VALUE : formatNumber(right, digits)} <small>{row.unit}</small>
                </span>
                <span className="compare-kpi-delta">
                  <Icon aria-hidden="true" />
                  {delta === null ? EMPTY_VALUE : roundsToZero ? "0" : `${delta > 0 ? "+" : ""}${formatNumber(delta, digits)}`}
                  {tone !== "neutral" ? <em>{tone === "better" ? "Better" : "Worse"}</em> : null}
                </span>
              </div>
            )
          })}
        </div>
        <MetricDefinitions keys={kpiRows.map((row) => row.key)} />
      </CardContent>
    </Card>
  )
}

function HistoryChart({ pair, time, duration, onSeek }: { pair: ComparePairResponse; time: number; duration: number; onSeek: (time: number) => void }) {
  const [tab, setTab] = React.useState<ChartTab>("wait")
  const data = React.useMemo(() => {
    const stride = Math.max(1, Math.ceil(pair.left.frames.length / CHART_POINTS))
    return pair.left.frames.flatMap((leftFrame, index) => {
      if (index % stride !== 0 && index !== pair.left.frames.length - 1) return []
      const rightFrame = pair.right.frames[index]
      return [{
        time: leftFrame.time,
        leftWait: leftFrame.interpreted_metrics?.avg_wait ?? null,
        rightWait: rightFrame?.interpreted_metrics?.avg_wait ?? null,
        leftQueue: leftFrame.interpreted_metrics?.avg_queue ?? null,
        rightQueue: rightFrame?.interpreted_metrics?.avg_queue ?? null,
        leftThroughput: leftFrame.interpreted_metrics?.throughput ?? null,
        rightThroughput: rightFrame?.interpreted_metrics?.throughput ?? null,
      }]
    })
  }, [pair])
  const chart = chartTabs[tab]
  return (
    <Card className="compare-chart-card">
      <CardHeader>
        <CardTitle>{chart.title}</CardTitle>
        <CardDescription>Both runs over simulation time. The vertical line is the playback position; click the chart to jump there.</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs value={tab} onValueChange={(value) => setTab(value as ChartTab)}>
          <TabsList>
            {(Object.keys(chartTabs) as ChartTab[]).map((key) => <TabsTrigger key={key} value={key}>{chartTabs[key].label}</TabsTrigger>)}
          </TabsList>
        </Tabs>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} onClick={(state) => { const clicked = Number(state?.activeLabel); if (Number.isFinite(clicked)) onSeek(clicked) }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="time" type="number" domain={[0, duration]} tickLine={false} axisLine={false} minTickGap={28} unit=" s" />
            <YAxis tickLine={false} axisLine={false} width={42} />
            <Tooltip />
            <Line type="monotone" dataKey={chart.left} stroke="var(--chart-2)" dot={false} strokeWidth={2} name="Baseline" isAnimationActive={false} />
            <Line type="monotone" dataKey={chart.right} stroke="var(--chart-1)" dot={false} strokeWidth={2} name="Compared" isAnimationActive={false} />
            <ReferenceLine x={time} stroke="var(--foreground)" strokeDasharray="4 3" />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export function CompareRunsPage() {
  const [runs, setRuns] = React.useState<CompareRunOption[]>([])
  const [compatibleRuns, setCompatibleRuns] = React.useState<CompareRunOption[]>([])
  const [leftRunId, setLeftRunId] = React.useState(noSelection)
  const [rightRunId, setRightRunId] = React.useState(noSelection)
  const [loadedPair, setLoadedPair] = React.useState<{ ids: string; pair: ComparePairResponse | null; error: string | null } | null>(null)
  const [loadedGeometry, setLoadedGeometry] = React.useState<{ networkId: string; geometry: SceneGeometry } | null>(null)
  const [frameWindows, setFrameWindows] = React.useState<FrameWindows>({ ids: null, byStart: {} })
  const [framesError, setFramesError] = React.useState<string | null>(null)
  const [time, setTime] = React.useState(0)
  const [isPlaying, setIsPlaying] = React.useState(false)
  const [speed, setSpeed] = React.useState<1 | 2 | 4>(1)
  const [isLoading, setIsLoading] = React.useState(false)
  const [notice, setNotice] = React.useState<string | null>(null)
  const timeRef = React.useRef(0)
  const windowsRef = React.useRef<Record<number, ComparePairFramesResponse>>({})
  const requestedRef = React.useRef(new Set<string>())
  const rightRunIdRef = React.useRef(rightRunId)

  const pairIds = leftRunId !== noSelection && rightRunId !== noSelection ? `${leftRunId}:${rightRunId}` : null
  const pairResult = loadedPair?.ids === pairIds ? loadedPair : null
  const pair = pairResult?.pair ?? null
  const duration = pair?.left.frames.at(-1)?.time ?? 0
  const byStart = frameWindows.ids === pairIds ? frameWindows.byStart : null
  const currentFrames = byStart ? framesAt(byStart, time) : null
  const isBuffering = Boolean(pair) && !currentFrames
  const networkId = pair ? networkIdOf(pair) : null
  const geometry = loadedGeometry && loadedGeometry.networkId === networkId ? loadedGeometry.geometry : null
  const firstLoaded = byStart ? Object.values(byStart)[0] : undefined
  const junctionId = studyJunctionId(currentFrames?.left ?? firstLoaded?.left[0])
  const condensedTimes = React.useMemo(() => pair?.left.frames.map((frame) => frame.time) ?? [], [pair])
  const condensedIndex = frameAtTime(condensedTimes, time)
  const windowStart = frameWindow(time, WINDOW_SECONDS).start
  const needsNextWindow = time >= windowStart + WINDOW_SECONDS - PREFETCH_SECONDS

  React.useEffect(() => { timeRef.current = time }, [time])
  React.useEffect(() => { windowsRef.current = byStart ?? {} }, [byStart])
  React.useEffect(() => { rightRunIdRef.current = rightRunId }, [rightRunId])

  const loadRuns = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await listCompareRuns()
      setRuns(response.runs)
      setNotice(response.runs.length ? null : "No completed pre-record timelines are ready for comparison.")
    } catch (error) {
      setNotice(compareErrorMessage(error, "Unable to load compare runs."))
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) void loadRuns() })
    return () => { active = false }
  }, [loadRuns])

  React.useEffect(() => {
    if (leftRunId === noSelection) return
    let isMounted = true
    listCompatibleCompareRuns(Number(leftRunId))
      .then((response) => {
        if (!isMounted) return
        setCompatibleRuns(response.runs)
        // A swap keeps the compared run: it stays compatible because pairing is symmetric.
        if (!response.runs.some((option) => String(option.run.id) === rightRunIdRef.current)) setRightRunId(noSelection)
        setNotice(response.runs.length ? null : "No compatible run found for that scenario, seed, and duration.")
      })
      .catch((error) => {
        if (!isMounted) return
        setCompatibleRuns([])
        setRightRunId(noSelection)
        setNotice(compareErrorMessage(error, "Unable to load compatible runs."))
      })
    return () => { isMounted = false }
  }, [leftRunId])

  // The pair loads as soon as both runs are chosen.
  React.useEffect(() => {
    if (!pairIds) return
    let active = true
    queueMicrotask(() => { if (active) setIsLoading(true) })
    getComparePair(Number(leftRunId), Number(rightRunId))
      .then((response) => { if (active) setLoadedPair({ ids: pairIds, pair: response, error: null }) })
      .catch((error) => { if (active) setLoadedPair({ ids: pairIds, pair: null, error: compareErrorMessage(error, "Unable to load compare pair.") }) })
      .finally(() => { if (active) setIsLoading(false) })
    return () => { active = false }
  }, [pairIds, leftRunId, rightRunId])

  // One network geometry serves both maps, because pairing guarantees the same network.
  React.useEffect(() => {
    if (!networkId || loadedGeometry?.networkId === networkId) return
    let active = true
    getVisualNetwork(networkId)
      .then((network) => { if (active) setLoadedGeometry({ networkId, geometry: normalizeSceneGeometry(network) }) })
      .catch((error) => { if (active) setFramesError(compareErrorMessage(error, "Unable to load the network map.")) })
    return () => { active = false }
  }, [networkId, loadedGeometry])

  // Fetch the window that holds the playback position, and the next one shortly before it ends.
  React.useEffect(() => {
    if (!pair || !pairIds) return
    const wanted = [windowStart, ...(needsNextWindow && windowStart + WINDOW_SECONDS <= duration ? [windowStart + WINDOW_SECONDS] : [])]
    for (const start of wanted) {
      const requestKey = `${pairIds}:${start}`
      if (requestedRef.current.has(requestKey)) continue
      requestedRef.current.add(requestKey)
      getComparePairFrames(pair.left.option.run.id, pair.right.option.run.id, start, start + WINDOW_SECONDS)
        .then((response) => {
          setFrameWindows((current) => {
            const kept = current.ids === pairIds ? current.byStart : {}
            const nearby = Object.fromEntries(Object.entries(kept).filter(([key]) => Math.abs(Number(key) - start) <= WINDOW_SECONDS * 3))
            return { ids: pairIds, byStart: { ...nearby, [start]: response } }
          })
        })
        .catch((error) => {
          requestedRef.current.delete(requestKey)
          setFramesError(compareErrorMessage(error, "Unable to load playback frames."))
        })
    }
  }, [pair, pairIds, windowStart, needsNextWindow, duration])

  // Playback follows simulation time, not a fixed delay per frame, and waits for frames rather than skipping.
  React.useEffect(() => {
    if (!isPlaying || duration <= 0) return
    let frameId = 0
    let last = performance.now()
    const tick = (now: number) => {
      frameId = requestAnimationFrame(tick)
      const elapsed = now - last
      if (elapsed < MIN_STEP_MS) return
      last = now
      const next = advancePlayback(timeRef.current, elapsed, speed, duration)
      if (!windowsRef.current[frameWindow(next.time, WINDOW_SECONDS).start]) return
      timeRef.current = next.time
      setTime(next.time)
      if (next.finished) setIsPlaying(false)
    }
    frameId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameId)
  }, [isPlaying, speed, duration])

  function resetPlayback() {
    timeRef.current = 0
    setTime(0)
    setIsPlaying(false)
    setFramesError(null)
    requestedRef.current = new Set()
  }

  function selectBaseline(value: string) {
    resetPlayback()
    setLeftRunId(value)
    setRightRunId(noSelection)
    setCompatibleRuns([])
  }

  function selectCompared(value: string) {
    resetPlayback()
    setRightRunId(value)
  }

  function swapRuns() {
    if (pairIds === null) return
    const previousBaseline = runs.find((option) => String(option.run.id) === leftRunId)
    resetPlayback()
    setLeftRunId(rightRunId)
    setRightRunId(leftRunId)
    setCompatibleRuns((current) => previousBaseline ? [previousBaseline, ...current.filter((option) => String(option.run.id) !== rightRunId)] : current)
  }

  function seek(next: number, keepPlaying = false) {
    const bounded = Math.min(Math.max(next, 0), duration)
    timeRef.current = bounded
    setTime(bounded)
    if (!keepPlaying) setIsPlaying(false)
  }

  function togglePlayback() {
    if (!pair || duration <= 0) return
    if (!isPlaying && time >= duration) seek(0, true)
    setIsPlaying((current) => !current)
  }

  function handlePlayerKeys(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!pair) return
    const onButton = (event.target as HTMLElement).closest("button") !== null
    if (event.key === " " && !onButton) {
      event.preventDefault()
      togglePlayback()
    } else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault()
      seek(time + (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 10 : 1))
    }
  }

  const failedSafety = (warning: string) => warning.includes("failed a safety check")
  const baselineTitle = pair ? runTitle(pair.left.option) : ""
  const comparedTitle = pair ? runTitle(pair.right.option) : ""

  return (
    <main className="compare-page">
      <section className="compare-hero">
        <div>
          <h1>Compare Runs</h1>
          <p>Watch two compatible recordings play side by side, then see what changed.</p>
        </div>
        <div className="compare-hero-actions">
          <Button variant="outline" type="button" onClick={loadRuns} disabled={isLoading}>
            <RefreshCcwIcon data-icon="inline-start" />
            Refresh
          </Button>
        </div>
      </section>

      <section className="compare-picker" aria-label="Choose runs">
        <div className="compare-picker-field">
          <span>Baseline</span>
          <RunSelect label="Baseline run" value={leftRunId} onChange={selectBaseline} options={runs} placeholder="Select a baseline run" disabled={runs.length === 0} />
        </div>
        <Button type="button" variant="outline" size="icon" onClick={swapRuns} disabled={pairIds === null} aria-label="Swap baseline and compared run">
          <ArrowLeftRightIcon />
        </Button>
        <div className="compare-picker-field">
          <span>Compare with</span>
          <RunSelect label="Compared run" value={rightRunId} onChange={selectCompared} options={compatibleRuns} placeholder="Select a compatible run" disabled={leftRunId === noSelection || compatibleRuns.length === 0} />
        </div>
        {pair ? <Badge variant="secondary" className="compare-match-chip">{matchSummary(pair)}</Badge> : null}
      </section>

      {notice ? <Alert><GitCompareArrowsIcon /><AlertDescription role="status">{notice}</AlertDescription></Alert> : null}
      {pairResult?.error ? <Alert variant="destructive"><TriangleAlertIcon /><AlertDescription>{pairResult.error}</AlertDescription></Alert> : null}
      {framesError ? <Alert variant="destructive"><TriangleAlertIcon /><AlertDescription>{framesError}</AlertDescription></Alert> : null}
      {pair?.warnings.map((warning) => (
        <Alert key={warning} variant={failedSafety(warning) ? "destructive" : "default"}>
          <TriangleAlertIcon />
          <AlertDescription>{warning}</AlertDescription>
        </Alert>
      ))}

      {!pair ? (
        <Empty className="compare-empty">
          <EmptyHeader>
            <EmptyTitle>{pairIds && isLoading ? "Loading the pair…" : "Pick two recorded runs"}</EmptyTitle>
            <EmptyDescription>Choose a baseline run, then a compatible run to compare with. Both play here side by side as soon as both are chosen.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <>
          <section className="compare-maps">
            {geometry ? (
              <>
                <CompareMap geometry={geometry} frame={currentFrames?.left ?? null} title={`Baseline · ${baselineTitle}`} runKey={`${pairIds}:left`} junctionId={junctionId} queue={condensedIndex >= 0 ? studyQueue(pair.left.frames[condensedIndex].queues) : null} />
                <CompareMap geometry={geometry} frame={currentFrames?.right ?? null} title={`Compared · ${comparedTitle}`} runKey={`${pairIds}:right`} junctionId={junctionId} queue={condensedIndex >= 0 ? studyQueue(pair.right.frames[condensedIndex].queues) : null} />
              </>
            ) : <p className="compare-maps-loading" role="status">Loading the network map…</p>}
          </section>

          <section className="compare-player" aria-label="Playback" onKeyDown={handlePlayerKeys}>
            <Button type="button" onClick={togglePlayback} disabled={duration <= 0} aria-label={isPlaying ? "Pause" : "Play"}>
              {isPlaying ? <PauseIcon data-icon="inline-start" /> : <PlayIcon data-icon="inline-start" />}
              {isPlaying ? "Pause" : "Play"}
            </Button>
            <ToggleGroup aria-label="Playback speed" variant="outline" value={[String(speed)]} onValueChange={(values) => values[0] && setSpeed(Number(values[0]) as 1 | 2 | 4)}>
              {[1, 2, 4].map((option) => <ToggleGroupItem key={option} value={String(option)}>{option}×</ToggleGroupItem>)}
            </ToggleGroup>
            <input
              className="compare-scrubber-input"
              type="range"
              aria-label="Simulation time"
              min={0}
              max={duration}
              step="any"
              value={Math.min(time, duration)}
              disabled={duration <= 0}
              onChange={(event) => seek(Number(event.target.value))}
            />
            <strong className="compare-time">{formatNumber(time, 0)} s / {formatNumber(duration, 0)} s</strong>
            {isBuffering ? <span className="compare-buffering" role="status">Loading frames…</span> : null}
            <small className="compare-player-hint">Space plays or pauses; arrow keys step 1 s (Shift: 10 s).</small>
          </section>

          <KpiCards pair={pair} />
          <HistoryChart pair={pair} time={time} duration={duration} onSeek={seek} />

          <Collapsible className="compare-details">
            <CollapsibleTrigger render={<Button variant="ghost" size="sm" className="-ml-2" />}>
              <ChevronDownIcon data-icon="inline-start" />
              Run details
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="compare-run-grid">
                <RunMetaCard bundle={pair.left} role="Baseline" />
                <RunMetaCard bundle={pair.right} role="Compared" />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </>
      )}
    </main>
  )
}

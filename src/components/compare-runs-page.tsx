import * as React from "react"
import {
  ArrowDownIcon,
  ArrowLeftRightIcon,
  ArrowUpIcon,
  ChevronDownIcon,
  DownloadIcon,
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
import { ApiError, SESSION_EXPIRED_EVENT, SESSION_RESTORED_EVENT } from "@/api/client"
import { toast } from "sonner"
import {
  getCompareHistory,
  getComparePair,
  getComparePairFrames,
  getCompareReport,
  listCompareRuns,
  listCompatibleCompareRuns,
  type ComparePairFramesResponse,
  type ComparePairHistory,
  type ComparePairResponse,
  type CompareRunBundle,
  type CompareRunOption,
} from "@/api/compare"
import { CompareMap } from "@/components/compare-map"
import { CompareSignalsCard } from "@/components/compare-signals"
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
import { Progress, ProgressLabel } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
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
import { advancePlayback, compareFrameWindow, frameAtTime, frameWindow, kpiChange, studyJunctionId, windowsNear, windowsToRequest } from "@/lib/compare-view"
import { controlLabel, isRlControl } from "@/lib/control-labels"
import { EMPTY_VALUE } from "@/lib/display-format"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"
import "@/styles/compare-runs.css"

const noSelection = "none"
// Each frame is about 30 KB per run, so the page asks for 10 s at a time (the server allows up to 60 s).
const WINDOW_SECONDS = 10
const PREFETCH_SECONDS = 5
const MIN_STEP_MS = 66
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

function matchSummary(pair: ComparePairResponse) {
  const { run, timeline } = pair.left.option
  const same = `Same scenario (${run.scenario_name ?? "unknown"}), seed ${run.seed ?? "none"}, ${formatNumber(timeline.actual_duration_seconds, 0)} s`
  const differs = pair.comparison_type === "signal" ? "signal controller differs"
    : pair.comparison_type === "routing" ? "routing differs" : "repeat of the same setup"
  return `${same}; ${differs}`
}

function framesAt(loaded: ComparePairFramesResponse | null | undefined, time: number) {
  if (!loaded?.times.length) return null
  const index = Math.max(0, frameAtTime(loaded.times, time))
  return { left: loaded.left[index], right: loaded.right[index] }
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
  const [expanded, setExpanded] = React.useState(false)
  const primary = ["avg_wait", "throughput", "avg_queue", "max_queue", "unfinished_vehicles", "avg_ped_delay"]
  return (
    <Card className="compare-kpi-card">
      <CardHeader>
        <CardTitle>What changed</CardTitle>
        <CardDescription>Baseline → compared. Each change applies to that metric; read wait, completed trips and unfinished demand together.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="compare-kpi-grid">
          {(expanded ? kpiRows : primary.map(key => kpiRows.find(row => row.key === key)!)).map((row) => {
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
        <Button variant="ghost" size="sm" className="mt-3" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
          <ChevronDownIcon data-icon="inline-start" />{expanded ? "Show key results" : "All metrics and measurement details"}
        </Button>
        <MetricDefinitions keys={kpiRows.map((row) => row.key)} />
      </CardContent>
    </Card>
  )
}

function DeferredCompareSection({ title, ready, children }: { title: string; ready: boolean; children: React.ReactNode }) {
  const section = React.useRef<HTMLDivElement>(null)
  const [visible, setVisible] = React.useState(false)

  React.useEffect(() => {
    if (!ready || visible || !section.current) return
    if (typeof IntersectionObserver === "undefined") {
      const timer = window.setTimeout(() => setVisible(true), 0)
      return () => window.clearTimeout(timer)
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        observer.disconnect()
        setVisible(true)
      }
    }, { rootMargin: "120px" })
    observer.observe(section.current)
    return () => observer.disconnect()
  }, [ready, visible])

  return <div ref={section}>{visible ? children : <Card>
    <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
    <CardContent><Skeleton className="h-12 w-full" /></CardContent>
  </Card>}</div>
}

function HistoryChart({ left, right, time, duration, onSeek, sessionRevision }: {
  left: number; right: number; time: number; duration: number; onSeek: (time: number) => void; sessionRevision: number
}) {
  const [tab, setTab] = React.useState<ChartTab>("wait")
  const [result, setResult] = React.useState<{ history: ComparePairHistory } | { error: string } | null>(null)
  const [revision, retry] = React.useReducer((value: number) => value + 1, 0)
  React.useEffect(() => {
    const request = new AbortController()
    getCompareHistory(left, right, request.signal)
      .then(history => { if (!request.signal.aborted) setResult({ history }) })
      .catch(error => {
        if (!request.signal.aborted) setResult({ error: compareErrorMessage(error, "Unable to load recorded metrics.") })
      })
    return () => request.abort()
  }, [left, right, revision, sessionRevision])
  const history = result && "history" in result ? result.history : null
  const data = React.useMemo(() => history?.left.map((leftFrame, index) => {
    const rightFrame = history.right[index]
    return {
      time: leftFrame.time,
      leftWait: leftFrame.interpreted_metrics?.avg_wait ?? null,
      rightWait: rightFrame?.interpreted_metrics?.avg_wait ?? null,
      leftQueue: leftFrame.interpreted_metrics?.avg_queue ?? null,
      rightQueue: rightFrame?.interpreted_metrics?.avg_queue ?? null,
      leftThroughput: leftFrame.interpreted_metrics?.throughput ?? null,
      rightThroughput: rightFrame?.interpreted_metrics?.throughput ?? null,
    }
  }) ?? [], [history])
  const chart = chartTabs[tab]
  return (
    <Card className="compare-chart-card">
      <CardHeader>
        <CardTitle>{chart.title}</CardTitle>
        <CardDescription>Sampled metrics across both recordings. The vertical line is the playback position. Click the chart to jump there.</CardDescription>
      </CardHeader>
      <CardContent>
        {result && "error" in result ? <Alert variant="destructive"><TriangleAlertIcon /><AlertDescription>
          {result.error} <Button variant="outline" size="sm" onClick={() => { setResult(null); retry() }}>Retry chart</Button>
        </AlertDescription></Alert> : !history ? <p role="status" className="text-sm text-muted-foreground">Loading recorded metrics…</p> : <>
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
        </>}
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
  const [frameWindows, setFrameWindows] = React.useState<FrameWindows>({ ids: null, byStart: {} })
  const [framesError, setFramesError] = React.useState<string | null>(null)
  const [time, setTime] = React.useState(0)
  const [isPlaying, setIsPlaying] = React.useState(false)
  const [seekRevision, setSeekRevision] = React.useState(0)
  const [speed, setSpeed] = React.useState<1 | 2 | 4>(1)
  const [isLoadingRuns, setIsLoadingRuns] = React.useState(false)
  const [notice, setNotice] = React.useState<string | null>(null)
  const timeRef = React.useRef(0)
  const windowsRef = React.useRef<Record<number, ComparePairFramesResponse>>({})
  const inFlightRef = React.useRef(new Map<string, AbortController>())
  const requestedWindowsRef = React.useRef<number[]>([])
  const pairIdsRef = React.useRef<string | null>(null)
  const [retryCount, setRetryCount] = React.useState(0)
  const [pairAttempt, retryPair] = React.useReducer((value: number) => value + 1, 0)
  const [sessionRevision, setSessionRevision] = React.useState(0)
  const [isExporting, setIsExporting] = React.useState(false)
  const frameRequestsBlocked = React.useRef(false)
  const rightRunIdRef = React.useRef(rightRunId)

  const pairIds = leftRunId !== noSelection && rightRunId !== noSelection ? `${leftRunId}:${rightRunId}` : null
  const pairResult = loadedPair?.ids === pairIds ? loadedPair : null
  const pair = pairResult?.pair ?? null
  const playbackTimes = pair?.playback_times
  const duration = playbackTimes?.at(-1) ?? 0
  const windowStart = compareFrameWindow(playbackTimes, time, WINDOW_SECONDS)
  const byStart = frameWindows.ids === pairIds ? frameWindows.byStart : null
  const bufferedFrames = framesAt(byStart?.[windowStart], time)
  const currentFrames = bufferedFrames ?? (time === 0 ? framesAt(pair?.opening_frames, time) : null)
  const geometry = React.useMemo(() => pair?.geometry ? normalizeSceneGeometry(pair.geometry) : null, [pair])
  const isBuffering = Boolean(geometry) && !bufferedFrames && !framesError
  const firstLoaded = byStart ? Object.values(byStart)[0] : undefined
  const junctionId = studyJunctionId(currentFrames?.left ?? firstLoaded?.left[0])
  const isLoadingPair = Boolean(pairIds) && !pairResult
  const isOpeningPlayback = isBuffering && !firstLoaded
  const detailReady = !geometry || Boolean(firstLoaded || framesError)
  const nextFrameIndex = playbackTimes ? frameAtTime(playbackTimes, windowStart + WINDOW_SECONDS - 1e-7) + 1 : 0
  const nextFrameTime = playbackTimes?.[nextFrameIndex]
  const prefetchStart = nextFrameTime !== undefined && nextFrameTime - time <= PREFETCH_SECONDS
    ? frameWindow(nextFrameTime, WINDOW_SECONDS).start : null

  React.useEffect(() => { timeRef.current = time }, [time])
  React.useEffect(() => { windowsRef.current = byStart ?? {} }, [byStart])
  React.useEffect(() => { rightRunIdRef.current = rightRunId }, [rightRunId])
  const cancelFrameRequests = React.useCallback(() => {
    const requests = inFlightRef.current
    inFlightRef.current = new Map()
    for (const request of requests.values()) request.abort()
  }, [])

  React.useEffect(() => {
    pairIdsRef.current = pairIds
    return cancelFrameRequests
  }, [pairIds, cancelFrameRequests])
  React.useEffect(() => {
    const expired = () => {
      frameRequestsBlocked.current = true
      cancelFrameRequests()
      setIsPlaying(false)
      setFramesError("Session ended. Sign in to continue from this comparison.")
    }
    const restored = () => {
      frameRequestsBlocked.current = false
      cancelFrameRequests()
      setFramesError(null)
      setSessionRevision(value => value + 1)
      setRetryCount(value => value + 1)
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, expired)
    window.addEventListener(SESSION_RESTORED_EVENT, restored)
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, expired)
      window.removeEventListener(SESSION_RESTORED_EVENT, restored)
    }
  }, [cancelFrameRequests])

  const loadRuns = React.useCallback(async () => {
    setIsLoadingRuns(true)
    try {
      const response = await listCompareRuns()
      setRuns(response.runs)
      setNotice(response.runs.length ? null : "No completed pre-record timelines are ready for comparison.")
    } catch (error) {
      setNotice(compareErrorMessage(error, "Unable to load compare runs."))
    } finally {
      setIsLoadingRuns(false)
    }
  }, [])

  React.useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) void loadRuns() })
    return () => { active = false }
  }, [loadRuns, sessionRevision])

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
  }, [leftRunId, sessionRevision])

  // The pair loads as soon as both runs are chosen.
  React.useEffect(() => {
    if (!pairIds) return
    const request = new AbortController()
    getComparePair(Number(leftRunId), Number(rightRunId), request.signal)
      .then((response) => {
        if (!request.signal.aborted) setLoadedPair({ ids: pairIds, pair: response, error: null })
      })
      .catch((error) => {
        if (!request.signal.aborted) setLoadedPair({ ids: pairIds, pair: null, error: compareErrorMessage(error, "Unable to load compare pair.") })
      })
    return () => request.abort()
  }, [pairIds, leftRunId, rightRunId, sessionRevision, pairAttempt])

  // Fetch the window that holds the playback position, and the next one shortly before it ends.
  // A window that was dropped from the cache, or whose request failed, is requested again when it is needed.
  React.useEffect(() => {
    if (!pair || !pairIds || !geometry || frameRequestsBlocked.current) return
    const wanted = prefetchStart === null ? [windowStart] : [windowStart, prefetchStart]
    requestedWindowsRef.current = wanted
    const requests = inFlightRef.current
    const inFlight = new Set([...requests.keys()].filter((key) => key.startsWith(`${pairIds}:`)).map((key) => Number(key.split(":").pop())))
    for (const start of windowsToRequest(wanted, byStart ?? {}, inFlight)) {
      const requestKey = `${pairIds}:${start}`
      const request = new AbortController()
      requests.set(requestKey, request)
      getComparePairFrames(pair.left.option.run.id, pair.right.option.run.id, start, start + WINDOW_SECONDS, request.signal)
        .then((response) => {
          requests.delete(requestKey)
          const stillWanted = requestedWindowsRef.current
          if (request.signal.aborted || frameRequestsBlocked.current || inFlightRef.current !== requests || pairIdsRef.current !== pairIds || !stillWanted.includes(start)) return
          setFramesError(null)
          setFrameWindows((current) => {
            const kept = current.ids === pairIds ? current.byStart : {}
            return { ids: pairIds, byStart: { ...windowsNear(kept, stillWanted[0], WINDOW_SECONDS * 3, stillWanted[1]), [start]: response } }
          })
        })
        .catch((error) => {
          requests.delete(requestKey)
          const stillWanted = requestedWindowsRef.current
          if (request.signal.aborted || inFlightRef.current !== requests || pairIdsRef.current !== pairIds || !stillWanted.includes(start)) return
          setFramesError(compareErrorMessage(error, "Unable to load playback frames."))
          frameRequestsBlocked.current = true
          setIsPlaying(false)
        })
    }
  }, [pair, pairIds, geometry, windowStart, prefetchStart, byStart, retryCount])

  // Playback follows simulation time, not a fixed delay per frame, and waits for frames rather than skipping.
  React.useEffect(() => {
    if (!isPlaying || duration <= 0 || !geometry) return
    let frameId = 0
    let last = performance.now()
    const tick = (now: number) => {
      frameId = requestAnimationFrame(tick)
      const elapsed = now - last
      if (elapsed < MIN_STEP_MS) return
      last = now
      const next = advancePlayback(timeRef.current, Math.min(elapsed, 250), speed, duration)
      if (!windowsRef.current[compareFrameWindow(playbackTimes, next.time, WINDOW_SECONDS)]) return
      timeRef.current = next.time
      setTime(next.time)
      if (next.finished) setIsPlaying(false)
    }
    frameId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameId)
  }, [isPlaying, speed, duration, geometry, playbackTimes])

  function resetPlayback() {
    timeRef.current = 0
    setTime(0)
    setIsPlaying(false)
    setFramesError(null)
    cancelFrameRequests()
    frameRequestsBlocked.current = false
    setLoadedPair(null)
  }

  async function exportReport() {
    if (!pair || isExporting) return
    setIsExporting(true)
    try {
      const blob = await getCompareReport(pair.left.option.run.id, pair.right.option.run.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `smartflow-comparison-${pair.left.option.run.id}-${pair.right.option.run.id}.pdf`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      toast.success("Comparison PDF downloaded")
    } catch (error) { toast.error(compareErrorMessage(error, "Unable to create the PDF.")) }
    finally { setIsExporting(false) }
  }

  function retryFrames() {
    frameRequestsBlocked.current = false
    cancelFrameRequests()
    setFramesError(null)
    setRetryCount(value => value + 1)
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
    setSeekRevision((revision) => revision + 1)
    if (!keepPlaying) setIsPlaying(false)
  }

  function togglePlayback() {
    if (!geometry || duration <= 0 || frameRequestsBlocked.current || (!bufferedFrames && !isPlaying)) return
    if (!isPlaying && time >= duration) seek(0, true)
    setIsPlaying((current) => !current)
  }

  function handlePlayerKeys(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!geometry || event.defaultPrevented || (event.target as HTMLElement).closest("[data-compare-speed]")) return
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
          <Button type="button" onClick={exportReport} disabled={!pair || isExporting}>
            <DownloadIcon data-icon="inline-start" />{isExporting ? "Preparing PDF…" : "Download PDF report"}
          </Button>
          <Button variant="outline" type="button" onClick={loadRuns} disabled={isLoadingRuns}>
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
      {pairResult?.error ? <Alert variant="destructive"><TriangleAlertIcon /><AlertDescription>
        {pairResult.error} <Button variant="outline" size="sm" onClick={() => { setLoadedPair(null); retryPair() }}>Retry comparison</Button>
      </AlertDescription></Alert> : null}
      {isLoadingPair || isOpeningPlayback ? <div className="compare-loading" role="status">
        <Progress className="compare-load-progress" value={null}>
          <ProgressLabel>{isLoadingPair ? "Preparing comparison…" : "Buffering the opening playback window…"}</ProgressLabel>
        </Progress>
      </div> : null}
      {framesError ? <Alert variant="destructive"><TriangleAlertIcon /><AlertDescription>
        {framesError} <Button variant="outline" size="sm" onClick={retryFrames}>Retry playback</Button>
      </AlertDescription></Alert> : null}
      {pair?.warnings.filter(failedSafety).map((warning) => (
        <Alert key={warning} variant={failedSafety(warning) ? "destructive" : "default"}>
          <TriangleAlertIcon />
          <AlertDescription>{warning}</AlertDescription>
        </Alert>
      ))}
      {pair ? <Collapsible className="compare-evidence">
        <CollapsibleTrigger render={<Button variant="ghost" size="sm" />}>
          <ChevronDownIcon data-icon="inline-start" />About this comparison · simulation evidence
        </CollapsibleTrigger>
        <CollapsibleContent><ul className="flex flex-col gap-2 p-4 text-sm text-muted-foreground">
          {pair.warnings.filter(warning => !failedSafety(warning)).map(warning => <li key={warning}>{warning}</li>)}
        </ul></CollapsibleContent>
      </Collapsible> : null}

      {!pair ? (
        !pairIds ? <Empty className="compare-empty">
          <EmptyHeader>
            <EmptyTitle>Pick two recorded runs</EmptyTitle>
            <EmptyDescription>Choose a baseline run, then a compatible run to compare with.</EmptyDescription>
          </EmptyHeader>
        </Empty> : null
      ) : (
        <>
          <section className="compare-maps">
            {geometry ? (
              <>
                <CompareMap geometry={geometry} frame={currentFrames?.left ?? null} title={`Baseline · ${baselineTitle}`} runKey={`${pairIds}:left`} junctionId={junctionId} playing={isPlaying} speed={speed} seekRevision={seekRevision} />
                <CompareMap geometry={geometry} frame={currentFrames?.right ?? null} title={`Compared · ${comparedTitle}`} runKey={`${pairIds}:right`} junctionId={junctionId} playing={isPlaying} speed={speed} seekRevision={seekRevision} />
              </>
            ) : <p className="compare-maps-loading" role="status">Recorded map unavailable.</p>}
          </section>

          <section className="compare-player" aria-label="Playback" onKeyDown={handlePlayerKeys}>
            <Button type="button" onClick={togglePlayback} disabled={!geometry || duration <= 0 || Boolean(framesError) || (!bufferedFrames && !isPlaying)} aria-label={isPlaying ? "Pause" : "Play"}>
              {isPlaying ? <PauseIcon data-icon="inline-start" /> : <PlayIcon data-icon="inline-start" />}
              {isPlaying ? "Pause" : "Play"}
            </Button>
            <ToggleGroup data-compare-speed aria-label="Playback speed" variant="outline" value={[String(speed)]} onValueChange={(values) => {
              if (!values[0] || Number(values[0]) === speed) return
              setSpeed(Number(values[0]) as 1 | 2 | 4)
              setSeekRevision((revision) => revision + 1)
            }}>
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
              disabled={!geometry || duration <= 0}
              onChange={(event) => seek(Number(event.target.value))}
            />
            <strong className="compare-time">{formatNumber(time, 0)} s / {formatNumber(duration, 0)} s</strong>
            {isBuffering && !isOpeningPlayback ? <span className="compare-buffering" role="status">Loading frames…</span> : null}
            <small className="compare-player-hint">Space plays or pauses; arrow keys step 1 s (Shift: 10 s).</small>
          </section>

          <KpiCards pair={pair} />
          <DeferredCompareSection key={`${pairIds}:signals`} title="How the signal changed" ready={detailReady}>
            <CompareSignalsCard left={pair.left.option.run.id} right={pair.right.option.run.id} />
          </DeferredCompareSection>
          <DeferredCompareSection key={`${pairIds}:history`} title="Performance history" ready={detailReady}>
            <HistoryChart left={pair.left.option.run.id} right={pair.right.option.run.id} time={time} duration={duration}
              onSeek={seek} sessionRevision={sessionRevision} />
          </DeferredCompareSection>

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

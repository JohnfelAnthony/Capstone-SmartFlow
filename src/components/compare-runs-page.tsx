import * as React from "react"
import {
  ActivityIcon,
  BarChart3Icon,
  ClockIcon,
  GitCompareArrowsIcon,
  PauseIcon,
  PlayIcon,
  RefreshCcwIcon,
  UsersRoundIcon,
} from "lucide-react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ApiError } from "@/api/client"
import {
  getComparePair,
  listCompareRuns,
  listCompatibleCompareRuns,
  type ComparePairResponse,
  type CompareRunBundle,
  type CompareRunOption,
  type CompareTimelineFrame,
} from "@/api/compare"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import "@/styles/compare-runs.css"

const noSelection = "none"
const approachLabels = ["north", "east", "south", "west"]
const kpiRows = [
  { key: "avg_waiting_time", label: "Avg Wait", unit: "s", lowerIsBetter: true },
  { key: "avg_queue_length", label: "Avg Queue", unit: "veh", lowerIsBetter: true },
  { key: "max_queue_length", label: "Max Queue", unit: "veh", lowerIsBetter: true },
  { key: "throughput", label: "Throughput", unit: "veh", lowerIsBetter: false },
  { key: "avg_pedestrian_delay", label: "Ped Delay", unit: "s", lowerIsBetter: true },
  { key: "scheduled_vehicles", label: "Scheduled Vehicles", unit: "veh", lowerIsBetter: null },
  { key: "unfinished_vehicles", label: "Unfinished Vehicles", unit: "veh", lowerIsBetter: true },
]

function compareErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return fallback
}

function formatNumber(value: number | null | undefined, digits = 1) {
  const safeValue = Number.isFinite(value) ? Number(value) : 0
  return safeValue.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

function metricValue(metrics: Record<string, unknown>, key: string) {
  const raw = metrics.raw_metrics as Record<string, unknown> | undefined
  const value = metrics[key] ?? raw?.[key]
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function runModeLabel(value: string | null | undefined) {
  return String(value || "unknown").replaceAll("-", " ")
}

function RunSelect({
  value,
  onChange,
  options,
  placeholder,
  disabled,
}: {
  value: string
  onChange: (value: string) => void
  options: CompareRunOption[]
  placeholder: string
  disabled?: boolean
}) {
  return (
    <Select value={value} onValueChange={(nextValue) => onChange(nextValue ?? noSelection)} disabled={disabled}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem value={noSelection}>{placeholder}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.run.id} value={String(option.run.id)}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

function StatStrip({ pair }: { pair: ComparePairResponse | null }) {
  const frameCount = pair?.frame_count ?? 0
  const duration = pair ? Math.min(pair.left.option.timeline.actual_duration_seconds, pair.right.option.timeline.actual_duration_seconds) : 0
  const compatible = pair ? `${pair.comparison_type[0].toUpperCase()}${pair.comparison_type.slice(1)}` : "Waiting"
  const stats = [
    { label: "Comparable Frames", value: frameCount.toLocaleString(), icon: ActivityIcon },
    { label: "Synced Duration", value: `${formatNumber(duration, 1)}s`, icon: ClockIcon },
    { label: "Comparison", value: compatible, icon: GitCompareArrowsIcon },
    { label: "Intersection", value: pair?.left.option.timeline.intersection_id ?? "None", icon: BarChart3Icon },
  ]
  return (
    <div className="compare-metric-strip">
      {stats.map((stat) => {
        const Icon = stat.icon
        return (
          <div className="compare-strip-metric" key={stat.label}>
            <Icon />
            <div>
              <strong>{stat.value}</strong>
              <small>{stat.label}</small>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function RunMetaCard({ bundle, side }: { bundle: CompareRunBundle | null; side: "Left" | "Right" }) {
  if (!bundle) {
    return (
      <Card className="compare-run-card">
        <CardHeader>
          <CardTitle>{side} Run</CardTitle>
          <CardDescription>Select a recorded run.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const { run, timeline } = bundle.option
  const provenance = bundle.option.provenance
  return (
    <Card className="compare-run-card">
      <CardHeader>
        <CardTitle>
          {side} Run #{run.id}
        </CardTitle>
        <CardDescription>{run.scenario_name ?? "Unknown scenario"}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="compare-meta-grid">
          <div>
            <span>Controller</span>
            <strong>{runModeLabel(run.control_mode)}</strong>
          </div>
          <div><span>Model</span><strong>{provenance.model_id ? `#${provenance.model_id}` : "Fixed-time / none"}</strong></div>
          <div><span>Model SHA-256</span><strong>{provenance.model_sha256 ?? "—"}</strong></div>
          <div><span>Demand</span><strong>{provenance.demand_source ?? "Unknown"}: {provenance.demand_description ?? "—"}</strong></div>
          <div><span>Demand SHA-256</span><strong>{provenance.demand_sha256 ?? "—"}</strong></div>
          <div><span>Network SHA-256</span><strong>{provenance.network_sha256 ?? "—"}</strong></div>
          <div>
            <span>Seed</span>
            <strong>{run.seed ?? "None"}</strong>
          </div>
          <div>
            <span>Duration</span>
            <strong>{formatNumber(timeline.actual_duration_seconds, 1)}s</strong>
          </div>
          <div>
            <span>Step</span>
            <strong>{formatNumber(timeline.step_length_seconds, 2)}s</strong>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function CurrentFrameCard({
  bundle,
  frame,
  side,
}: {
  bundle: CompareRunBundle | null
  frame: CompareTimelineFrame | null
  side: "Left" | "Right"
}) {
  return (
    <Card className="compare-frame-card">
      <CardHeader>
        <CardTitle>{side} Frame</CardTitle>
        <CardDescription>{bundle ? `Run #${bundle.option.run.id}` : "No pair loaded"}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="compare-frame-head">
          <div>
            <span>Time</span>
            <strong>{formatNumber(frame?.time, 1)}s</strong>
          </div>
          <div>
            <span>Phase</span>
            <strong>{frame?.phase ?? "UNKNOWN"}</strong>
          </div>
          <div>
            <span>Vehicles</span>
            <strong>{frame?.vehicle_count ?? 0}</strong>
          </div>
          <div>
            <span>Pedestrians</span>
            <strong>{frame?.pedestrian_count ?? 0}</strong>
          </div>
        </div>
        <div className="compare-queue-bars">
          {approachLabels.map((approach) => {
            const queue = frame?.queues?.[approach] ?? 0
            const maxQueue = Math.max(...approachLabels.map((item) => frame?.queues?.[item] ?? 0), 1)
            const width = Math.min((queue / maxQueue) * 100, 100)
            return (
              <div className="compare-queue-row" key={approach}>
                <span>{approach}</span>
                <div className="compare-queue-track">
                  <div className="compare-queue-fill" style={{ width: `${width}%` }} />
                </div>
                <strong>{formatNumber(queue, 0)}</strong>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

function TimelineChart({ pair }: { pair: ComparePairResponse | null }) {
  const data = React.useMemo(() => {
    if (!pair) return []
    return pair.left.frames.map((leftFrame, index) => {
      const rightFrame = pair.right.frames[index]
      return {
        time: leftFrame.time,
        leftWait: leftFrame.avg_wait,
        rightWait: rightFrame?.avg_wait ?? 0,
        leftQueue: leftFrame.avg_queue,
        rightQueue: rightFrame?.avg_queue ?? 0,
        leftThroughput: leftFrame.throughput,
        rightThroughput: rightFrame?.throughput ?? 0,
      }
    })
  }, [pair])

  return (
    <Card className="compare-chart-card">
      <CardHeader>
        <CardTitle>Metric History</CardTitle>
        <CardDescription>Saved timeline frames, played back together.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="compare-chart-grid">
          {[
            { title: "Average Wait", left: "leftWait", right: "rightWait" },
            { title: "Average Queue", left: "leftQueue", right: "rightQueue" },
            { title: "Throughput", left: "leftThroughput", right: "rightThroughput" },
          ].map((chart) => (
            <div className="compare-chart-panel" key={chart.title}>
              <strong>{chart.title}</strong>
              <ResponsiveContainer width="100%" height={190}>
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="time" tickLine={false} axisLine={false} minTickGap={28} />
                  <YAxis tickLine={false} axisLine={false} width={38} />
                  <Tooltip />
                  <Line type="monotone" dataKey={chart.left} stroke="var(--chart-2)" dot={false} strokeWidth={2} name="Left" />
                  <Line type="monotone" dataKey={chart.right} stroke="var(--chart-1)" dot={false} strokeWidth={2} name="Right" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function KpiTable({ pair }: { pair: ComparePairResponse | null }) {
  return (
    <Card className="compare-kpi-card">
      <CardHeader>
        <CardTitle>KPI Comparison</CardTitle>
        <CardDescription>Final metrics persisted with each simulation run.</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Metric</TableHead>
              <TableHead>Left</TableHead>
              <TableHead>Right</TableHead>
              <TableHead>Delta</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {kpiRows.map((row) => {
              const left = pair ? metricValue(pair.left.metrics, row.key) : 0
              const right = pair ? metricValue(pair.right.metrics, row.key) : 0
              const delta = left === null || right === null ? null : right - left
              const isNeutral = delta === null || Math.abs(delta) < 0.0001 || row.lowerIsBetter === null
              const isGood = delta !== null && (row.lowerIsBetter ? delta < 0 : delta > 0)
              return (
                <TableRow key={row.key}>
                  <TableCell>{row.label}</TableCell>
                  <TableCell>{left === null ? "—" : formatNumber(left, row.key.includes("vehicles") || row.key === "throughput" ? 0 : 2)} {row.unit}</TableCell>
                  <TableCell>{right === null ? "—" : formatNumber(right, row.key.includes("vehicles") || row.key === "throughput" ? 0 : 2)} {row.unit}</TableCell>
                  <TableCell>
                    <Badge variant={isNeutral ? "secondary" : isGood ? "default" : "destructive"}>
                      {delta === null ? "—" : `${delta >= 0 ? "+" : ""}${formatNumber(delta, row.key.includes("vehicles") || row.key === "throughput" ? 0 : 2)}`}
                    </Badge>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function CompareRunsPage() {
  const [runs, setRuns] = React.useState<CompareRunOption[]>([])
  const [compatibleRuns, setCompatibleRuns] = React.useState<CompareRunOption[]>([])
  const [leftRunId, setLeftRunId] = React.useState(noSelection)
  const [rightRunId, setRightRunId] = React.useState(noSelection)
  const [pair, setPair] = React.useState<ComparePairResponse | null>(null)
  const [frameIndex, setFrameIndex] = React.useState(0)
  const [isPlaying, setIsPlaying] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(false)
  const [notice, setNotice] = React.useState("Loading compare-ready timeline runs.")

  const frameMax = Math.max((pair?.frame_count ?? 0) - 1, 0)
  const leftFrame = pair?.left.frames[Math.min(frameIndex, frameMax)] ?? null
  const rightFrame = pair?.right.frames[Math.min(frameIndex, frameMax)] ?? null

  const loadRuns = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await listCompareRuns()
      setRuns(response.runs)
      setNotice(response.runs.length ? "Compare-ready timeline runs loaded from SQLite." : "No completed pre-record timelines are ready for comparison.")
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
    if (leftRunId === noSelection) {
      return
    }
    let isMounted = true
    listCompatibleCompareRuns(Number(leftRunId))
      .then((response) => {
        if (!isMounted) return
        setCompatibleRuns(response.runs)
        setRightRunId(noSelection)
        setNotice(response.runs.length ? "Compatible right-side runs loaded." : "No compatible run found for that scenario, seed, and duration.")
      })
      .catch((error) => {
        if (!isMounted) return
        setCompatibleRuns([])
        setRightRunId(noSelection)
        setNotice(compareErrorMessage(error, "Unable to load compatible runs."))
      })
    return () => {
      isMounted = false
    }
  }, [leftRunId])

  React.useEffect(() => {
    if (!isPlaying || !pair || pair.frame_count <= 1) return
    const timer = window.setInterval(() => {
      setFrameIndex((current) => {
        if (current >= pair.frame_count - 1) {
          window.clearInterval(timer)
          setIsPlaying(false)
          return current
        }
        return current + 1
      })
    }, 140)
    return () => window.clearInterval(timer)
  }, [isPlaying, pair])

  async function handleLoadPair() {
    if (leftRunId === noSelection || rightRunId === noSelection) {
      setNotice("Select a left run and a compatible right run first.")
      return
    }
    setIsLoading(true)
    setIsPlaying(false)
    try {
      const response = await getComparePair(Number(leftRunId), Number(rightRunId))
      setPair(response)
      setFrameIndex(0)
      const comparisonLabel = `${response.comparison_type[0].toUpperCase()}${response.comparison_type.slice(1)} comparison loaded.`
      setNotice([comparisonLabel, ...response.warnings].join(" "))
    } catch (error) {
      setPair(null)
      setNotice(compareErrorMessage(error, "Unable to load compare pair."))
    } finally {
      setIsLoading(false)
    }
  }

  function handleLeftChange(nextValue: string) {
    setLeftRunId(nextValue)
    setRightRunId(noSelection)
    setPair(null)
    setFrameIndex(0)
    setIsPlaying(false)
  }

  return (
    <main className="compare-page">
      <section className="compare-hero">
        <div>
          <h1>Compare Runs</h1>
          <p>Load two compatible pre-recorded timelines and review their saved playback metrics side by side.</p>
        </div>
        <div className="compare-hero-actions">
          <Button variant="outline" type="button" onClick={loadRuns} disabled={isLoading}>
            <RefreshCcwIcon data-icon="inline-start" />
            Refresh
          </Button>
        </div>
      </section>

      <StatStrip pair={pair} />

      <div className="compare-notice">
        <GitCompareArrowsIcon />
        <span>{notice}</span>
      </div>

      <section className="compare-controls">
        <Card>
          <CardHeader>
            <CardTitle>Left Run</CardTitle>
            <CardDescription>Choose the baseline timeline first.</CardDescription>
          </CardHeader>
          <CardContent>
            <RunSelect value={leftRunId} onChange={handleLeftChange} options={runs} placeholder="Select left run" disabled={isLoading || runs.length === 0} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Right Run</CardTitle>
            <CardDescription>Only compatible timelines are shown here.</CardDescription>
          </CardHeader>
          <CardContent>
            <RunSelect
              value={rightRunId}
              onChange={setRightRunId}
              options={compatibleRuns}
              placeholder="Select compatible run"
              disabled={isLoading || leftRunId === noSelection || compatibleRuns.length === 0}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Playback</CardTitle>
            <CardDescription>Scrub or play the paired recordings together.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="compare-load-actions">
              <Button type="button" onClick={handleLoadPair} disabled={isLoading || leftRunId === noSelection || rightRunId === noSelection}>
                <GitCompareArrowsIcon data-icon="inline-start" />
                Load Pair
              </Button>
              <Button type="button" variant="outline" onClick={() => setIsPlaying((current) => !current)} disabled={!pair || pair.frame_count <= 1}>
                {isPlaying ? <PauseIcon data-icon="inline-start" /> : <PlayIcon data-icon="inline-start" />}
                {isPlaying ? "Pause" : "Play"}
              </Button>
            </div>
            <div className="compare-scrubber">
              <div>
                <span>Frame</span>
                <strong>{pair ? `${Math.min(frameIndex + 1, pair.frame_count)}/${pair.frame_count}` : "0/0"}</strong>
              </div>
              <input
                type="range"
                min="0"
                max={frameMax}
                value={Math.min(frameIndex, frameMax)}
                disabled={!pair || pair.frame_count <= 1}
                onChange={(event) => {
                  setIsPlaying(false)
                  setFrameIndex(Number(event.target.value))
                }}
              />
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="compare-run-grid">
        <RunMetaCard bundle={pair?.left ?? null} side="Left" />
        <RunMetaCard bundle={pair?.right ?? null} side="Right" />
      </section>

      <section className="compare-frame-grid">
        <CurrentFrameCard bundle={pair?.left ?? null} frame={leftFrame} side="Left" />
        <CurrentFrameCard bundle={pair?.right ?? null} frame={rightFrame} side="Right" />
      </section>

      <section className="compare-analysis-grid">
        <TimelineChart pair={pair} />
        <KpiTable pair={pair} />
      </section>

      {!pair ? (
        <div className="compare-empty">
          <UsersRoundIcon />
          <span>Select two compatible recorded runs to unlock playback, charts, and KPI deltas.</span>
        </div>
      ) : null}
    </main>
  )
}

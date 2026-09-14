import * as React from "react"
import {
  BarChart3Icon,
  CheckCircle2Icon,
  DownloadIcon,
  FileJsonIcon,
  FileSpreadsheetIcon,
  HistoryIcon,
  ListFilterIcon,
  PlayCircleIcon,
  RefreshCcwIcon,
  StarIcon,
  Trash2Icon,
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
  deleteRun,
  exportRuns,
  favoriteRun,
  getRunTimeline,
  listRuns,
  type RunTimelineResponse,
} from "@/api/runs"
import { listScenarios, type ApiScenario } from "@/api/scenarios"
import { loadPlayback, type SimulationRunRecord } from "@/api/simulation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
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
import { cn } from "@/lib/utils"
import "@/styles/runs-reports.css"

type FilterState = {
  scenarioId: string
  runMode: string
  controlMode: string
  status: string
}

const defaultFilters: FilterState = {
  scenarioId: "all",
  runMode: "all",
  controlMode: "all",
  status: "all",
}

function runsErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return fallback
}

function formatDate(value: string | null) {
  if (!value) return "Unknown"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value))
}

function formatMode(value: string | null | undefined) {
  return String(value || "unknown").replaceAll("-", " ")
}

function metricNumber(run: SimulationRunRecord, key: string) {
  const value = run.metrics?.[key]
  return typeof value === "number" && Number.isFinite(value) ? value : 0
}

function compactNumber(value: number, digits = 0) {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase()
  return (
    <Badge
      variant={normalized === "completed" ? "secondary" : normalized === "running" ? "outline" : "destructive"}
      className={cn("runs-status-badge", normalized)}
    >
      {formatMode(status)}
    </Badge>
  )
}

function TimelinePreviewCard({
  preview,
  selectedRun,
  isLoading,
}: {
  preview: RunTimelineResponse | null
  selectedRun: SimulationRunRecord | null
  isLoading: boolean
}) {
  const hasRecordedTimeline =
    selectedRun?.status === "completed" && selectedRun.run_mode === "pre-record" && Boolean(selectedRun.timeline_path)
  const frames = preview?.frames ?? []
  const chartData = frames.map((frame) => ({
    time: frame.time,
    avgWait: frame.avg_wait,
    avgQueue: frame.avg_queue,
    throughput: frame.throughput,
  }))

  return (
    <Card className="runs-timeline-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3Icon />
          Timeline Preview
        </CardTitle>
        <CardDescription>
          {selectedRun ? `Recorded frame history for run #${selectedRun.id}.` : "Select a recorded run to inspect timeline frames."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedRun ? (
          <div className="runs-empty-state">No run selected.</div>
        ) : !hasRecordedTimeline ? (
          <div className="runs-empty-state">This run does not have a completed pre-record timeline artifact.</div>
        ) : isLoading ? (
          <div className="runs-empty-state">Loading timeline frames...</div>
        ) : preview && frames.length ? (
          <div className="runs-timeline-layout">
            <div className="runs-timeline-summary">
              <div><span>Frames</span><strong>{preview.timeline.frame_count.toLocaleString()}</strong></div>
              <div><span>Duration</span><strong>{compactNumber(preview.timeline.actual_duration_seconds, 1)}s</strong></div>
              <div><span>Step</span><strong>{compactNumber(preview.timeline.step_length_seconds, 2)}s</strong></div>
              <div><span>Intersection</span><strong>{preview.timeline.intersection_id ?? "Unknown"}</strong></div>
            </div>
            <div className="runs-timeline-chart">
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="time" tickLine={false} axisLine={false} minTickGap={28} />
                  <YAxis tickLine={false} axisLine={false} width={42} />
                  <Tooltip />
                  <Line type="monotone" dataKey="avgWait" stroke="var(--chart-1)" dot={false} strokeWidth={2} name="Avg Wait" />
                  <Line type="monotone" dataKey="avgQueue" stroke="var(--chart-2)" dot={false} strokeWidth={2} name="Avg Queue" />
                  <Line type="monotone" dataKey="throughput" stroke="var(--chart-3)" dot={false} strokeWidth={2} name="Throughput" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : (
          <div className="runs-empty-state">Timeline metadata is available, but no preview frames were returned.</div>
        )}
      </CardContent>
    </Card>
  )
}

function RunsSelect({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (value: string) => void
  options: { label: string; value: string }[]
}) {
  return (
    <Select value={value} onValueChange={(nextValue) => nextValue !== null && onChange(nextValue)}>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

export function RunsReportsPage({ onOpenDashboard }: { onOpenDashboard?: () => void }) {
  const [runs, setRuns] = React.useState<SimulationRunRecord[]>([])
  const [scenarios, setScenarios] = React.useState<ApiScenario[]>([])
  const [filters, setFilters] = React.useState<FilterState>(defaultFilters)
  const [selectedRunIds, setSelectedRunIds] = React.useState<number[]>([])
  const [selectedRunId, setSelectedRunId] = React.useState<number | null>(null)
  const [timelinePreview, setTimelinePreview] = React.useState<RunTimelineResponse | null>(null)
  const [isTimelineLoading, setIsTimelineLoading] = React.useState(false)
  const [alert, setAlert] = React.useState("Loading simulation run history.")
  const [isLoading, setIsLoading] = React.useState(false)

  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null
  const selectedIds = selectedRunIds.length ? selectedRunIds : selectedRun ? [selectedRun.id] : []
  const completedRuns = runs.filter((run) => run.status === "completed")
  const avgWait =
    completedRuns.length > 0
      ? completedRuns.reduce((sum, run) => sum + metricNumber(run, "avg_waiting_time"), 0) / completedRuns.length
      : 0
  const throughputTotal = completedRuns.reduce((sum, run) => sum + metricNumber(run, "throughput"), 0)

  const loadData = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const [scenarioResponse, runResponse] = await Promise.all([
        listScenarios(),
        listRuns({
          scenarioId: filters.scenarioId === "all" ? undefined : Number(filters.scenarioId),
          runMode: filters.runMode === "all" ? undefined : filters.runMode,
          controlMode: filters.controlMode === "all" ? undefined : filters.controlMode,
          status: filters.status === "all" ? undefined : filters.status,
          limit: 300,
        }),
      ])
      setScenarios(scenarioResponse.scenarios)
      setRuns(runResponse.runs)
      setSelectedRunId((current) => current ?? runResponse.runs[0]?.id ?? null)
      setSelectedRunIds((current) => current.filter((id) => runResponse.runs.some((run) => run.id === id)))
      setAlert("Simulation run history loaded from SQLite.")
    } catch (error) {
      setAlert(runsErrorMessage(error, "Unable to load runs and reports."))
    } finally {
      setIsLoading(false)
    }
  }, [filters])

  React.useEffect(() => {
    void loadData()
  }, [loadData])

  React.useEffect(() => {
    let isMounted = true
    setTimelinePreview(null)

    const hasRecordedTimeline =
      selectedRun?.status === "completed" && selectedRun.run_mode === "pre-record" && Boolean(selectedRun.timeline_path)
    if (!selectedRun || !hasRecordedTimeline) {
      setIsTimelineLoading(false)
      return
    }

    setIsTimelineLoading(true)
    getRunTimeline(selectedRun.id)
      .then((response) => {
        if (isMounted) {
          setTimelinePreview(response)
        }
      })
      .catch((error) => {
        if (isMounted) {
          setAlert(runsErrorMessage(error, `Unable to load timeline preview for run #${selectedRun.id}.`))
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsTimelineLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [selectedRun?.id, selectedRun?.run_mode, selectedRun?.status, selectedRun?.timeline_path])

  function toggleSelected(runId: number, checked: boolean) {
    setSelectedRunIds((current) => {
      if (checked) return current.includes(runId) ? current : [...current, runId]
      return current.filter((id) => id !== runId)
    })
  }

  async function toggleFavorite(run: SimulationRunRecord) {
    try {
      const updated = await favoriteRun(run.id, !run.is_favorite)
      setRuns((current) => current.map((item) => (item.id === updated.id ? updated : item)))
      setAlert(`Run #${run.id} ${updated.is_favorite ? "marked as favorite" : "removed from favorites"}.`)
    } catch (error) {
      setAlert(runsErrorMessage(error, `Unable to update favorite for run #${run.id}.`))
    }
  }

  async function deleteSelectedRuns() {
    if (!selectedIds.length) {
      setAlert("Select at least one run first.")
      return
    }
    try {
      await Promise.all(selectedIds.map((runId) => deleteRun(runId)))
      setRuns((current) => current.filter((run) => !selectedIds.includes(run.id)))
      setSelectedRunIds([])
      setSelectedRunId(null)
      setAlert(`Deleted ${selectedIds.length} selected run${selectedIds.length === 1 ? "" : "s"}.`)
    } catch (error) {
      setAlert(runsErrorMessage(error, "Unable to delete selected runs."))
    }
  }

  async function exportSelected(format: "csv" | "json") {
    if (!selectedIds.length) {
      setAlert("Select at least one run to export.")
      return
    }
    try {
      await exportRuns(selectedIds, format)
      setAlert(`Export started for ${selectedIds.length} run${selectedIds.length === 1 ? "" : "s"}.`)
    } catch (error) {
      setAlert(runsErrorMessage(error, "Unable to export selected runs."))
    }
  }

  async function replaySelectedRun() {
    if (!selectedRun) {
      setAlert("Select a completed run first.")
      return
    }
    if (selectedRun.status !== "completed") {
      setAlert("Only completed runs can be replayed.")
      return
    }
    try {
      const response = await loadPlayback(selectedRun.id)
      setAlert(response.message)
      onOpenDashboard?.()
    } catch (error) {
      setAlert(runsErrorMessage(error, `Unable to load run #${selectedRun.id} for replay.`))
    }
  }

  const scenarioOptions = [
    { label: "All Scenarios", value: "all" },
    ...scenarios.map((scenario) => ({ label: scenario.name, value: String(scenario.id) })),
  ]

  const metrics = [
    { label: "Total Runs", value: runs.length, hint: "Current filters", icon: HistoryIcon, tone: "info" },
    { label: "Completed", value: completedRuns.length, hint: "Replay-ready", icon: CheckCircle2Icon, tone: "success" },
    { label: "Avg Wait", value: `${compactNumber(avgWait, 1)}s`, hint: "Completed runs", icon: BarChart3Icon, tone: "warning" },
    { label: "Throughput", value: compactNumber(throughputTotal), hint: "Total vehicles", icon: ListFilterIcon, tone: "purple" },
  ]

  return (
    <main className="smartflow-page runs-page">
      <section className="runs-hero">
        <div>
          <h1>Runs & Reports</h1>
          <p>Review saved simulations, replay completed timelines, and export report data.</p>
        </div>
        <div className="runs-hero-actions">
          <Button variant="outline" onClick={() => void loadData()} disabled={isLoading}>
            <RefreshCcwIcon data-icon="inline-start" />
            Refresh
          </Button>
          <Button onClick={replaySelectedRun} disabled={!selectedRun}>
            <PlayCircleIcon data-icon="inline-start" />
            Replay
          </Button>
        </div>
      </section>

      <section className="runs-metric-strip" aria-label="Runs metrics">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div key={metric.label} className={cn("runs-strip-metric", metric.tone)}>
              <Icon />
              <div>
                <div>
                  <strong>{metric.value}</strong>
                  <span>{metric.label}</span>
                </div>
                <small>{metric.hint}</small>
              </div>
            </div>
          )
        })}
      </section>

      <div className="runs-notice">
        <HistoryIcon />
        <span>{alert}</span>
      </div>

      <section className="runs-layout">
        <Card className="runs-filter-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListFilterIcon />
              Filters
            </CardTitle>
            <CardDescription>Match Dash run history filters.</CardDescription>
          </CardHeader>
          <CardContent className="runs-filter-stack">
            <RunsSelect value={filters.scenarioId} onChange={(scenarioId) => setFilters({ ...filters, scenarioId })} options={scenarioOptions} />
            <RunsSelect
              value={filters.runMode}
              onChange={(runMode) => setFilters({ ...filters, runMode })}
              options={[
                { label: "All Run Modes", value: "all" },
                { label: "Live", value: "live" },
                { label: "Pre-record", value: "pre-record" },
              ]}
            />
            <RunsSelect
              value={filters.controlMode}
              onChange={(controlMode) => setFilters({ ...filters, controlMode })}
              options={[
                { label: "All Control Modes", value: "all" },
                { label: "Fixed-Time", value: "fixed-time" },
                { label: "RL Agent", value: "rl-agent" },
                { label: "Playback", value: "playback" },
              ]}
            />
            <RunsSelect
              value={filters.status}
              onChange={(status) => setFilters({ ...filters, status })}
              options={[
                { label: "All Statuses", value: "all" },
                { label: "Completed", value: "completed" },
                { label: "Running", value: "running" },
                { label: "Stopped", value: "stopped" },
                { label: "Error", value: "error" },
              ]}
            />
          </CardContent>
        </Card>

        <Card className="runs-table-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HistoryIcon />
              Simulation Runs
            </CardTitle>
            <CardDescription>{runs.length} saved run{runs.length === 1 ? "" : "s"} match the current filters.</CardDescription>
            <CardAction>
              <Badge variant="secondary">{selectedIds.length} selected</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="runs-table-shell">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Select</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>Scenario</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Avg Wait</TableHead>
                  <TableHead>Throughput</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => {
                  const isSelected = selectedRun?.id === run.id
                  return (
                    <TableRow key={run.id} className={cn(isSelected && "selected")} onClick={() => setSelectedRunId(run.id)}>
                      <TableCell>
                        <Checkbox
                          checked={selectedRunIds.includes(run.id)}
                          onCheckedChange={(checked) => toggleSelected(run.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell>#{run.id}</TableCell>
                      <TableCell>{run.scenario_name ?? "Unknown"}</TableCell>
                      <TableCell>{formatMode(run.run_mode)} / {formatMode(run.control_mode)}</TableCell>
                      <TableCell><StatusBadge status={run.status} /></TableCell>
                      <TableCell>{compactNumber(metricNumber(run, "avg_waiting_time"), 1)}s</TableCell>
                      <TableCell>{compactNumber(metricNumber(run, "throughput"))}</TableCell>
                      <TableCell>{formatDate(run.start_time)}</TableCell>
                      <TableCell>
                        <div className="runs-row-actions">
                          <Button variant="ghost" size="icon-sm" title="Favorite" onClick={() => void toggleFavorite(run)}>
                            <StarIcon className={cn(run.is_favorite && "runs-star-active")} />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card className="runs-actions-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DownloadIcon />
              Reports
            </CardTitle>
            <CardDescription>Export selected run records for offline analysis.</CardDescription>
          </CardHeader>
          <CardContent className="runs-action-stack">
            <Button onClick={() => void exportSelected("csv")}>
              <FileSpreadsheetIcon data-icon="inline-start" />
              Export CSV
            </Button>
            <Button variant="outline" onClick={() => void exportSelected("json")}>
              <FileJsonIcon data-icon="inline-start" />
              Export JSON
            </Button>
            <Button variant="destructive" onClick={() => void deleteSelectedRuns()}>
              <Trash2Icon data-icon="inline-start" />
              Delete Selected
            </Button>
          </CardContent>
        </Card>

        <Card className="runs-detail-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3Icon />
              Run Details
            </CardTitle>
            <CardDescription>{selectedRun ? `Run #${selectedRun.id}` : "Select a run to inspect metrics."}</CardDescription>
          </CardHeader>
          <CardContent>
            {selectedRun ? (
              <div className="runs-detail-grid">
                <div><span>Scenario</span><strong>{selectedRun.scenario_name ?? "Unknown"}</strong></div>
                <div><span>Duration</span><strong>{compactNumber(selectedRun.duration_seconds, 1)}s</strong></div>
                <div><span>Max Queue</span><strong>{compactNumber(metricNumber(selectedRun, "max_queue_length"))}</strong></div>
                <div><span>Pedestrian Delay</span><strong>{compactNumber(metricNumber(selectedRun, "avg_pedestrian_delay"), 1)}s</strong></div>
                <div><span>Seed</span><strong>{selectedRun.seed ?? "--"}</strong></div>
                <div><span>Timeline</span><strong>{selectedRun.timeline_path ? "Available" : "None"}</strong></div>
              </div>
            ) : (
              <div className="runs-empty-state">No run selected.</div>
            )}
          </CardContent>
        </Card>

        <TimelinePreviewCard preview={timelinePreview} selectedRun={selectedRun} isLoading={isTimelineLoading} />
      </section>
    </main>
  )
}

import { metricValue, metricLabel, metricDescription, metricDefinition, formatMetric } from "@/lib/metrics"
import { MetricDefinitions } from "@/components/metric-definitions"
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
  Legend,
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { NativeSelect } from "@/components/native-scenario-controls"
import { cn } from "@/lib/utils"
import { controlLabel } from "@/lib/control-labels"
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

function metricNumber(run: SimulationRunRecord, key: string) {
  return metricValue(run.metrics, key)
}

function rawRunMetrics(run: SimulationRunRecord): Record<string, unknown> {
  const raw = run.metrics?.raw_metrics
  return raw && typeof raw === "object" ? raw as Record<string, unknown> : {}
}

function sourceRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function RunSourceSummary({ run }: { run: SimulationRunRecord }) {
  const experiment = sourceRecord(rawRunMetrics(run).experiment)
  const settings = sourceRecord(experiment.config)
  const source = sourceRecord(settings.demand_source)
  const datasets = Array.isArray(source.datasets) ? source.datasets.map(sourceRecord) : []
  const text = (value: unknown) => typeof value === "string" && value ? value : "Not recorded"
  return <section className="runs-prose" aria-label="Saved input context">
    <p>Network: {text(experiment.network_id)}. Controlled junction: {text(settings.controlled_junction)}.</p>
    <p>Input assumptions: {text(source.description)}.</p>
    {datasets.length ? <ul>{datasets.map((dataset, index) => <li key={index}>
      {text(dataset.description)} — declared {text(dataset.kind)}; {text(dataset.schema)}; collected {text(dataset.collected_on)}, {text(dataset.collection_start)} to {text(dataset.collection_end)}. Conversion: {text(dataset.conversion)}.
    </li>)}</ul> : <p>No collection periods or reviewed datasets are recorded for this run.</p>}
  </section>
}

function demandSourceKind(run: SimulationRunRecord) {
  const experiment = rawRunMetrics(run).experiment as Record<string, unknown> | undefined
  const config = experiment?.config as Record<string, unknown> | undefined
  const source = config?.demand_source as Record<string, unknown> | undefined
  return typeof source?.kind === "string" ? source.kind : "—"
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
      {controlLabel(status)}
    </Badge>
  )
}

function hasRecordedTimeline(run: SimulationRunRecord | null) {
  return run?.status === "completed" && run.run_mode === "pre-record" && Boolean(run.timeline_path)
}

function TimelinePanel({ preview, run, isLoading }: { preview: RunTimelineResponse | null; run: SimulationRunRecord; isLoading: boolean }) {
  const frames = preview?.frames ?? []
  if (!hasRecordedTimeline(run)) return <p className="runs-empty-state">Only completed recordings keep a timeline. This run has none.</p>
  if (isLoading) return <p className="runs-empty-state">Loading timeline...</p>
  if (!preview || !frames.length) return <p className="runs-empty-state">No timeline frames were returned for this run.</p>
  const chartData = frames.map((frame) => ({
    time: frame.time,
    avgWait: frame.interpreted_metrics?.avg_wait ?? null,
    avgQueue: frame.interpreted_metrics?.avg_queue ?? null,
    throughput: frame.throughput,
  }))
  return <div className="flex flex-col gap-2">
    <p className="runs-empty-state">{preview.timeline.frame_count.toLocaleString()} frames over {compactNumber(preview.timeline.actual_duration_seconds, 1)} s.</p>
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="time" tickLine={false} axisLine={false} minTickGap={28} tickFormatter={(time) => `${time}s`} />
        <YAxis tickLine={false} axisLine={false} width={42} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="avgWait" stroke="var(--chart-1)" dot={false} strokeWidth={2} name="Average wait (s)" />
        <Line type="monotone" dataKey="avgQueue" stroke="var(--chart-2)" dot={false} strokeWidth={2} name="Average queue (veh)" />
        <Line type="monotone" dataKey="throughput" stroke="var(--chart-3)" dot={false} strokeWidth={2} name="Completed trips" />
      </LineChart>
    </ResponsiveContainer>
  </div>
}

function MetricTiles({ run, keys }: { run: SimulationRunRecord; keys: string[] }) {
  return <div className="runs-detail-grid">
    {keys.map((key) => {
      const value = metricNumber(run, key)
      return <div key={key} title={metricDescription(key)}><span>{metricLabel(key)}</span><strong>{formatMetric(value, 2)}{value === null ? "" : ` ${metricDefinition(key)?.unit ?? ""}`}</strong></div>
    })}
  </div>
}

export function RunsReportsPage({ onOpenDashboard, onOpenResearch, onOpenCompare }: {
  onOpenDashboard?: () => void;
  onOpenResearch?: () => void; onOpenCompare?: () => void;
}) {
  const [runs, setRuns] = React.useState<SimulationRunRecord[]>([])
  const [scenarios, setScenarios] = React.useState<ApiScenario[]>([])
  const [filters, setFilters] = React.useState<FilterState>(defaultFilters)
  const [selectedRunIds, setSelectedRunIds] = React.useState<number[]>([])
  const [selectedRunId, setSelectedRunId] = React.useState<number | null>(null)
  const [timelinePreview, setTimelinePreview] = React.useState<RunTimelineResponse | null>(null)
  const [isTimelineLoading, setIsTimelineLoading] = React.useState(false)
  const [alert, setAlert] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)

  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null
  const selectedIds = selectedRunIds.length ? selectedRunIds : selectedRun ? [selectedRun.id] : []
  const completedRuns = runs.filter((run) => run.status === "completed")
  const measuredWaits = completedRuns.map((run) => metricNumber(run, "avg_waiting_time")).filter((value): value is number => value !== null)
  const avgWait = measuredWaits.length ? measuredWaits.reduce((sum, value) => sum + value, 0) / measuredWaits.length : null
  const completions = completedRuns.map((run) => metricNumber(run, "throughput")).filter((value): value is number => value !== null)
  const throughputTotal = completions.length ? completions.reduce((sum, value) => sum + value, 0) : null

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
      setAlert("")
    } catch (error) {
      setAlert(runsErrorMessage(error, "Unable to load runs and reports."))
    } finally {
      setIsLoading(false)
    }
  }, [filters])

  React.useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) void loadData() })
    return () => { active = false }
  }, [loadData])

  React.useEffect(() => {
    let isMounted = true
    queueMicrotask(() => { if (isMounted) setTimelinePreview(null) })

    if (!selectedRun || !hasRecordedTimeline(selectedRun)) {
      queueMicrotask(() => { if (isMounted) setIsTimelineLoading(false) })
      return () => { isMounted = false }
    }

    queueMicrotask(() => { if (isMounted) setIsTimelineLoading(true) })
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
  }, [selectedRun])

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
      setAlert(`Exported ${selectedIds.length} run${selectedIds.length === 1 ? "" : "s"} as ${format.toUpperCase()}.`)
    } catch (error) {
      setAlert(runsErrorMessage(error, "Unable to export selected runs."))
    }
  }

  async function replaySelectedRun() {
    if (!selectedRun) {
      setAlert("Select a completed run first.")
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
    { label: "All", value: "all" },
    ...scenarios.map((scenario) => ({ label: scenario.name, value: String(scenario.id) })),
  ]

  const metrics = [
    { label: "Runs", value: runs.length, hint: "Matching the filters", icon: HistoryIcon, tone: "info" },
    { label: "Completed", value: completedRuns.length, hint: "Finished and saved", icon: CheckCircle2Icon, tone: "success" },
    { label: "Average wait", value: `${formatMetric(avgWait, 1)} s`, hint: "Mean across completed runs", icon: BarChart3Icon, tone: "warning" },
    { label: "Completed trips", value: formatMetric(throughputTotal, 0), hint: "Total across completed runs", icon: ListFilterIcon, tone: "purple" },
  ]
  const actionTarget = selectedRunIds.length
    ? `${selectedRunIds.length} ticked run${selectedRunIds.length === 1 ? "" : "s"}.`
    : selectedRun ? `Run #${selectedRun.id}, the highlighted row. Tick rows to choose several.` : "No run selected."
  const canReplay = hasRecordedTimeline(selectedRun)

  return (
    <main className="smartflow-page runs-page">
      <section className="runs-hero">
        <div>
          <h1>Runs & Reports</h1>
          <p>Review saved simulations, replay recordings and export results.</p>
        </div>
        <Button variant="outline" onClick={() => void loadData()} disabled={isLoading}>
          <RefreshCcwIcon data-icon="inline-start" />
          Refresh
        </Button>
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

      {alert ? <div className="runs-notice" role="status">
        <HistoryIcon />
        <span>{alert}</span>
      </div> : null}

      <section className="runs-layout">
        <Card className="runs-table-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HistoryIcon />
              Simulation runs
            </CardTitle>
            <CardDescription>Click a row to see its results below.</CardDescription>
          </CardHeader>
          <CardContent className="runs-table-shell">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead aria-label="Select" />
                  <TableHead>Run</TableHead>
                  <TableHead>Scenario</TableHead>
                  <TableHead>Signal control</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Avg wait</TableHead>
                  <TableHead>Trips</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead aria-label="Favorite" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.id} className={cn(selectedRun?.id === run.id && "selected")} onClick={() => setSelectedRunId(run.id)}>
                    <TableCell>
                      <Checkbox aria-label={`Select run ${run.id}`} checked={selectedRunIds.includes(run.id)} onCheckedChange={(checked) => toggleSelected(run.id, Boolean(checked))} />
                    </TableCell>
                    <TableCell>#{run.id}</TableCell>
                    <TableCell className="runs-scenario-cell" title={run.scenario_name ?? undefined}>{run.scenario_name ?? "Unknown"}</TableCell>
                    <TableCell className="whitespace-normal">{controlLabel(run.control_mode)}</TableCell>
                    <TableCell><StatusBadge status={run.status} /></TableCell>
                    <TableCell>{metricNumber(run, "avg_waiting_time") === null ? "—" : `${compactNumber(metricNumber(run, "avg_waiting_time")!, 1)} s`}</TableCell>
                    <TableCell>{metricNumber(run, "throughput") === null ? "—" : compactNumber(metricNumber(run, "throughput")!)}</TableCell>
                    <TableCell className="whitespace-normal">{formatDate(run.start_time)}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon-sm" title="Favorite" aria-label={`Favorite run ${run.id}`} onClick={() => void toggleFavorite(run)}>
                        <StarIcon className={cn(run.is_favorite && "runs-star-active")} />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {!runs.length ? <TableRow><TableCell colSpan={9} className="runs-empty-state py-8 text-center">{isLoading ? "Loading runs..." : "No runs match these filters."}</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card className="runs-filter-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListFilterIcon />
              Filters
            </CardTitle>
          </CardHeader>
          <CardContent className="runs-filter-stack">
            <NativeSelect label="Scenario" value={filters.scenarioId} onChange={(scenarioId) => setFilters({ ...filters, scenarioId })} options={scenarioOptions} />
            <NativeSelect label="Run type" value={filters.runMode} onChange={(runMode) => setFilters({ ...filters, runMode })}
              options={[{ label: "All", value: "all" }, { label: "Live", value: "live" }, { label: "Recording", value: "pre-record" }]} />
            <NativeSelect label="Signal control" value={filters.controlMode} onChange={(controlMode) => setFilters({ ...filters, controlMode })}
              options={[
                { label: "All", value: "all" },
                { label: controlLabel("fixed-time"), value: "fixed-time" },
                { label: controlLabel("no-signal"), value: "no-signal" },
                ...[...new Set(runs.map((run) => run.control_mode))].filter((mode) => !["fixed-time", "no-signal", "playback"].includes(mode))
                  .map((mode) => ({ label: controlLabel(mode), value: mode })),
                { label: "Playback", value: "playback" },
              ]} />
            <NativeSelect label="Status" value={filters.status} onChange={(status) => setFilters({ ...filters, status })}
              options={[{ label: "All", value: "all" }, { label: "Completed", value: "completed" }, { label: "Running", value: "running" }, { label: "Stopped", value: "stopped" }, { label: "Error", value: "error" }]} />
          </CardContent>
        </Card>

        <Card className="runs-actions-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DownloadIcon />
              Export or delete
            </CardTitle>
            <CardDescription>{actionTarget}</CardDescription>
          </CardHeader>
          <CardContent className="runs-action-stack">
            <div className="grid grid-cols-2 gap-2">
              <Button disabled={!selectedIds.length} onClick={() => void exportSelected("csv")}>
                <FileSpreadsheetIcon data-icon="inline-start" />
                CSV
              </Button>
              <Button variant="outline" disabled={!selectedIds.length} onClick={() => void exportSelected("json")}>
                <FileJsonIcon data-icon="inline-start" />
                JSON
              </Button>
            </div>
            <Button variant="destructive" disabled={!selectedIds.length} onClick={() => void deleteSelectedRuns()}>
              <Trash2Icon data-icon="inline-start" />
              Delete {selectedIds.length === 1 ? `run #${selectedIds[0]}` : `${selectedIds.length} runs`}
            </Button>
          </CardContent>
        </Card>

        <Card className="runs-detail-card">
          <CardHeader>
            <CardTitle>{selectedRun ? `Run #${selectedRun.id}` : "Run results"}</CardTitle>
            <CardDescription>{selectedRun ? selectedRun.scenario_name ?? "Unknown scenario" : "Select a run to see its results."}</CardDescription>
            {selectedRun ? <CardAction className="flex flex-wrap justify-end gap-2">
              {onOpenCompare ? <Button variant="outline" size="sm" onClick={onOpenCompare}>Compare runs</Button> : null}
              <Button size="sm" onClick={replaySelectedRun} disabled={!canReplay} title={canReplay ? undefined : "Only completed recordings can be replayed"}>
                <PlayCircleIcon data-icon="inline-start" />
                Replay
              </Button>
            </CardAction> : null}
          </CardHeader>
          {selectedRun ? <CardContent>
            <dl className="runs-facts">
              <div><dt>Signal control</dt><dd>{controlLabel(selectedRun.control_mode)}</dd></div>
              <div><dt>Run type</dt><dd>{selectedRun.run_mode === "pre-record" ? "Recording" : "Live"}</dd></div>
              <div><dt>Status</dt><dd><StatusBadge status={selectedRun.status} /></dd></div>
              <div><dt>Duration</dt><dd>{compactNumber(selectedRun.duration_seconds, 1)} s</dd></div>
              <div><dt>Seed</dt><dd>{selectedRun.seed ?? "—"}</dd></div>
              <div><dt>Input data</dt><dd>{demandSourceKind(selectedRun)}</dd></div>
              {selectedRun.rl_model_id ? <div><dt>Model</dt><dd>#{selectedRun.rl_model_id}</dd></div> : null}
            </dl>
            <Tabs defaultValue="results" className="mt-4">
              <TabsList>
                <TabsTrigger value="results">Results</TabsTrigger>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
                <TabsTrigger value="details">Inputs and definitions</TabsTrigger>
              </TabsList>
              <TabsContent value="results" className="flex flex-col gap-4 pt-3">
                <div>
                  <h3 className="runs-group-title">Traffic</h3>
                  <MetricTiles run={selectedRun} keys={["avg_wait", "avg_queue", "max_queue", "throughput", "avg_travel_time", "avg_ped_delay"]} />
                </div>
                <div>
                  <h3 className="runs-group-title">Vehicle demand</h3>
                  <MetricTiles run={selectedRun} keys={["requested_vehicles", "total_vehicles_spawned", "pending_demand", "dropped_vehicles", "unfinished_vehicles"]} />
                </div>
                <p className="runs-empty-state">One run shows these conditions only. It is not field evidence or an overall recommendation. — means unavailable.{selectedRun.notes ? ` Note: ${selectedRun.notes}` : ""}</p>
              </TabsContent>
              <TabsContent value="timeline" className="pt-3">
                <TimelinePanel preview={timelinePreview} run={selectedRun} isLoading={isTimelineLoading} />
              </TabsContent>
              <TabsContent value="details" className="flex flex-col gap-4 pt-3">
                <div>
                  <h3 className="runs-group-title">Measurement window</h3>
                  <MetricTiles run={selectedRun} keys={["measurement_start", "measurement_seconds", "boundary_wait_seconds", "avg_admitted_boundary_wait"]} />
                </div>
                <div>
                  <h3 className="runs-group-title">Inputs</h3>
                  <RunSourceSummary run={selectedRun} />
                  {onOpenResearch ? <Button className="mt-2" variant="outline" size="sm" onClick={onOpenResearch}>Review baseline evidence</Button> : null}
                </div>
                <details className="runs-prose"><summary>Saved settings for reproducing this run</summary><pre className="whitespace-pre-wrap break-all">{JSON.stringify(rawRunMetrics(selectedRun).experiment ?? { note: "This older run kept no saved settings." }, null, 2)}</pre></details>
                <MetricDefinitions />
              </TabsContent>
            </Tabs>
          </CardContent> : null}
        </Card>
      </section>
    </main>
  )
}

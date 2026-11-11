import { toast } from "sonner"
import * as React from "react"
import {
  ChartLineIcon,
  ChevronDownIcon,
  DatabaseIcon,
  DownloadIcon,
  GaugeIcon,
  ListChecksIcon,
  PlayIcon,
  RefreshCcwIcon,
  RotateCcwIcon,
  SquareIcon,
  TerminalIcon,
} from "lucide-react"
import {
  CartesianGrid,
  Line,
  LineChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ApiError } from "@/api/client"
import { resolveNativeScenario, type NativeScenarioConfig } from "@/api/native-scenario"
import { listScenarios, type ApiScenario } from "@/api/scenarios"
import {
  evaluateRLModel,
  getRLEvaluationReport,
  getRLTrainingStatus,
  listRLTrainingJobs,
  startRLTrainingJob,
  stopRLTrainingJob,
  type RLAdvancedSettings,
  type RLEvaluationReport,
  type RLLogLine,
  type RLModelRecord,
  type RLTrainingJob,
  type RLTrainingJobItem,
  type RLTrainingSettings,
  type RLTrainingStatusResponse,
} from "@/api/rl"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DesktopModelImport } from "@/components/desktop-model-import"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
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
import { EMPTY_VALUE, formatServerDate, parseServerTimestamp } from "@/lib/display-format"
import { resumeTargetCompatible } from "@/lib/rl-resume"
import { rewardSeries } from "@/lib/reward-series"
import { cn } from "@/lib/utils"
import "@/styles/rl-training.css"

type AlgorithmId = "ql" | "dql" | "ppo"
type TrainingTab = "models" | "train" | "jobs"
type ModelAction = "evaluate" | "resume"

type RewardPoint = {
  index: number
  algorithm: string
  episode: number
  reward: number
}

const algorithmOptions: { value: AlgorithmId; label: string }[] = [
  { value: "ql", label: "Q-Learning" },
  { value: "dql", label: "Deep Q-Learning" },
  { value: "ppo", label: "PPO" },
]

// Mirrors simulation/rl_env.py DEFAULT_* (engine fix plan P1-7): about 100k decisions from developed traffic.
const defaultSettings: RLTrainingSettings = {
  scenario_id: null,
  evaluation_scenario_id: null,
  episodes: 560,
  seeds: "11,22,33,44,55",
  evaluation_seeds: "101,102,103,104,105",
  warmup_seconds: 300,
  evaluation_seconds: 900,
  decision_interval_seconds: 5,
  minimum_green_hold_seconds: 10,
  checkpoint_every: 25,
  resume_model_id: null,
  resume_checkpoint_id: null,
}

const defaultAdvanced: RLAdvancedSettings = {
  ql: {
    alpha: 0.1,
    gamma: 0.9,
    epsilon: 0.2,
  },
  dql: {
    learning_starts: 500,
    buffer_size: 50000,
    batch_size: 32,
  },
  ppo: {
    n_steps: 128,
    batch_size: 64,
    n_epochs: 10,
  },
}

function rlErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return fallback
}

function statusLabel(value: string | null | undefined) {
  return String(value || "idle").replaceAll("_", " ").replaceAll("-", " ")
}

function selectedAlgorithmLabel(algorithms: string[]) {
  if (!algorithms.length) {
    return EMPTY_VALUE
  }
  return algorithms.map((algorithm) => algorithm.toUpperCase()).join(", ")
}

function parseRewardPoints(lines: RLLogLine[]): RewardPoint[] {
  const rewardPattern = /\[(\d+)\/\d+\s+\|\s+[\d.]+%\].*reward=(-?\d+(?:\.\d+)?)/
  return lines.flatMap((line, index) => {
    const match = rewardPattern.exec(line.text)
    if (!match) {
      return []
    }
    return [{
      index,
      algorithm: (line.algorithm || "rl").toUpperCase(),
      episode: Number(match[1]),
      reward: Number(match[2]),
    }]
  })
}

function compactNumber(value: number | null | undefined, digits = 1) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return EMPTY_VALUE
  }
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

function ScenarioSelect({
  id,
  scenarios,
  selectedScenarioId,
  onChange,
}: {
  id: string
  scenarios: ApiScenario[]
  selectedScenarioId: string
  onChange: (value: string) => void
}) {
  return (
    <Select value={selectedScenarioId} onValueChange={(value) => value !== null && onChange(value)}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue>{(value: string | null) => scenarios.find((scenario) => String(scenario.id) === value)?.name ?? "Select a scenario"}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {scenarios.map((scenario) => (
            <SelectItem key={scenario.id} value={String(scenario.id)}>
              {scenario.name}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
}) {
  const id = React.useId()
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </Field>
  )
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase()
  const isDanger = ["error", "interrupted"].includes(normalized)
  return (
    <Badge
      variant={isDanger ? "destructive" : "outline"}
      className={cn("rl-status-badge", normalized)}
    >
      {statusLabel(status)}
    </Badge>
  )
}

function ProgressBar({ value }: { value: number }) {
  const boundedValue = Math.max(0, Math.min(100, value || 0))
  return <Progress value={boundedValue} aria-label="Job progress" />
}

function JobConsole({ job, lines }: { job: RLTrainingJob | null; lines: RLLogLine[] }) {
  return (
    <Card className="rl-console-card">
      <CardHeader>
        <CardTitle className="rl-card-title"><TerminalIcon /> Live Console</CardTitle>
        {job && <CardDescription>Job #{job.id} · {lines.length} recent log lines</CardDescription>}
      </CardHeader>
      <CardContent className="rl-console-body">
        <div className="rl-console-frame">
          {lines.length
            ? <pre className="rl-console" tabIndex={0} aria-label="Worker output">{lines.slice(-140).map((line) => line.text).join("\n")}</pre>
            : <p className="rl-idle-console">{job ? "Waiting for worker output." : "Worker output appears here when a job starts."}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

function elapsedTime(job: RLTrainingJob) {
  const start = parseServerTimestamp(job.started_at)?.getTime()
  const end = parseServerTimestamp(job.ended_at)?.getTime() ?? Date.now()
  if (start === undefined) return EMPTY_VALUE
  const seconds = Math.max(0, Math.floor((end - start) / 1000))
  return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60]
    .map((value) => String(value).padStart(2, "0")).join(":")
}

function EvaluationResults({ jobId, report }: { jobId: number; report: RLEvaluationReport }) {
  function exportResults() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }))
    const link = document.createElement("a")
    link.href = url
    link.download = `smartflow-job-${jobId}-evaluation.json`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const excludedSeeds = Object.keys(report.excluded_matched_seeds ?? {})
  return (
    <Card>
      <CardHeader>
        <CardTitle>Held-out evaluation</CardTitle>
        <CardDescription>Mean metrics across matched runs. Seeds {report.seeds.join(", ")}.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {excludedSeeds.length > 0 && <p className="text-sm text-muted-foreground">Excluded seeds with safety or integrity issues: {excludedSeeds.join(", ")}.</p>}
        {Object.keys(report.summary).length ? (
          <Table>
            <TableHeader><TableRow>
              <TableHead>Controller</TableHead><TableHead>Stopped wait (s)</TableHead>
              <TableHead>Completed trips</TableHead><TableHead>Unfinished vehicles</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {report.controllers.filter((name) => report.summary[name]).map((name) => {
                const metrics = report.summary[name]
                return <TableRow key={name}>
                  <TableCell>{name === "fixed-time" ? "Fixed-time" : name === "no-signal" ? "No signal" : name.toUpperCase()}</TableCell>
                  <TableCell>{compactNumber(metrics.avg_wait?.mean)}</TableCell>
                  <TableCell>{compactNumber(metrics.throughput?.mean)}</TableCell>
                  <TableCell>{compactNumber(metrics.unfinished_vehicles?.mean)}</TableCell>
                </TableRow>
              })}
            </TableBody>
          </Table>
        ) : <p>No matched runs passed the checks for this summary.</p>}
        <Button className="self-start" variant="outline" onClick={exportResults}>
          <DownloadIcon data-icon="inline-start" /> Export results (JSON)
        </Button>
      </CardContent>
    </Card>
  )
}

export function RLTrainingPage({ currentUserId, isAdmin, canRunTraining }: { currentUserId: number; isAdmin: boolean; canRunTraining: boolean }) {
  const [algorithms, setAlgorithms] = React.useState<AlgorithmId[]>(["ql"])
  const [settings, setSettings] = React.useState<RLTrainingSettings>(defaultSettings)
  const [advanced, setAdvanced] = React.useState<RLAdvancedSettings>(defaultAdvanced)
  const [scenarios, setScenarios] = React.useState<ApiScenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = React.useState("")
  const [scenarioResolution, setScenarioResolution] = React.useState<{ id: string; config: NativeScenarioConfig | null } | null>(null)
  const [viewedJobId, setViewedJobId] = React.useState<number | null>(null)
  const [status, setStatus] = React.useState<RLTrainingStatusResponse>({
    active_job_id: null,
    job: null,
    items: [],
    log_lines: [],
    models: [],
  })
  const [jobs, setJobs] = React.useState<RLTrainingJob[]>([])
  const [selectedModelId, setSelectedModelId] = React.useState<number | null>(null)
  const [selectedCheckpointId, setSelectedCheckpointId] = React.useState<number | null>(null)
  const [alert, setAlert] = React.useState("")
  const [tab, setTab] = React.useState<TrainingTab | null>(null)
  const [modelAction, setModelAction] = React.useState<ModelAction | null>(null)
  const [evaluation, setEvaluation] = React.useState<{ jobId: number; report?: RLEvaluationReport; error?: string } | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [pendingAction, setPendingAction] = React.useState(false)
  const requestId = React.useRef(0)
  const viewedJobRef = React.useRef<number | null>(null)
  const inFlightRefreshes = React.useRef<Set<number | null>>(new Set())

  const scenarioConfig = scenarioResolution?.id === selectedScenarioId ? scenarioResolution.config : null
  const scenarioLoading = Boolean(selectedScenarioId && scenarioResolution?.id !== selectedScenarioId)
  // Models from an older contract cannot run or resume; they are hidden here, never deleted.
  const shownModels = status.models.filter((model) => model.compatible || model.checkpoints.some((checkpoint) => checkpoint.compatible))
  const hiddenModelCount = status.models.length - shownModels.length
  const selectedModel = status.models.find((model) => model.id === selectedModelId) ?? null
  const selectedModelMatchesScenario = Boolean(selectedModel && scenarioConfig && selectedModel.controlled_junction === scenarioConfig.controlled_junction)
  const viewedJob = status.job?.id === viewedJobId ? status.job : null
  const serverActiveJobId = status.active_job_id
  const viewedJobPending = viewedJob?.status === "queued" || viewedJob?.status === "running"
  const activeJob = jobs.find((job) => job.id === serverActiveJobId)
  const canStopActiveJob = Boolean(canRunTraining && serverActiveJobId && (isAdmin || activeJob?.user_id === currentUserId))
  const selectedScenario = scenarios.find((item) => String(item.id) === selectedScenarioId) ?? null
  const evaluationScenarios = scenarios.filter((item) => item.id !== settings.scenario_id
    && (!scenarioConfig?.controlled_junction || !item.engine_config?.controlled_junction
      || item.engine_config.controlled_junction === scenarioConfig.controlled_junction))
  const evaluationScenario = evaluationScenarios.find((item) => item.id === settings.evaluation_scenario_id)
  const selectedTab = tab ?? "models"
  const evaluatingModel = modelAction === "evaluate"
  const resumingModel = modelAction === "resume"
  const canSubmit = canRunTraining && !serverActiveJobId && !pendingAction && !scenarioLoading
  const reportJobId = selectedTab === "jobs" && viewedJob?.status === "completed"
    && status.items.some((item) => item.evaluation_path) ? viewedJob.id : null
  const activeItem = status.items.find((item) => item.id === viewedJob?.current_item_id) ?? status.items[0] ?? null
  const rewardChart = React.useMemo(() => rewardSeries(parseRewardPoints(status.log_lines)), [status.log_lines])

  const refreshStatus = React.useCallback(async (jobId: number | null = viewedJobRef.current) => {
    if (inFlightRefreshes.current.has(jobId)) return
    inFlightRefreshes.current.add(jobId)
    const thisRequest = ++requestId.current
    setIsLoading(true)
    try {
      const [nextStatus, nextJobs] = await Promise.all([
        getRLTrainingStatus(jobId),
        listRLTrainingJobs({ limit: 30 }),
      ])
      if (thisRequest === requestId.current && jobId === viewedJobRef.current) {
        setStatus(nextStatus)
        setJobs(nextJobs.jobs)
      }
    } catch (error) {
      if (thisRequest === requestId.current) setAlert(rlErrorMessage(error, "Unable to refresh RL training status."))
    } finally {
      inFlightRefreshes.current.delete(jobId)
      if (thisRequest === requestId.current) setIsLoading(false)
    }
  }, [])

  function viewJob(jobId: number | null) {
    if (jobId !== viewedJobRef.current) requestId.current += 1
    viewedJobRef.current = jobId
    setViewedJobId(jobId)
    setTab("jobs")
    void refreshStatus(jobId)
  }

  React.useEffect(() => {
    let isMounted = true

    async function loadInitial() {
      try {
        const [scenarioResponse, statusResponse, jobsResponse] = await Promise.all([
          listScenarios(),
          getRLTrainingStatus(),
          listRLTrainingJobs({ limit: 30 }),
        ])
        if (!isMounted) return
        setScenarios(scenarioResponse.scenarios)
        setSelectedScenarioId(String(scenarioResponse.scenarios[0]?.id ?? ""))
        setSettings((current) => ({ ...current,
          scenario_id: scenarioResponse.scenarios[0]?.id ?? null,
          evaluation_scenario_id: scenarioResponse.scenarios.find((scenario) => scenario.id !== scenarioResponse.scenarios[0]?.id)?.id ?? null,
        }))
        setStatus(statusResponse)
        setJobs(jobsResponse.jobs)
        setTab((current) => current ?? (statusResponse.active_job_id ? "jobs"
          : statusResponse.models.some((model) => model.compatible || model.checkpoints.some((checkpoint) => checkpoint.compatible))
            || !canRunTraining ? "models" : "train"))
        const initialJobId = statusResponse.job?.id ?? null
        viewedJobRef.current = initialJobId
        setViewedJobId(initialJobId)
      } catch (error) {
        if (isMounted) {
          setAlert(rlErrorMessage(error, "Unable to load RL training data."))
        }
      }
    }

    void loadInitial()
    return () => {
      isMounted = false
    }
  }, [canRunTraining])

  React.useEffect(() => {
    const scenarioId = Number(selectedScenarioId)
    if (!scenarioId) return
    let cancelled = false
    void resolveNativeScenario(scenarioId).then((response) => {
      if (!cancelled) setScenarioResolution({ id: selectedScenarioId, config: response.engine_config })
    }).catch((error) => {
      if (!cancelled) {
        setScenarioResolution({ id: selectedScenarioId, config: null })
        setAlert(rlErrorMessage(error, "Unable to load saved scenario settings."))
      }
    })
    return () => { cancelled = true }
  }, [selectedScenarioId])

  React.useEffect(() => {
    if (!serverActiveJobId && !viewedJobPending) return
    const intervalId = window.setInterval(() => {
      void refreshStatus(viewedJobRef.current)
    }, 1500)
    return () => window.clearInterval(intervalId)
  }, [serverActiveJobId, viewedJobPending, viewedJobId, refreshStatus])

  React.useEffect(() => {
    if (!reportJobId) return
    const controller = new AbortController()
    void getRLEvaluationReport(reportJobId, controller.signal).then((report) => {
      if (!controller.signal.aborted) setEvaluation({ jobId: reportJobId, report })
    }).catch((error) => {
      if (!controller.signal.aborted) setEvaluation({ jobId: reportJobId, error: rlErrorMessage(error, "Unable to load evaluation results.") })
    })
    return () => controller.abort()
  }, [reportJobId])

  function toggleAlgorithm(algorithm: AlgorithmId, checked: boolean) {
    setAlgorithms((current) => {
      if (checked) {
        return current.includes(algorithm) ? current : [...current, algorithm]
      }
      return current.filter((item) => item !== algorithm)
    })
  }

  function validateSettings(values: RLTrainingSettings, queue: AlgorithmId[] = algorithms) {
    if (!values.scenario_id || !scenarioConfig || scenarioLoading) return "Select a saved scenario and wait for its settings to load."
    if (!values.evaluation_scenario_id || values.evaluation_scenario_id === values.scenario_id) return "Choose a different saved scenario for held-out evaluation."
    if (!evaluatingModel && !queue.length) return "Select at least one algorithm."
    const ranges: Array<[string, number, number, number, boolean]> = [
      ["Episodes", values.episodes, 1, 100000, true],
      ["Warmup seconds", values.warmup_seconds, 0, 86400, false],
      ["Evaluation seconds", values.evaluation_seconds, 0.1, 86400, false],
      ["Decision interval", values.decision_interval_seconds, 0.1, 60, false],
      ["Minimum green hold", values.minimum_green_hold_seconds, 5, 60, false],
      ["Checkpoint every", values.checkpoint_every, 0, 100000, true],
    ]
    for (const [label, value, min, max, integer] of ranges) {
      if (!Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) {
        return `${label} must be ${integer ? "a whole number" : "a number"} from ${min} to ${max}.`
      }
    }
    if (values.warmup_seconds + values.evaluation_seconds > 86400) return "Warmup and evaluation together must not exceed 86400 seconds."
    if (values.decision_interval_seconds > values.evaluation_seconds) return "Decision interval must not exceed evaluation seconds."
    if (![values.warmup_seconds, values.evaluation_seconds, values.decision_interval_seconds].every((value) => Math.abs(value * 10 - Math.round(value * 10)) < 1e-7)) return "Time settings must use 0.1-second increments."
    const seeds = values.seeds.split(",").map((value) => value.trim())
    if (seeds.length > 100 || seeds.some((value) => !/^\d+$/.test(value) || Number(value) > 4294967295)) return "Enter 1–100 comma-separated non-negative seeds."
    const evaluationSeeds = values.evaluation_seeds.split(",").map((value) => value.trim())
    if (evaluationSeeds.length > 100 || evaluationSeeds.some((value) => !/^\d+$/.test(value) || Number(value) > 4294967295)) return "Enter 1–100 held-out evaluation seeds."
    if (evaluationSeeds.some((value) => seeds.includes(value))) return "Training and held-out evaluation seeds must not overlap."
    if (values.resume_model_id && queue.length !== 1) return "Resume one matching algorithm at a time."
    return null
  }

  async function startTraining(values: RLTrainingSettings = settings, queue: AlgorithmId[] = algorithms) {
    if (!canRunTraining || pendingAction || serverActiveJobId) return
    const validationError = validateSettings(values, queue)
    if (validationError) { setAlert(validationError); return }
    setPendingAction(true)
    try {
      const response = await startRLTrainingJob({
        algorithms: queue,
        settings: values,
        advanced,
      })
      viewJob(response.job_id)
      setAlert("")
      toast.success(response.message)
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to start RL training."))
    } finally {
      setPendingAction(false)
    }
  }

  async function stopTraining() {
    if (!canRunTraining || !serverActiveJobId || pendingAction) return
    setPendingAction(true)
    try {
      const response = await stopRLTrainingJob(serverActiveJobId)
      setAlert("")
      toast.success(response.message)
      viewJob(serverActiveJobId)
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to stop RL training."))
    } finally {
      setPendingAction(false)
    }
  }

  function chooseScenario(id: string) {
    const scenarioId = Number(id) || null
    const junction = scenarios.find((item) => item.id === scenarioId)?.engine_config?.controlled_junction
    const compatibleHoldout = (item: ApiScenario) => item.id !== scenarioId
      && (!junction || !item.engine_config?.controlled_junction || item.engine_config.controlled_junction === junction)
    setSelectedScenarioId(id)
    setSettings((current) => ({ ...current, scenario_id: scenarioId,
      evaluation_scenario_id: scenarios.find((item) => item.id === current.evaluation_scenario_id && compatibleHoldout(item))?.id
        ?? scenarios.find(compatibleHoldout)?.id ?? null }))
  }

  function openModelAction(model: RLModelRecord, action: ModelAction) {
    setSelectedModelId(model.id)
    setSelectedCheckpointId(model.compatible ? null : model.checkpoints.find((item) => item.compatible)?.id ?? null)
    setModelAction(action)
    setAlert("")
    if (scenarioConfig?.controlled_junction !== model.controlled_junction) {
      const matchingScenario = scenarios.find((item) => item.engine_config?.controlled_junction === model.controlled_junction)
      if (matchingScenario) chooseScenario(String(matchingScenario.id))
    }
    setTab("train")
  }

  function resumeSelectedModel() {
    const checkpoint = selectedModel?.checkpoints.find((item) => item.id === selectedCheckpointId)
    if (!selectedModelMatchesScenario) { setAlert("This model controls a different junction. Choose its matching scenario or train a new model."); return }
    if (!selectedModel || (checkpoint ? !checkpoint.compatible : !selectedModel.compatible)) {
      setAlert(checkpoint?.compatibility_message ?? selectedModel?.compatibility_message ?? "Select a compatible registered model.")
      return
    }
    const algorithm = selectedModel.algorithm.toLowerCase() as AlgorithmId
    if (!algorithmOptions.some((option) => option.value === algorithm)) { setAlert("Unknown model algorithm."); return }
    void startTraining({
      ...settings,
      resume_model_id: selectedModel.id,
      resume_checkpoint_id: checkpoint?.id ?? null,
      decision_interval_seconds: selectedModel.decision_interval_seconds,
      minimum_green_hold_seconds: selectedModel.minimum_green_hold_seconds,
    }, [algorithm])
  }

  async function evaluateSelectedModel() {
    if (!canRunTraining) return
    if (!selectedModelMatchesScenario) { setAlert("This model controls a different junction. Choose its matching scenario or train a new model."); return }
    if (!selectedModel?.compatible || pendingAction || serverActiveJobId) { setAlert(selectedModel?.compatibility_message ?? "Select a compatible trained model."); return }
    const evaluationSettings = { ...settings, resume_model_id: null, resume_checkpoint_id: null, decision_interval_seconds: selectedModel.decision_interval_seconds, minimum_green_hold_seconds: selectedModel.minimum_green_hold_seconds }
    const validationError = validateSettings(evaluationSettings)
    if (validationError) { setAlert(validationError); return }
    setPendingAction(true)
    try {
      const response = await evaluateRLModel({ model_id: selectedModel.id, settings: evaluationSettings })
      viewJob(response.job_id)
      setAlert("")
      toast.success(response.message)
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to evaluate selected model."))
    } finally {
      setPendingAction(false)
    }
  }

  function clearModelAction() {
    setModelAction(null)
    setSelectedModelId(null)
    setSelectedCheckpointId(null)
    setAlert("")
  }

  function useShortWorkflowCheck() {
    setSettings((current) => ({ ...current, episodes: 2, seeds: "11", evaluation_seeds: "101",
      warmup_seconds: 0, evaluation_seconds: 20, decision_interval_seconds: 1, minimum_green_hold_seconds: 5, checkpoint_every: 1 }))
    setAdvanced({ ql: defaultAdvanced.ql, dql: { learning_starts: 4, buffer_size: 100, batch_size: 4 },
      ppo: { n_steps: 8, batch_size: 4, n_epochs: 1 } })
    setAlert("Short workflow check selected. Use its results to verify the workflow.")
  }

  const configuredAlgorithms = selectedModel && modelAction ? [selectedModel.algorithm] : algorithms
  const reportState = evaluation?.jobId === reportJobId ? evaluation : null
  const activeConsoleJob = viewedJob && viewedJob.id === serverActiveJobId ? viewedJob : null
  const modelTargetReady = !modelAction || (selectedModelMatchesScenario && (evaluatingModel
    ? selectedModel?.compatible : resumeTargetCompatible(selectedModel, selectedCheckpointId)))
  const trainTitle = evaluatingModel ? "Evaluate model" : resumingModel ? "Resume training" : "Training configuration"
  const submitLabel = evaluatingModel ? "Start evaluation" : resumingModel ? "Resume training" : "Start training"
  const metrics = [
    { label: "Saved models", value: shownModels.length, detail: "Available to evaluate or resume", icon: DatabaseIcon, tone: "blue" },
    { label: "Worker", value: serverActiveJobId ? "Active" : "Idle", detail: serverActiveJobId ? `Job #${serverActiveJobId}` : "Ready for a job", icon: ListChecksIcon, tone: "green" },
    { label: "Job progress", value: viewedJob ? `${compactNumber(viewedJob.progress_percent)}%` : EMPTY_VALUE,
      detail: viewedJob ? `Job #${viewedJob.id}` : "No job selected", icon: GaugeIcon, tone: "violet" },
    { label: "Latest reward", value: viewedJob ? compactNumber(activeItem?.latest_reward, 3) : EMPTY_VALUE,
      detail: viewedJob && activeItem ? `Job #${viewedJob.id} · ${activeItem.algorithm.toUpperCase()}` : "Latest training episode", icon: ChartLineIcon, tone: "blue" },
  ]

  return (
    <main className="smartflow-page rl-training-page">
      <header className="rl-training-hero">
        <div>
          <h1>RL Training</h1>
          <p>Train and evaluate traffic signal controllers using QL, DQL, and PPO.</p>
          {!canRunTraining && <p>Training is read-only for your role.</p>}
        </div>
        <Button variant="outline" onClick={() => void refreshStatus(viewedJobId)} disabled={isLoading}>
          <RefreshCcwIcon data-icon="inline-start" /> Refresh
        </Button>
      </header>

      <dl className="rl-kpis" aria-label="RL training summary">
        {metrics.map(({ label, value, detail, icon: Icon, tone }) => (
          <div className="rl-kpi" data-tone={tone} key={label}>
            <Icon aria-hidden="true" />
            <div>
              <div className="rl-kpi-heading"><dt>{label}</dt><dd>{value}</dd></div>
              <span>{detail}</span>
            </div>
          </div>
        ))}
      </dl>

      {alert && <Alert><AlertDescription>{alert}</AlertDescription></Alert>}

      <Tabs value={selectedTab} onValueChange={(value) => { setTab(value as TrainingTab); setAlert("") }}>
        <TabsList variant="line" className="rl-tabs" aria-label="RL training views">
          <TabsTrigger value="models"><DatabaseIcon /> Models</TabsTrigger>
          <TabsTrigger value="train"><PlayIcon /> Train</TabsTrigger>
          <TabsTrigger value="jobs"><ListChecksIcon /> Jobs{serverActiveJobId ? " · Active" : ""}</TabsTrigger>
        </TabsList>

        <TabsContent value="models">
          <Card>
            <CardHeader className="rl-models-header">
              <CardTitle>Saved models</CardTitle>
              <CardDescription>Evaluate a model on a held-out scenario or resume from a compatible artifact.</CardDescription>
              {import.meta.env.VITE_SMARTFLOW_DESKTOP === "1" && isAdmin && (
                <CardAction><DesktopModelImport onImported={() => void refreshStatus(viewedJobId)} /></CardAction>
              )}
            </CardHeader>
            <CardContent className="rl-models">
              {!shownModels.length && <Empty>
                <EmptyHeader>
                  <EmptyTitle>No compatible models yet</EmptyTitle>
                  <EmptyDescription>Saved models will appear here after training.</EmptyDescription>
                </EmptyHeader>
                {canRunTraining && <Button onClick={() => { clearModelAction(); setTab("train") }}>Configure training</Button>}
              </Empty>}
              {shownModels.map((model) => (
                <div key={model.id} className="rl-model-row">
                  <div className="min-w-0">
                    <div className="rl-action-row">
                      <Badge variant="outline" className="rl-model-tag" data-algorithm={model.algorithm.toLowerCase()}>{model.algorithm.toUpperCase()}</Badge>
                      <Badge variant="outline" className="rl-model-tag" data-tone={model.compatible ? "green" : "amber"}>{model.compatible ? "Compatible" : "Checkpoint available"}</Badge>
                    </div>
                    <p className="rl-model-name">{model.name ?? `Model #${model.id}`}</p>
                    <p className="text-muted-foreground">{model.controlled_junction === "tagum_site_a_j" ? "Site A"
                      : model.controlled_junction === "tagum_site_b_j" ? "Site B" : model.controlled_junction ?? "Junction unknown"} · {formatServerDate(model.training_date)}</p>
                    <p className="text-muted-foreground">{model.best_evaluation_score == null ? "No evaluation score" : `Recorded mean stopped wait ${compactNumber(Math.abs(model.best_evaluation_score), 3)} s`}</p>
                  </div>
                  {canRunTraining && <div className="rl-action-row">
                    <Button size="sm" variant="outline" className="rl-model-action" data-tone="blue" aria-label={`Evaluate model #${model.id}`} onClick={() => openModelAction(model, "evaluate")} disabled={!model.compatible}>
                      <ChartLineIcon data-icon="inline-start" /> Evaluate
                    </Button>
                    <Button size="sm" variant="outline" className="rl-model-action" data-tone="violet" aria-label={`Resume model #${model.id}`} onClick={() => openModelAction(model, "resume")}>
                      <RotateCcwIcon data-icon="inline-start" /> Resume
                    </Button>
                  </div>}
                </div>
              ))}
              {shownModels.some((model) => model.best_evaluation_score != null) && <p className="text-muted-foreground">Compare stopped wait across matching inputs and measurement definitions. Historical scores may lack coverage information.</p>}
              {hiddenModelCount > 0 && <p className="text-muted-foreground">{hiddenModelCount} older {hiddenModelCount === 1 ? "model requires" : "models require"} an earlier controller contract.</p>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="train">
          <div className="rl-training-grid rl-train-grid">
            <Card>
              <CardHeader>
                <CardTitle className="rl-card-title"><PlayIcon /> {trainTitle}</CardTitle>
                <CardDescription>{selectedModel && modelAction ? selectedModel.name ?? `Model #${selectedModel.id}`
                  : "Choose algorithms and a saved scenario. Training controls one junction."}</CardDescription>
                {modelAction && <CardAction><Button size="sm" variant="ghost" onClick={clearModelAction}>New training</Button></CardAction>}
              </CardHeader>
              <CardContent className="rl-form-stack">
                {!modelAction && <fieldset className="rl-form-stack">
                  <legend className="mb-2 font-medium">Algorithms</legend>
                  <div className="rl-action-row">
                    {algorithmOptions.map((option) => (
                      <label key={option.value} className="rl-checkbox-card">
                        <Checkbox checked={algorithms.includes(option.value)} onCheckedChange={(checked) => toggleAlgorithm(option.value, Boolean(checked))} />
                        {option.label}
                      </label>
                    ))}
                  </div>
                </fieldset>}

                <FieldGroup className="rl-scenario-grid">
                  <Field>
                    <FieldLabel htmlFor="rl-scenario">{evaluatingModel ? "Reference scenario" : "Training scenario"}</FieldLabel>
                    <ScenarioSelect id="rl-scenario" scenarios={scenarios} selectedScenarioId={selectedScenarioId} onChange={chooseScenario} />
                    <FieldDescription>{scenarioLoading ? "Loading saved settings…" : scenarioConfig && selectedScenario
                      ? `${scenarioConfig.controlled_junction ?? selectedScenario.network_id} · ${String(scenarioConfig.demand_source?.kind ?? "synthetic").replaceAll("_", " ")} demand`
                      : "Choose a saved scenario."}</FieldDescription>
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="rl-holdout">Held-out evaluation scenario</FieldLabel>
                    <ScenarioSelect id="rl-holdout" scenarios={evaluationScenarios} selectedScenarioId={String(settings.evaluation_scenario_id ?? "")}
                      onChange={(id) => setSettings((current) => ({ ...current, evaluation_scenario_id: Number(id) || null }))} />
                    <FieldDescription>Choose a different scenario with the same controlled junction.</FieldDescription>
                  </Field>
                  {!evaluatingModel && <NumberField label="Episodes per algorithm" min={1} max={100000} value={settings.episodes} onChange={(episodes) => setSettings({ ...settings, episodes })} />}
                  {resumingModel && selectedModel && <Field>
                    <FieldLabel htmlFor="rl-checkpoint">Resume from</FieldLabel>
                    <select className="rl-native-select" id="rl-checkpoint" value={selectedCheckpointId ?? ""}
                      onChange={(event) => setSelectedCheckpointId(event.target.value ? Number(event.target.value) : null)}>
                      <option value="" disabled={!selectedModel.compatible}>Final model artifact</option>
                      {selectedModel.checkpoints.map((checkpoint) => <option key={checkpoint.id} value={checkpoint.id} disabled={!checkpoint.compatible}>
                        Checkpoint #{checkpoint.id} · episode {checkpoint.episode}
                      </option>)}
                    </select>
                    <FieldDescription>Saved learning parameters may be retained.</FieldDescription>
                  </Field>}
                </FieldGroup>

                <Collapsible className="rl-advanced">
                  <CollapsibleTrigger render={<Button className="w-full justify-between" variant="outline" />}>
                    Advanced settings <ChevronDownIcon />
                  </CollapsibleTrigger>
                  <CollapsibleContent className="rl-form-stack pt-4">
                    <FieldGroup className="rl-scenario-grid">
                      <Field>
                        <FieldLabel htmlFor="rl-seeds">Training seeds</FieldLabel>
                        <Input id="rl-seeds" value={settings.seeds} onChange={(event) => setSettings({ ...settings, seeds: event.target.value })} />
                        <FieldDescription>Comma-separated non-negative integers.</FieldDescription>
                      </Field>
                      <Field>
                        <FieldLabel htmlFor="rl-evaluation-seeds">Held-out evaluation seeds</FieldLabel>
                        <Input id="rl-evaluation-seeds" value={settings.evaluation_seeds} onChange={(event) => setSettings({ ...settings, evaluation_seeds: event.target.value })} />
                        <FieldDescription>Use seeds distinct from training.</FieldDescription>
                      </Field>
                    </FieldGroup>
                    <FieldGroup className="rl-number-grid">
                      <NumberField label="Warm-up (s)" min={0} max={86400} step={0.1} value={settings.warmup_seconds} onChange={(warmup_seconds) => setSettings({ ...settings, warmup_seconds })} />
                      <NumberField label="Evaluation (s)" min={0.1} max={86400} step={0.1} value={settings.evaluation_seconds} onChange={(evaluation_seconds) => setSettings({ ...settings, evaluation_seconds })} />
                      {!modelAction && <>
                        <NumberField label="Decision interval (s)" min={0.1} max={60} step={0.1} value={settings.decision_interval_seconds} onChange={(decision_interval_seconds) => setSettings({ ...settings, decision_interval_seconds })} />
                        <NumberField label="Minimum green hold (s)" min={5} max={60} step={0.1} value={settings.minimum_green_hold_seconds} onChange={(minimum_green_hold_seconds) => setSettings({ ...settings, minimum_green_hold_seconds })} />
                      </>}
                      {!evaluatingModel && <NumberField label="Checkpoint interval (episodes)" min={0} max={100000} value={settings.checkpoint_every} onChange={(checkpoint_every) => setSettings({ ...settings, checkpoint_every })} />}
                    </FieldGroup>
                    {!modelAction && algorithms.map((algorithm) => (
                      <fieldset className="rl-parameter-group" key={algorithm}>
                        <legend>{algorithm.toUpperCase()} parameters</legend>
                        <FieldGroup className="rl-number-grid">
                          {Object.entries(advanced[algorithm]).map(([key, value]) => (
                            <NumberField key={key} label={key.replaceAll("_", " ")} value={value} step={algorithm === "ql" ? 0.01 : 1}
                              onChange={(next) => setAdvanced((current) => ({ ...current, [algorithm]: { ...current[algorithm], [key]: next } }))} />
                          ))}
                        </FieldGroup>
                      </fieldset>
                    ))}
                    {!modelAction && <Button className="self-start" variant="outline" onClick={useShortWorkflowCheck}>Use short workflow check</Button>}
                  </CollapsibleContent>
                </Collapsible>

                <div className="rl-review">
                  <p className="font-medium">{selectedAlgorithmLabel(configuredAlgorithms)}{!evaluatingModel && ` · ${settings.episodes.toLocaleString()} episodes per algorithm`}</p>
                  <p className="text-muted-foreground">{evaluationScenario?.name ?? "Choose a held-out scenario"} · Evaluation seeds {settings.evaluation_seeds || EMPTY_VALUE}</p>
                  <p className="text-muted-foreground">Compare against fixed-time and no-signal control. Results apply to the saved scenario inputs.</p>
                </div>
                {modelAction && scenarioConfig && !selectedModelMatchesScenario && <p role="status">Choose a reference scenario for the model’s controlled junction.</p>}
                {serverActiveJobId && <Button className="self-start" variant="outline" onClick={() => viewJob(serverActiveJobId)}>Open active job #{serverActiveJobId}</Button>}
                <Button className="self-start" disabled={!canSubmit || !modelTargetReady}
                  onClick={() => evaluatingModel ? void evaluateSelectedModel() : resumingModel ? resumeSelectedModel() : void startTraining()}>
                  <PlayIcon data-icon="inline-start" /> {pendingAction ? "Submitting…" : submitLabel}
                </Button>
              </CardContent>
            </Card>
            <JobConsole job={activeConsoleJob} lines={activeConsoleJob ? status.log_lines : []} />
          </div>
        </TabsContent>

        <TabsContent value="jobs" className="rl-form-stack">
          {!jobs.length && !viewedJob ? <Card><CardContent>
            <Empty>
              <EmptyHeader><EmptyTitle>No jobs yet</EmptyTitle><EmptyDescription>Start training or evaluate a saved model to see job progress here.</EmptyDescription></EmptyHeader>
            </Empty>
          </CardContent></Card> : <>
            {viewedJob && <>
              <Card>
                <CardHeader>
                  <CardTitle>Job #{viewedJob.id} · {selectedAlgorithmLabel(viewedJob.selected_algorithms)}</CardTitle>
                  <CardDescription>{viewedJob.message}</CardDescription>
                  <CardAction><StatusBadge status={viewedJob.status} /></CardAction>
                </CardHeader>
                <CardContent className="rl-form-stack">
                  <dl className="rl-job-metrics">
                    <div><dt>Stage</dt><dd className="capitalize">{viewedJob.status === "running" && viewedJob.current_algorithm
                      ? viewedJob.current_algorithm === "evaluation" ? "Evaluation" : viewedJob.current_algorithm.toUpperCase()
                      : statusLabel(viewedJob.status)}</dd></div>
                    <div><dt>Episode</dt><dd>{activeItem?.latest_episode || EMPTY_VALUE}</dd></div>
                    <div><dt>Elapsed</dt><dd>{elapsedTime(viewedJob)}</dd></div>
                    <div><dt>Job progress</dt><dd>{compactNumber(viewedJob.progress_percent)}%</dd></div>
                  </dl>
                  <ProgressBar value={viewedJob.progress_percent} />
                  {canStopActiveJob && serverActiveJobId === viewedJob.id && <Button className="self-start" variant="destructive" disabled={pendingAction} onClick={stopTraining}>
                    <SquareIcon data-icon="inline-start" /> Stop active job
                  </Button>}
                  {status.items.length > 0 && <ul className="rl-job-items" aria-label="Algorithms in this job">
                    {status.items.map((item: RLTrainingJobItem) => <li key={item.id}>
                      <strong>{item.algorithm.toUpperCase()}</strong> <StatusBadge status={item.status} />
                      {["error", "interrupted"].includes(item.status) && item.message && <span>{item.message}</span>}
                    </li>)}
                  </ul>}
                </CardContent>
              </Card>
            </>}
            {!viewedJob && <p role="status">Loading job details…</p>}
            <div className="rl-training-grid">
              <JobConsole job={viewedJob} lines={viewedJob ? status.log_lines : []} />
              <Card>
                <CardHeader><CardTitle>Recent jobs</CardTitle></CardHeader>
                <CardContent>
                  <ul className="rl-job-list">
                    {jobs.map((job) => <li key={job.id}>
                      <Button className="w-full justify-between" variant={viewedJob?.id === job.id ? "secondary" : "ghost"}
                        aria-current={viewedJob?.id === job.id ? "true" : undefined} onClick={() => viewJob(job.id)}>
                        <span>#{job.id} · {selectedAlgorithmLabel(job.selected_algorithms)}</span>
                        <span className="rl-action-row"><span className="rl-job-date">{formatServerDate(job.created_at)}</span><StatusBadge status={job.status} /></span>
                      </Button>
                    </li>)}
                  </ul>
                </CardContent>
              </Card>
            </div>
            {viewedJob && rewardChart.data.length > 0 && <Card>
              <CardHeader><CardTitle className="rl-card-title"><ChartLineIcon /> Recent training rewards</CardTitle></CardHeader>
              <CardContent className="rl-chart-shell">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={rewardChart.data}>
                    <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="episode" /><YAxis /><Tooltip /><Legend />
                    {rewardChart.algorithms.map((algorithm, index) => <Line key={algorithm} type="monotone" dataKey={algorithm}
                      stroke={`var(--chart-${(index % 5) + 1})`} dot={false} connectNulls isAnimationActive={false} />)}
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>}
            {reportJobId && (reportState?.report ? <EvaluationResults jobId={reportJobId} report={reportState.report} />
              : <p role="status">{reportState?.error ?? "Loading evaluation results…"}</p>)}
          </>}
        </TabsContent>
      </Tabs>
    </main>
  )
}

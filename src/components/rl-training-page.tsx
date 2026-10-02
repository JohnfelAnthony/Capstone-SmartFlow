import * as React from "react"
import {
  BrainIcon,
  ChartLineIcon,
  DatabaseIcon,
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
  getRLTrainingStatus,
  listRLTrainingJobs,
  startRLTrainingJob,
  stopRLTrainingJob,
  type RLAdvancedSettings,
  type RLLogLine,
  type RLModelRecord,
  type RLTrainingJob,
  type RLTrainingJobItem,
  type RLTrainingSettings,
  type RLTrainingStatusResponse,
} from "@/api/rl"
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
import { Input } from "@/components/ui/input"
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
import { cn } from "@/lib/utils"
import "@/styles/rl-training.css"

type AlgorithmId = "ql" | "dql" | "ppo"

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

const defaultSettings: RLTrainingSettings = {
  scenario_id: null,
  evaluation_scenario_id: null,
  episodes: 150,
  seeds: "11,22,33,44,55",
  evaluation_seeds: "101,102,103,104,105",
  warmup_seconds: 20,
  evaluation_seconds: 300,
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

function formatDate(value: string | null) {
  if (!value) {
    return "Never"
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value))
}

function statusLabel(value: string | null | undefined) {
  return String(value || "idle").replaceAll("_", " ").replaceAll("-", " ")
}

function selectedAlgorithmLabel(algorithms: string[]) {
  if (!algorithms.length) {
    return "--"
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
    return "--"
  }
  return value.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })
}

function ScenarioSelect({
  scenarios,
  selectedScenarioId,
  onChange,
}: {
  scenarios: ApiScenario[]
  selectedScenarioId: string
  onChange: (value: string) => void
}) {
  return (
    <Select value={selectedScenarioId} onValueChange={(value) => value !== null && onChange(value)}>
      <SelectTrigger className="w-full">
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
  const isDone = normalized === "completed"
  return (
    <Badge
      variant={isDanger ? "destructive" : isDone ? "secondary" : "outline"}
      className={cn("rl-status-badge", normalized)}
    >
      {statusLabel(status)}
    </Badge>
  )
}

function ProgressBar({ value }: { value: number }) {
  const boundedValue = Math.max(0, Math.min(100, value || 0))
  return (
    <div className="rl-progress" aria-label={`Progress ${boundedValue.toFixed(1)} percent`}>
      <span style={{ width: `${boundedValue}%` }} />
    </div>
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
  const [alert, setAlert] = React.useState("RL training console loaded.")
  const [isLoading, setIsLoading] = React.useState(false)
  const [pendingAction, setPendingAction] = React.useState(false)
  const requestId = React.useRef(0)
  const viewedJobRef = React.useRef<number | null>(null)
  const inFlightRefreshes = React.useRef<Set<number | null>>(new Set())

  const scenarioConfig = scenarioResolution?.id === selectedScenarioId ? scenarioResolution.config : null
  const scenarioLoading = Boolean(selectedScenarioId && scenarioResolution?.id !== selectedScenarioId)
  const selectedModel = status.models.find((model) => model.id === selectedModelId) ?? null
  const selectedModelMatchesScenario = Boolean(selectedModel && scenarioConfig && selectedModel.controlled_junction === scenarioConfig.controlled_junction)
  const viewedJob = status.job
  const serverActiveJobId = status.active_job_id
  const activeJob = jobs.find((job) => job.id === serverActiveJobId)
  const canStopActiveJob = Boolean(canRunTraining && serverActiveJobId && (isAdmin || activeJob?.user_id === currentUserId))
  const selectedScenario = scenarios.find((item) => String(item.id) === selectedScenarioId) ?? null
  const activeItem = status.items.find((item) => item.id === viewedJob?.current_item_id) ?? status.items[0] ?? null
  const rewardPoints = React.useMemo(() => parseRewardPoints(status.log_lines), [status.log_lines])
  const consoleText = status.log_lines.length
    ? status.log_lines.slice(-140).map((line) => line.text).join("\n")
    : "No training output yet."

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
  }, [])

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
    if (!serverActiveJobId) return
    const intervalId = window.setInterval(() => {
      void refreshStatus(viewedJobRef.current)
    }, 1500)
    return () => window.clearInterval(intervalId)
  }, [serverActiveJobId, viewedJobId, refreshStatus])

  function toggleAlgorithm(algorithm: AlgorithmId, checked: boolean) {
    setAlgorithms((current) => {
      if (checked) {
        return current.includes(algorithm) ? current : [...current, algorithm]
      }
      return current.filter((item) => item !== algorithm)
    })
  }

  function validateSettings(values: RLTrainingSettings = settings) {
    if (!values.scenario_id || !scenarioConfig || scenarioLoading) return "Select a saved scenario and wait for its settings to load."
    if (!values.evaluation_scenario_id || values.evaluation_scenario_id === values.scenario_id) return "Choose a different saved scenario for held-out evaluation."
    if (!algorithms.length) return "Select at least one algorithm."
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
    if (values.resume_model_id && algorithms.length !== 1) return "Resume one matching algorithm at a time."
    return null
  }

  async function startTraining() {
    if (!canRunTraining || pendingAction || serverActiveJobId) return
    const validationError = validateSettings()
    if (validationError) { setAlert(validationError); return }
    setPendingAction(true)
    try {
      const response = await startRLTrainingJob({
        algorithms,
        settings,
        advanced,
      })
      viewJob(response.job_id)
      setAlert(response.message)
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
      setAlert(response.message)
      viewJob(serverActiveJobId)
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to stop RL training."))
    } finally {
      setPendingAction(false)
    }
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
    setSettings((current) => ({
      ...current,
      resume_model_id: selectedModel.id,
      resume_checkpoint_id: checkpoint?.id ?? null,
      decision_interval_seconds: selectedModel.decision_interval_seconds,
      minimum_green_hold_seconds: selectedModel.minimum_green_hold_seconds,
    }))
    setAlgorithms([algorithm])
    setAlert(`Resume ${algorithm.toUpperCase()} from registered ${checkpoint ? `checkpoint #${checkpoint.id}` : `model #${selectedModel.id}`}. Saved learning parameters may be retained by the artifact.`)
  }

  async function evaluateSelectedModel() {
    if (!canRunTraining) return
    if (!selectedModelMatchesScenario) { setAlert("This model controls a different junction. Choose its matching scenario or train a new model."); return }
    if (!selectedModel?.compatible || pendingAction || serverActiveJobId) { setAlert(selectedModel?.compatibility_message ?? "Select a compatible trained model."); return }
    const evaluationSettings = { ...settings, resume_model_id: null, resume_checkpoint_id: null, decision_interval_seconds: selectedModel.decision_interval_seconds, minimum_green_hold_seconds: selectedModel.minimum_green_hold_seconds }
    const validationError = validateSettings(evaluationSettings)
    if (validationError) { setAlert(validationError); return }
    setSettings(evaluationSettings)
    setPendingAction(true)
    try {
      const response = await evaluateRLModel({ model_id: selectedModel.id, settings: evaluationSettings })
      viewJob(response.job_id)
      setAlert(response.message)
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to evaluate selected model."))
    } finally {
      setPendingAction(false)
    }
  }

  const metrics = [
    { label: "Job", value: statusLabel(viewedJob?.status), hint: viewedJob?.message ?? "Idle", icon: ListChecksIcon, tone: "info" },
    { label: "Algorithm", value: (viewedJob?.current_algorithm ?? activeItem?.algorithm ?? selectedAlgorithmLabel(algorithms)).toUpperCase(), hint: "Viewed job", icon: BrainIcon, tone: "success" },
    { label: "Progress", value: `${compactNumber(viewedJob?.progress_percent ?? 0)}%`, hint: "Viewed job", icon: GaugeIcon, tone: "warning" },
    { label: "Reward", value: compactNumber(activeItem?.latest_reward, 3), hint: "Latest episode", icon: ChartLineIcon, tone: "purple" },
  ]

  return (
    <main className="smartflow-page rl-training-page">
      <section className="rl-training-hero">
        <div>
          <h1>RL Training</h1>
          <p>Queue QL, DQL, and PPO training jobs, evaluate saved models, and monitor live output.</p>
          {!canRunTraining && <p>Training is read-only for your role. An administrator can grant the RL training run permission.</p>}
        </div>
        <div className="rl-hero-actions">
          <Button variant="outline" onClick={() => void refreshStatus(viewedJobId)} disabled={isLoading}>
            <RefreshCcwIcon data-icon="inline-start" />
            Refresh
          </Button>
          <Button onClick={startTraining} disabled={!canRunTraining || Boolean(serverActiveJobId) || pendingAction || scenarioLoading}>
            <PlayIcon data-icon="inline-start" />
            Start Queue
          </Button>
          <Button variant="destructive" onClick={stopTraining} disabled={!canStopActiveJob || pendingAction}>
            <SquareIcon data-icon="inline-start" />
            Stop active job
          </Button>
        </div>
      </section>

      <section className="rl-metric-strip" aria-label="RL training metrics">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div key={metric.label} className={cn("rl-strip-metric", metric.tone)}>
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

      <Alert>
        <BrainIcon />
        <AlertDescription>{alert}</AlertDescription>
      </Alert>
      <p role="status" className="text-sm text-muted-foreground">Viewing {viewedJob ? `job #${viewedJob.id}` : "latest job"}.
        {serverActiveJobId ? ` Active worker: job #${serverActiveJobId}, owner user #${activeJob?.user_id ?? "unknown"}.` : " No active worker."}
        {viewedJob?.id && serverActiveJobId !== viewedJob.id ? " The viewed job is historical." : ""}
      </p>

      <section className="rl-training-grid">
        <Card className="rl-queue-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PlayIcon />
              Training Queue
            </CardTitle>
            <CardDescription>Train one selected junction from a complete saved scenario. Other junctions follow their saved plans. Synthetic inputs are workflow evidence, not field validation.</CardDescription>
            <CardAction>
              <Badge variant="secondary">{selectedAlgorithmLabel(algorithms)}</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="rl-form-stack">
            <div className="rl-algorithm-row">
              {algorithmOptions.map((option) => (
                <label key={option.value} className="rl-checkbox-card">
                  <Checkbox
                    checked={algorithms.includes(option.value)}
                    onCheckedChange={(checked) => toggleAlgorithm(option.value, Boolean(checked))}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>

            <FieldGroup className="rl-form-grid">
              <Field className="rl-field-wide">
                <FieldLabel>Saved scenario</FieldLabel>
                <ScenarioSelect scenarios={scenarios} selectedScenarioId={selectedScenarioId} onChange={(id) => {
                  setSelectedScenarioId(id)
                  setSettings((current) => ({ ...current, scenario_id: Number(id) || null,
                    evaluation_scenario_id: current.evaluation_scenario_id === Number(id)
                      ? scenarios.find((scenario) => scenario.id !== Number(id))?.id ?? null
                      : current.evaluation_scenario_id }))
                }} />
                <FieldDescription>{scenarioLoading ? "Loading saved configuration…" : selectedScenario && scenarioConfig ? `${selectedScenario.name} · junction ${String(scenarioConfig.controlled_junction ?? selectedScenario.intersection_id)} · ${String(scenarioConfig.demand_source?.kind ?? "synthetic")} demand · ${scenarioConfig.events?.length ?? 0} timed road events` : "Choose an available scenario."}</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor="rl-seeds">Training seeds</FieldLabel>
                <Input id="rl-seeds" value={settings.seeds} onChange={(event) => setSettings({ ...settings, seeds: event.target.value })} />
                <FieldDescription>Comma-separated non-negative integers.</FieldDescription>
              </Field>
              <Field className="rl-field-wide">
                <FieldLabel>Held-out evaluation scenario</FieldLabel>
                <ScenarioSelect scenarios={scenarios.filter((scenario) => scenario.id !== settings.scenario_id)} selectedScenarioId={String(settings.evaluation_scenario_id ?? "")} onChange={(id) => setSettings((current) => ({ ...current, evaluation_scenario_id: Number(id) || null }))} />
                <FieldDescription>Choose a different saved scenario for automatic and manual evaluation. Its controlled junction must match training.</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor="rl-evaluation-seeds">Held-out evaluation seeds</FieldLabel>
                <Input id="rl-evaluation-seeds" value={settings.evaluation_seeds} onChange={(event) => setSettings({ ...settings, evaluation_seeds: event.target.value })} />
                <FieldDescription>These seeds must differ from the training seeds.</FieldDescription>
              </Field>
              <NumberField label="Episodes" min={1} max={100000} value={settings.episodes} onChange={(episodes) => setSettings({ ...settings, episodes })} />
              <NumberField label="Warmup seconds" min={0} max={86400} step={0.1} value={settings.warmup_seconds} onChange={(warmup_seconds) => setSettings({ ...settings, warmup_seconds })} />
              <NumberField label="Evaluation seconds" min={0.1} max={86400} step={0.1} value={settings.evaluation_seconds} onChange={(evaluation_seconds) => setSettings({ ...settings, evaluation_seconds })} />
              <NumberField label="Decision interval seconds" min={0.1} max={60} step={0.1} value={settings.decision_interval_seconds} onChange={(decision_interval_seconds) => setSettings({ ...settings, decision_interval_seconds })} />
              <NumberField label="Minimum green hold seconds" min={5} max={60} step={0.1} value={settings.minimum_green_hold_seconds} onChange={(minimum_green_hold_seconds) => setSettings({ ...settings, minimum_green_hold_seconds })} />
              <NumberField label="Checkpoint every" min={0} max={100000} value={settings.checkpoint_every} onChange={(checkpoint_every) => setSettings({ ...settings, checkpoint_every })} />
            </FieldGroup>
            <Button variant="outline" onClick={() => {
              setSettings((current) => ({ ...current, episodes: 2, seeds: "11", evaluation_seeds: "101", warmup_seconds: 0, evaluation_seconds: 20, decision_interval_seconds: 1, minimum_green_hold_seconds: 5, checkpoint_every: 1, resume_model_id: null, resume_checkpoint_id: null }))
              setAdvanced({ ql: { ...defaultAdvanced.ql }, dql: { learning_starts: 4, buffer_size: 100, batch_size: 4 }, ppo: { n_steps: 8, batch_size: 4, n_epochs: 1 } })
              setAlert("Short workflow check selected. This trains and evaluates on separate saved scenarios and seeds.")
            }}>Use short workflow check</Button>

            <div className="rl-advanced-grid">
              <Card size="sm">
                <CardHeader>
                  <CardTitle>QL</CardTitle>
                </CardHeader>
                <CardContent className="rl-mini-grid">
                  <NumberField label="Alpha" value={advanced.ql.alpha} onChange={(alpha) => setAdvanced({ ...advanced, ql: { ...advanced.ql, alpha } })} />
                  <NumberField label="Gamma" value={advanced.ql.gamma} onChange={(gamma) => setAdvanced({ ...advanced, ql: { ...advanced.ql, gamma } })} />
                  <NumberField label="Epsilon" value={advanced.ql.epsilon} onChange={(epsilon) => setAdvanced({ ...advanced, ql: { ...advanced.ql, epsilon } })} />
                </CardContent>
              </Card>
              <Card size="sm">
                <CardHeader>
                  <CardTitle>DQL</CardTitle>
                </CardHeader>
                <CardContent className="rl-mini-grid">
                  <NumberField label="Learning Starts" value={advanced.dql.learning_starts} onChange={(learning_starts) => setAdvanced({ ...advanced, dql: { ...advanced.dql, learning_starts } })} />
                  <NumberField label="Buffer Size" value={advanced.dql.buffer_size} onChange={(buffer_size) => setAdvanced({ ...advanced, dql: { ...advanced.dql, buffer_size } })} />
                  <NumberField label="Batch Size" value={advanced.dql.batch_size} onChange={(batch_size) => setAdvanced({ ...advanced, dql: { ...advanced.dql, batch_size } })} />
                </CardContent>
              </Card>
              <Card size="sm">
                <CardHeader>
                  <CardTitle>PPO</CardTitle>
                </CardHeader>
                <CardContent className="rl-mini-grid">
                  <NumberField label="N Steps" value={advanced.ppo.n_steps} onChange={(n_steps) => setAdvanced({ ...advanced, ppo: { ...advanced.ppo, n_steps } })} />
                  <NumberField label="Batch Size" value={advanced.ppo.batch_size} onChange={(batch_size) => setAdvanced({ ...advanced, ppo: { ...advanced.ppo, batch_size } })} />
                  <NumberField label="N Epochs" value={advanced.ppo.n_epochs} onChange={(n_epochs) => setAdvanced({ ...advanced, ppo: { ...advanced.ppo, n_epochs } })} />
                </CardContent>
              </Card>
            </div>

            <div className="rl-secondary-actions">
              <Button variant="outline" onClick={() => { setSettings((current) => ({ ...current, resume_model_id: null, resume_checkpoint_id: null })); setSelectedCheckpointId(null); setAlert("New training selected.") }}>Start new training</Button>
              <Button variant="outline" onClick={resumeSelectedModel}>
                <RotateCcwIcon data-icon="inline-start" />
                Resume Selected
              </Button>
              <Button variant="outline" onClick={evaluateSelectedModel} disabled={!canRunTraining || !selectedModel?.compatible || !selectedModelMatchesScenario || Boolean(serverActiveJobId) || pendingAction}>
                <ChartLineIcon data-icon="inline-start" />
                Evaluate Selected
              </Button>
              {settings.resume_model_id ? <Badge variant="outline">Resume model #{settings.resume_model_id}{settings.resume_checkpoint_id ? ` checkpoint #${settings.resume_checkpoint_id}` : ""}</Badge> : null}
            </div>
          </CardContent>
        </Card>

        <Card className="rl-console-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TerminalIcon />
              Live Console
            </CardTitle>
            <CardDescription>{status.log_lines.length} recent log line{status.log_lines.length === 1 ? "" : "s"}</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="rl-console">{consoleText}</pre>
          </CardContent>
        </Card>

        <Card className="rl-chart-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ChartLineIcon />
              Reward Progress
            </CardTitle>
            <CardDescription>Parsed from live training output.</CardDescription>
          </CardHeader>
          <CardContent className="rl-chart-shell">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={rewardPoints}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="episode" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="reward" stroke="var(--primary)" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="rl-jobs-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListChecksIcon />
              Training Jobs
            </CardTitle>
            <CardDescription>Select a job to inspect its status and logs.</CardDescription>
            <CardAction>
              <Badge variant="secondary">{jobs.length} jobs</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="rl-table-shell">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Algorithms</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow
                    key={job.id}
                    className={cn(viewedJob?.id === job.id && "selected")}
                    onClick={() => viewJob(job.id)}
                  >
                    <TableCell>#{job.id}{serverActiveJobId === job.id ? " · active" : ""}</TableCell>
                    <TableCell><StatusBadge status={job.status} /></TableCell>
                    <TableCell>{selectedAlgorithmLabel(job.selected_algorithms)}</TableCell>
                    <TableCell>
                      <ProgressBar value={job.progress_percent} />
                    </TableCell>
                    <TableCell>{formatDate(job.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card className="rl-models-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DatabaseIcon />
              Trained Models
            </CardTitle>
            <CardDescription>Select a registered model explicitly. A checkpoint can resume even when the final artifact is missing, if that checkpoint is compatible.</CardDescription>
            <CardAction>
              <Badge variant="secondary">{status.models.length} models</Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="rl-table-shell">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Algorithm</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Best Eval</TableHead>
                  <TableHead>Trained</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {status.models.map((model: RLModelRecord) => (
                  <TableRow
                    key={model.id}
                    className={cn(selectedModel?.id === model.id && "selected")}
                    onClick={() => { setSelectedModelId(model.id); setSelectedCheckpointId(null) }}
                  >
                    <TableCell>#{model.id}</TableCell>
                    <TableCell><Badge variant="outline">{model.algorithm}</Badge></TableCell>
                    <TableCell>{model.name ?? "RL Model"} · {model.compatible ? "compatible" : model.compatibility_message}</TableCell>
                    <TableCell>{compactNumber(model.best_evaluation_score, 3)}</TableCell>
                    <TableCell>{formatDate(model.training_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {selectedModel ? (
              <div className="flex flex-col gap-2 p-3">
                <p>Model #{selectedModel.id}: {selectedModel.compatible ? "compatible artifact" : selectedModel.compatibility_message}. Junction {selectedModel.controlled_junction ?? "unknown"}; decision every {selectedModel.decision_interval_seconds}s; minimum green hold {selectedModel.minimum_green_hold_seconds}s. Status: {selectedModel.training_status ?? "unknown"}. {selectedModelMatchesScenario ? "Matches the selected scenario junction." : "Choose a scenario with this controlled junction to use this model."}</p>
                <Field>
                  <FieldLabel htmlFor="rl-checkpoint">Resume checkpoint</FieldLabel>
                  <select id="rl-checkpoint" value={selectedCheckpointId ?? ""} onChange={(event) => setSelectedCheckpointId(event.target.value ? Number(event.target.value) : null)}>
                    <option value="">Final model artifact</option>
                    {selectedModel.checkpoints.map((checkpoint) => <option key={checkpoint.id} value={checkpoint.id}>#{checkpoint.id} · episode {checkpoint.episode} · {checkpoint.compatible ? "compatible" : checkpoint.compatibility_message}</option>)}
                  </select>
                </Field>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="rl-items-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GaugeIcon />
              Job Items
            </CardTitle>
            <CardDescription>Per-algorithm execution and evaluation artifacts.</CardDescription>
          </CardHeader>
          <CardContent className="rl-table-shell">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Algorithm</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Episode</TableHead>
                  <TableHead>Reward</TableHead>
                  <TableHead>Artifact</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {status.items.map((item: RLTrainingJobItem) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.algorithm.toUpperCase()}</TableCell>
                    <TableCell><StatusBadge status={item.status} /></TableCell>
                    <TableCell>{item.latest_episode}</TableCell>
                    <TableCell>{compactNumber(item.latest_reward, 3)}</TableCell>
                    <TableCell className="rl-path-cell">{item.artifact_path ?? item.evaluation_path ?? "--"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}

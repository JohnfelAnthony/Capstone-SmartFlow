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

const trafficDensityOptions = ["low", "medium", "high", "very high"]
const pedestrianDensityOptions = ["low", "medium", "high"]
const emergencyOptions = ["disabled", "enabled"]
const roadOptions = ["None", "Constraint type", "Severity", "Lane affected"]

const defaultSettings: RLTrainingSettings = {
  episodes: 150,
  seeds: "11,22,33,44,55",
  warmup_seconds: 20,
  evaluation_seconds: 300,
  intersection_id: "tagum_1",
  traffic_density: "medium",
  pedestrian_density: "medium",
  emergency_mode: "disabled",
  road_constraint: "None",
  checkpoint_every: 25,
  resume_model: null,
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

function isActiveJob(job: RLTrainingJob | null) {
  return job ? ["queued", "running", "stopping"].includes(job.status) : false
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
        <SelectValue />
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

function OptionSelect({
  value,
  options,
  onChange,
}: {
  value: string
  options: string[]
  onChange: (value: string) => void
}) {
  return (
    <Select value={value} onValueChange={(nextValue) => nextValue !== null && onChange(nextValue)}>
      <SelectTrigger className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
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
}: {
  label: string
  value: number
  onChange: (value: number) => void
}) {
  return (
    <label className="rl-field">
      <span>{label}</span>
      <Input
        type="number"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
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

export function RLTrainingPage() {
  const [algorithms, setAlgorithms] = React.useState<AlgorithmId[]>(["ql"])
  const [settings, setSettings] = React.useState<RLTrainingSettings>(defaultSettings)
  const [advanced, setAdvanced] = React.useState<RLAdvancedSettings>(defaultAdvanced)
  const [scenarios, setScenarios] = React.useState<ApiScenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = React.useState("")
  const [activeJobId, setActiveJobId] = React.useState<number | null>(null)
  const [status, setStatus] = React.useState<RLTrainingStatusResponse>({
    job: null,
    items: [],
    log_lines: [],
    models: [],
  })
  const [jobs, setJobs] = React.useState<RLTrainingJob[]>([])
  const [selectedModelId, setSelectedModelId] = React.useState<number | null>(null)
  const [alert, setAlert] = React.useState("RL training console loaded.")
  const [isLoading, setIsLoading] = React.useState(false)

  const selectedModel = status.models.find((model) => model.id === selectedModelId) ?? status.models[0] ?? null
  const activeJob = status.job
  const activeItem = status.items.find((item) => item.id === activeJob?.current_item_id) ?? status.items[0] ?? null
  const rewardPoints = React.useMemo(() => parseRewardPoints(status.log_lines), [status.log_lines])
  const consoleText = status.log_lines.length
    ? status.log_lines.slice(-140).map((line) => line.text).join("\n")
    : "No training output yet."

  const refreshStatus = React.useCallback(async (jobId: number | null = activeJobId) => {
    setIsLoading(true)
    try {
      const [nextStatus, nextJobs] = await Promise.all([
        getRLTrainingStatus(jobId),
        listRLTrainingJobs({ limit: 30 }),
      ])
      setStatus(nextStatus)
      setJobs(nextJobs.jobs)
      setActiveJobId((current) => current ?? nextStatus.job?.id ?? null)
      setSelectedModelId((current) => current ?? nextStatus.models[0]?.id ?? null)
      setAlert("RL training status refreshed from SQLite.")
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to refresh RL training status."))
    } finally {
      setIsLoading(false)
    }
  }, [activeJobId])

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
        setStatus(statusResponse)
        setJobs(jobsResponse.jobs)
        setActiveJobId(statusResponse.job?.id ?? null)
        setSelectedModelId(statusResponse.models[0]?.id ?? null)
        setAlert("RL training data loaded from SQLite.")
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
    if (!selectedScenarioId) {
      return
    }
    const scenario = scenarios.find((item) => String(item.id) === selectedScenarioId)
    if (!scenario) {
      return
    }
    setSettings((current) => ({
      ...current,
      intersection_id: scenario.intersection_id || "tagum_1",
      traffic_density: String(scenario.traffic_density || "medium").toLowerCase(),
      pedestrian_density: String(scenario.pedestrian_density || "medium").toLowerCase(),
      emergency_mode: String(scenario.emergency_mode || "").toLowerCase().includes("enabled") ? "enabled" : "disabled",
      road_constraint: scenario.road_constraint || "None",
    }))
  }, [scenarios, selectedScenarioId])

  React.useEffect(() => {
    if (!isActiveJob(activeJob)) {
      return
    }
    const intervalId = window.setInterval(() => {
      void refreshStatus(activeJobId)
    }, 1500)
    return () => window.clearInterval(intervalId)
  }, [activeJob, activeJobId, refreshStatus])

  function toggleAlgorithm(algorithm: AlgorithmId, checked: boolean) {
    setAlgorithms((current) => {
      if (checked) {
        return current.includes(algorithm) ? current : [...current, algorithm]
      }
      return current.filter((item) => item !== algorithm)
    })
  }

  async function startTraining() {
    try {
      const response = await startRLTrainingJob({
        algorithms,
        settings,
        advanced,
      })
      setActiveJobId(response.job_id)
      setAlert(response.message)
      await refreshStatus(response.job_id)
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to start RL training."))
    }
  }

  async function stopTraining() {
    if (!activeJobId) {
      setAlert("No active RL job selected.")
      return
    }
    try {
      const response = await stopRLTrainingJob(activeJobId)
      setAlert(response.message)
      await refreshStatus(activeJobId)
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to stop RL training."))
    }
  }

  function resumeSelectedModel() {
    if (!selectedModel?.checkpoint_path) {
      setAlert("Select a trained model with a checkpoint path first.")
      return
    }
    const algorithm = selectedModel.algorithm.toLowerCase() as AlgorithmId
    setSettings((current) => ({ ...current, resume_model: selectedModel.checkpoint_path }))
    setAlgorithms([algorithm])
    setAlert(`Resume model selected: ${selectedModel.checkpoint_path}`)
  }

  async function evaluateSelectedModel() {
    if (!selectedModel) {
      setAlert("Select a trained model first.")
      return
    }
    try {
      const response = await evaluateRLModel({ model_id: selectedModel.id, settings })
      setActiveJobId(response.job_id)
      setAlert(response.message)
      await refreshStatus(response.job_id)
    } catch (error) {
      setAlert(rlErrorMessage(error, "Unable to evaluate selected model."))
    }
  }

  const metrics = [
    { label: "Queue", value: statusLabel(activeJob?.status), hint: activeJob?.message ?? "Idle", icon: ListChecksIcon, tone: "info" },
    { label: "Algorithm", value: (activeJob?.current_algorithm ?? activeItem?.algorithm ?? selectedAlgorithmLabel(algorithms)).toUpperCase(), hint: "Current selection", icon: BrainIcon, tone: "success" },
    { label: "Progress", value: `${compactNumber(activeJob?.progress_percent ?? 0)}%`, hint: "Active job", icon: GaugeIcon, tone: "warning" },
    { label: "Reward", value: compactNumber(activeItem?.latest_reward, 3), hint: "Latest episode", icon: ChartLineIcon, tone: "purple" },
  ]

  return (
    <main className="smartflow-page rl-training-page">
      <section className="rl-training-hero">
        <div>
          <h1>RL Training</h1>
          <p>Queue QL, DQL, and PPO training jobs, evaluate saved models, and monitor live output.</p>
        </div>
        <div className="rl-hero-actions">
          <Button variant="outline" onClick={() => void refreshStatus(activeJobId)} disabled={isLoading}>
            <RefreshCcwIcon data-icon="inline-start" />
            Refresh
          </Button>
          <Button onClick={startTraining} disabled={isActiveJob(activeJob)}>
            <PlayIcon data-icon="inline-start" />
            Start Queue
          </Button>
          <Button variant="destructive" onClick={stopTraining} disabled={!isActiveJob(activeJob)}>
            <SquareIcon data-icon="inline-start" />
            Stop
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

      <div className={cn("rl-notice", isActiveJob(activeJob) && "running")}>
        <BrainIcon />
        <span>{alert}</span>
      </div>

      <section className="rl-training-grid">
        <Card className="rl-queue-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PlayIcon />
              Training Queue
            </CardTitle>
            <CardDescription>Configure algorithms, scenario defaults, and run length.</CardDescription>
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

            <div className="rl-form-grid">
              <label className="rl-field rl-field-wide">
                <span>Scenario</span>
                <ScenarioSelect scenarios={scenarios} selectedScenarioId={selectedScenarioId} onChange={setSelectedScenarioId} />
              </label>
              <label className="rl-field">
                <span>Seeds</span>
                <Input value={settings.seeds} onChange={(event) => setSettings({ ...settings, seeds: event.target.value })} />
              </label>
              <NumberField label="Episodes" value={settings.episodes} onChange={(episodes) => setSettings({ ...settings, episodes })} />
              <NumberField label="Warmup Seconds" value={settings.warmup_seconds} onChange={(warmup_seconds) => setSettings({ ...settings, warmup_seconds })} />
              <NumberField label="Evaluation Seconds" value={settings.evaluation_seconds} onChange={(evaluation_seconds) => setSettings({ ...settings, evaluation_seconds })} />
              <NumberField label="Checkpoint Every" value={settings.checkpoint_every} onChange={(checkpoint_every) => setSettings({ ...settings, checkpoint_every })} />
              <label className="rl-field">
                <span>Intersection</span>
                <Input value={settings.intersection_id} onChange={(event) => setSettings({ ...settings, intersection_id: event.target.value })} />
              </label>
              <label className="rl-field">
                <span>Traffic Density</span>
                <OptionSelect value={settings.traffic_density} options={trafficDensityOptions} onChange={(traffic_density) => setSettings({ ...settings, traffic_density })} />
              </label>
              <label className="rl-field">
                <span>Pedestrian Density</span>
                <OptionSelect value={settings.pedestrian_density} options={pedestrianDensityOptions} onChange={(pedestrian_density) => setSettings({ ...settings, pedestrian_density })} />
              </label>
              <label className="rl-field">
                <span>Emergency Mode</span>
                <OptionSelect value={settings.emergency_mode} options={emergencyOptions} onChange={(emergency_mode) => setSettings({ ...settings, emergency_mode })} />
              </label>
              <label className="rl-field">
                <span>Road Constraint</span>
                <OptionSelect value={settings.road_constraint} options={roadOptions} onChange={(road_constraint) => setSettings({ ...settings, road_constraint })} />
              </label>
            </div>

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
              <Button variant="outline" onClick={resumeSelectedModel}>
                <RotateCcwIcon data-icon="inline-start" />
                Resume Selected
              </Button>
              <Button variant="outline" onClick={evaluateSelectedModel} disabled={!selectedModel}>
                <ChartLineIcon data-icon="inline-start" />
                Evaluate Selected
              </Button>
              {settings.resume_model ? <Badge variant="outline" className="rl-resume-badge">{settings.resume_model}</Badge> : null}
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
                    className={cn(activeJob?.id === job.id && "selected")}
                    onClick={() => {
                      setActiveJobId(job.id)
                      void refreshStatus(job.id)
                    }}
                  >
                    <TableCell>#{job.id}</TableCell>
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
            <CardDescription>Saved RL models available for resume or evaluation.</CardDescription>
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
                    onClick={() => setSelectedModelId(model.id)}
                  >
                    <TableCell>#{model.id}</TableCell>
                    <TableCell><Badge variant="outline">{model.algorithm}</Badge></TableCell>
                    <TableCell>{model.name ?? "RL Model"}</TableCell>
                    <TableCell>{compactNumber(model.best_evaluation_score, 3)}</TableCell>
                    <TableCell>{formatDate(model.training_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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

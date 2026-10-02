import * as React from "react"
import {
  ArchiveIcon,
  BadgeCheckIcon,
  BoltIcon,
  CalendarClockIcon,
  EyeIcon,
  FilmIcon,
  FolderTreeIcon,
  GaugeIcon,
  Grid2X2Icon,
  ListIcon,
  MapPinnedIcon,
  PlayIcon,
  PlusIcon,
  RotateCcwIcon,
  SearchIcon,
  PencilIcon,
  SlidersHorizontalIcon,
  TriangleAlertIcon,
  UserRoundIcon,
} from "lucide-react"

import {
  archiveScenario,
  createScenario,
  listScenarios,
  restoreScenario,
  updateScenario,
  type ApiScenario,
  type ScenarioWritePayload,
} from "@/api/scenarios"
import { configureSimulation, generateTimeline, startSimulation } from "@/api/simulation"
import { listRLModels, type RLModelRecord } from "@/api/rl"
import { downloadObservationTemplate, getNativeScenarioOptions, importObservationCsv, resolveNativeScenario, type NativeScenarioConfig, type NativeScenarioOptions } from "@/api/native-scenario"
import { NativeNumber, NativeScenarioControls, NativeScenarioSummary, NativeSelect } from "@/components/native-scenario-controls"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

type ScenarioDensity = "None" | "Single" | "Low" | "Medium" | "High" | "Very High"
type ScenarioCategory = "all" | "official" | "user" | "active" | "archived"
type ScenarioTypeFilter = "all" | "official" | "user"
type ScenarioStateFilter = "all" | "active" | "archived"
type ScenarioViewMode = "cards" | "table"
type ScenarioSort = "name_asc" | "name_desc" | "date_desc" | "date_asc" | "density_desc"
type ScenarioFormMode = "create" | "edit"
type ScenarioPermissions = { create: boolean; edit: boolean; run: boolean }

type DisruptionConfig = {
  enabled: boolean
  approach: string
  severity?: string
  lanesClosed?: string
  speedReduction?: string
}

type ScenarioRecord = {
  id: number
  name: string
  description: string
  intersectionId: string
  trafficDensity: ScenarioDensity
  pedestrianDensity: string
  emergencyMode: string
  roadConstraint: string
  isOfficial: boolean
  isArchived: boolean
  createdAt: string
  updatedAt: string
  laneClosure: DisruptionConfig
  construction: DisruptionConfig
  accident: DisruptionConfig
  flooding: DisruptionConfig
  constraintsJson: string
  engineConfig: NativeScenarioConfig
}

type ScenarioDraft = {
  name: string
  description: string
  intersectionId: string
  trafficDensity: ScenarioDensity
  pedestrianDensity: string
  emergencyMode: string
  roadConstraint: string
  engineConfig: NativeScenarioConfig
}

const densityOrder: Record<ScenarioDensity, number> = {
  None: 0,
  Single: 0,
  Low: 1,
  Medium: 2,
  High: 3,
  "Very High": 4,
}

const emptyScenarioDraft: ScenarioDraft = {
  name: "",
  description: "",
  intersectionId: "",
  trafficDensity: "Medium",
  pedestrianDensity: "Medium",
  emergencyMode: "Disabled",
  roadConstraint: "None",
  engineConfig: {},
}

function normalizeDensity(value: string): ScenarioDensity {
  return (Object.keys(densityOrder) as ScenarioDensity[]).find((density) => density.toLowerCase() === value.toLowerCase()) ?? "Medium"
}

function disruptionFromApi(value: Record<string, unknown>): DisruptionConfig {
  return {
    enabled: Boolean(value.enabled),
    approach: String(value.approach ?? "north"),
    severity: typeof value.severity === "string" ? value.severity : undefined,
    lanesClosed:
      typeof value.lanes_closed === "number"
        ? `${value.lanes_closed} lane${value.lanes_closed === 1 ? "" : "s"}`
        : typeof value.lanesClosed === "string"
          ? value.lanesClosed
          : undefined,
    speedReduction:
      typeof value.speed_reduction === "number"
        ? `${Math.round(value.speed_reduction * 100)}%`
        : typeof value.speedReduction === "string"
          ? value.speedReduction
          : undefined,
  }
}

function scenarioFromApi(scenario: ApiScenario): ScenarioRecord {
  return {
    id: scenario.id,
    name: scenario.name,
    description: scenario.description ?? "",
    intersectionId: scenario.intersection_id,
    trafficDensity: normalizeDensity(scenario.traffic_density),
    pedestrianDensity: scenario.pedestrian_density || "Medium",
    emergencyMode: scenario.emergency_mode || "Disabled",
    roadConstraint: scenario.road_constraint || "None",
    isOfficial: scenario.is_official,
    isArchived: scenario.is_archived,
    createdAt: scenario.created_at ?? "",
    updatedAt: scenario.updated_at ?? "",
    laneClosure: disruptionFromApi(scenario.lane_closure_config),
    construction: disruptionFromApi(scenario.construction_config),
    accident: disruptionFromApi(scenario.accident_config),
    flooding: disruptionFromApi(scenario.flooding_config),
    constraintsJson: JSON.stringify(
      {
        lane_closure_config: scenario.lane_closure_config,
        construction_config: scenario.construction_config,
        accident_config: scenario.accident_config,
        flooding_config: scenario.flooding_config,
      },
      null,
      2
    ),
    engineConfig: scenario.engine_config ?? {},
  }
}

function formatDate(value: string) {
  if (!value) return "Not recorded"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 10)
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsed)
}

function formatIntersection(intersectionId: string) {
  return {
    tagum_network: "Tagum — 5 connected junctions",
    tagum_1: "Legacy scenario (uses connected network)",
    tagum_2: "Legacy scenario (uses connected network)",
  }[intersectionId] ?? intersectionId.replace("_", " ").toUpperCase()
}

function categoryMatches(scenario: ScenarioRecord, category: ScenarioCategory) {
  if (category === "official") return scenario.isOfficial
  if (category === "user") return !scenario.isOfficial
  if (category === "active") return !scenario.isArchived
  if (category === "archived") return scenario.isArchived
  return true
}

function sortScenarios(scenarios: ScenarioRecord[], sort: ScenarioSort) {
  return [...scenarios].sort((left, right) => {
    if (sort === "name_desc") return right.name.localeCompare(left.name)
    if (sort === "date_desc") return right.updatedAt.localeCompare(left.updatedAt)
    if (sort === "date_asc") return left.updatedAt.localeCompare(right.updatedAt)
    if (sort === "density_desc") return densityOrder[right.trafficDensity] - densityOrder[left.trafficDensity]
    return left.name.localeCompare(right.name)
  })
}

function densityBadgeVariant(density: ScenarioDensity): "default" | "secondary" | "destructive" | "outline" {
  if (density === "Very High" || density === "High") return "destructive"
  if (density === "Medium") return "secondary"
  return "outline"
}

function draftFromScenario(scenario: ScenarioRecord): ScenarioDraft {
  return {
    name: scenario.name,
    description: scenario.description,
    intersectionId: scenario.intersectionId,
    trafficDensity: scenario.trafficDensity,
    pedestrianDensity: scenario.pedestrianDensity,
    emergencyMode: scenario.emergencyMode,
    roadConstraint: scenario.roadConstraint,
    engineConfig: structuredClone(scenario.engineConfig),
  }
}

function payloadFromDraft(draft: ScenarioDraft): ScenarioWritePayload {
  return {
    name: draft.name, description: draft.description, intersection_id: draft.intersectionId,
    traffic_density: draft.trafficDensity, pedestrian_density: draft.pedestrianDensity,
    emergency_mode: draft.emergencyMode, road_constraint: "None",
    lane_closure_config: {}, construction_config: {}, accident_config: {}, flooding_config: {},
    engine_config: { ...draft.engineConfig, traffic_density: draft.trafficDensity.toLowerCase(),
      pedestrian_density: draft.pedestrianDensity.toLowerCase(), emergency_mode: draft.emergencyMode.toLowerCase(), road_constraint: "None" },
  }
}

function ScenarioSelect({
  value,
  options,
  onChange,
  className,
}: {
  value: string
  options: { label: string; value: string }[]
  onChange: (value: string) => void
  className?: string
}) {
  return (
    <Select items={options} value={value} onValueChange={(nextValue) => nextValue !== null && onChange(nextValue)}>
      <SelectTrigger className={cn("w-full", className)}>
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
function ScenarioStatusBadges({ scenario }: { scenario: ScenarioRecord }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Badge variant={scenario.isOfficial ? "default" : "secondary"}>
        {scenario.isOfficial ? <BadgeCheckIcon data-icon="inline-start" /> : <UserRoundIcon data-icon="inline-start" />}
        {scenario.isOfficial ? "Official" : "User"}
      </Badge>
      <Badge variant={scenario.isArchived ? "outline" : "secondary"}>{scenario.isArchived ? "Archived" : "Active"}</Badge>
      <Badge variant={densityBadgeVariant(scenario.trafficDensity)}>{scenario.trafficDensity}</Badge>
    </div>
  )
}

export function ScenariosPage({ onOpenDashboard, permissions }: {
  onOpenDashboard?: () => void; permissions: ScenarioPermissions
}) {
  const [scenarios, setScenarios] = React.useState<ScenarioRecord[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [isSaving, setIsSaving] = React.useState(false)
  const [search, setSearch] = React.useState("")
  const [category, setCategory] = React.useState<ScenarioCategory>("all")
  const [density, setDensity] = React.useState<"all" | ScenarioDensity>("all")
  const [typeFilter, setTypeFilter] = React.useState<ScenarioTypeFilter>("all")
  const [stateFilter, setStateFilter] = React.useState<ScenarioStateFilter>("all")
  const [sort, setSort] = React.useState<ScenarioSort>("name_asc")
  const [viewMode, setViewMode] = React.useState<ScenarioViewMode>("cards")
  const [selectedId, setSelectedId] = React.useState<number | null>(null)
  const [recordingScenarioId, setRecordingScenarioId] = React.useState<number | null>(null)
  const [recordingModels, setRecordingModels] = React.useState<RLModelRecord[]>([])
  const [recordControlMode, setRecordControlMode] = React.useState("fixed-time")
  const [recordDuration, setRecordDuration] = React.useState(300)
  const [recordSeed, setRecordSeed] = React.useState(42)
  const [recordError, setRecordError] = React.useState("")
  const [notice, setNotice] = React.useState("Loading scenarios from SQLite...")
  const [formMode, setFormMode] = React.useState<ScenarioFormMode | null>(null)
  const [editingScenarioId, setEditingScenarioId] = React.useState<number | null>(null)
  const [draft, setDraft] = React.useState<ScenarioDraft>(emptyScenarioDraft)
  const [nativeOptions, setNativeOptions] = React.useState<NativeScenarioOptions | null>(null)
  const [formError, setFormError] = React.useState("")
  const [importKind, setImportKind] = React.useState<"trips" | "od_counts" | "turn_counts" | "pedestrian_counts">("trips")
  const [importSourceKind, setImportSourceKind] = React.useState<"synthetic" | "observed">("synthetic")
  const [importDescription, setImportDescription] = React.useState("")
  const [importDate, setImportDate] = React.useState(new Date().toISOString().slice(0, 10))
  const [importCollectionStart, setImportCollectionStart] = React.useState("")
  const [importCollectionEnd, setImportCollectionEnd] = React.useState("")
  const [importFile, setImportFile] = React.useState<File | null>(null)
  const [importNotice, setImportNotice] = React.useState("")
  const [isImporting, setIsImporting] = React.useState(false)
  const [isDownloadingTemplate, setIsDownloadingTemplate] = React.useState(false)
  const [isResolving, setIsResolving] = React.useState(false)
  const [editConfigReady, setEditConfigReady] = React.useState(true)
  const editRequest = React.useRef(0)

  React.useEffect(() => {
    let mounted = true
    getNativeScenarioOptions().then((options) => { if (mounted) setNativeOptions(options) })
      .catch((error) => { if (mounted) setNotice(error instanceof Error ? error.message : "Unable to load network choices.") })
    return () => { mounted = false }
  }, [])

  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedId) ?? null
  const recordingScenario = scenarios.find((scenario) => scenario.id === recordingScenarioId) ?? null

  const loadScenarios = React.useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await listScenarios({ includeArchived: true })
      const nextScenarios = response.scenarios.map(scenarioFromApi)
      setScenarios(nextScenarios)
      setNotice(`Loaded ${nextScenarios.length} scenario${nextScenarios.length === 1 ? "" : "s"} from SQLite.`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to load scenarios from the API.")
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) void loadScenarios() })
    return () => { active = false }
  }, [loadScenarios])

  const filteredScenarios = React.useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return sortScenarios(
      scenarios.filter((scenario) => {
        if (!categoryMatches(scenario, category)) return false
        if (normalizedSearch && !`${scenario.name} ${scenario.description}`.toLowerCase().includes(normalizedSearch)) {
          return false
        }
        if (density !== "all" && scenario.trafficDensity !== density) return false
        if (typeFilter === "official" && !scenario.isOfficial) return false
        if (typeFilter === "user" && scenario.isOfficial) return false
        if (stateFilter === "active" && scenario.isArchived) return false
        if (stateFilter === "archived" && !scenario.isArchived) return false
        return true
      }),
      sort
    )
  }, [category, density, scenarios, search, sort, stateFilter, typeFilter])

  const stats = React.useMemo(() => {
    const total = scenarios.length
    const official = scenarios.filter((scenario) => scenario.isOfficial).length
    const archived = scenarios.filter((scenario) => scenario.isArchived).length
    return {
      total,
      official,
      user: total - official,
      active: total - archived,
    }
  }, [scenarios])

  function openView(scenario: ScenarioRecord) {
    setSelectedId(scenario.id)
  }

  function openCreateForm() {
    if (!permissions.create) return
    editRequest.current += 1
    setFormError("")
    setEditConfigReady(true)
    setIsResolving(false)
    setFormMode("create")
    setEditingScenarioId(null)
    setDraft({ ...emptyScenarioDraft, intersectionId: nativeOptions?.network_id ?? "",
      engineConfig: structuredClone(nativeOptions?.defaults ?? {}) })
  }

  async function openEditForm(scenario: ScenarioRecord) {
    if (!permissions.edit) return
    const request = ++editRequest.current
    setSelectedId(null)
    setFormMode("edit")
    setEditingScenarioId(scenario.id)
    setDraft(draftFromScenario(scenario))
    setFormError("")
    setEditConfigReady(false)
    setIsResolving(true)
    try {
      const result = await resolveNativeScenario(scenario.id)
      if (request !== editRequest.current) return
      setDraft((current) => ({ ...current, engineConfig: result.engine_config,
        trafficDensity: normalizeDensity(String(result.engine_config.traffic_density)),
        pedestrianDensity: String(result.engine_config.pedestrian_density),
        emergencyMode: String(result.engine_config.emergency_mode) }))
      setEditConfigReady(true)
    } catch (error) {
      if (request === editRequest.current) setFormError(error instanceof Error ? error.message : "Unable to load native settings.")
    } finally {
      if (request === editRequest.current) setIsResolving(false)
    }
  }

  async function saveScenarioDraft() {
    if (formMode === "edit" ? !permissions.edit : !permissions.create) return
    if (!nativeOptions || isResolving || !editConfigReady) return
    setFormError("")
    if (!draft.name.trim()) {
      setFormError("Scenario name is required.")
      return
    }
    setIsSaving(true)
    try {
      if (formMode === "edit" && editingScenarioId !== null) {
        const updated = await updateScenario(editingScenarioId, payloadFromDraft(draft))
        setScenarios((current) => current.map((scenario) => scenario.id === updated.id ? scenarioFromApi(updated) : scenario))
        setNotice(`"${updated.name}" updated in SQLite.`)
      } else {
        const created = await createScenario(payloadFromDraft(draft))
        setScenarios((current) => sortScenarios([...current, scenarioFromApi(created)], "name_asc"))
        setNotice(`"${created.name}" created in SQLite.`)
      }
      setFormMode(null)
      setEditingScenarioId(null)
      setDraft(emptyScenarioDraft)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to save scenario.")
    } finally {
      setIsSaving(false)
    }
  }

  async function downloadImportTemplate(example: boolean) {
    setIsDownloadingTemplate(true)
    setFormError("")
    try {
      const result = await downloadObservationTemplate(importKind, example)
      if (example) {
        setImportSourceKind("synthetic")
        setImportDescription(`Synthetic ${importKind} example for ${result.network_id}; no field observations`)
      }
      setImportNotice(`${example ? "Synthetic example" : "Blank template"} downloaded for ${result.network_id}. ${example ? "Use Synthetic sample provenance; example values are not field observations." : "Add your data rows before importing."}`)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to download CSV template.")
    } finally {
      setIsDownloadingTemplate(false)
    }
  }

  async function importCsvToDraft() {
    if (!importFile || !nativeOptions || !editConfigReady) {
      setFormError("Choose a CSV file and wait for scenario settings to load.")
      return
    }
    setIsImporting(true)
    setFormError("")
    setImportNotice("")
    try {
      const response = await importObservationCsv({
        kind: importKind, source_kind: importSourceKind, csv_text: await importFile.text(),
        source_description: importDescription, collected_on: importDate, engine_config: draft.engineConfig,
        collection_start: importSourceKind === "observed" ? importCollectionStart || undefined : undefined,
        collection_end: importSourceKind === "observed" ? importCollectionEnd || undefined : undefined,
      })
      setDraft((current) => ({ ...current, engineConfig: response.engine_config,
        trafficDensity: importKind === "pedestrian_counts" ? current.trafficDensity : "None",
        pedestrianDensity: importKind === "pedestrian_counts" ? "none" : current.pedestrianDensity }))
      setImportNotice(`Validated ${response.summary.row_count} rows and ${response.summary.arrival_count} arrivals. Source SHA-256: ${response.summary.sha256}. Save the scenario to use them.`)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to import CSV.")
    } finally {
      setIsImporting(false)
    }
  }

  async function toggleArchiveScenario(scenario: ScenarioRecord) {
    if (!permissions.edit) return
    setIsSaving(true)
    try {
      const updated = scenario.isArchived
        ? await restoreScenario(scenario.id)
        : await archiveScenario(scenario.id)
      setScenarios((current) => current.map((item) => item.id === updated.id ? scenarioFromApi(updated) : item))
      setNotice(`"${updated.name}" ${updated.is_archived ? "archived" : "restored"}.`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to update scenario status.")
    } finally {
      setIsSaving(false)
    }
  }

  async function launchScenario(scenario: ScenarioRecord, action: "load" | "live" | "record") {
    if (!permissions.run) return
    if (scenario.isArchived) {
      setNotice(`"${scenario.name}" is archived. Restore it before loading or running.`)
      return
    }
    if (action === "record") {
      setSelectedId(null)
      setRecordingScenarioId(scenario.id)
      setRecordControlMode("fixed-time")
      setRecordDuration(300)
      setRecordSeed(42)
      setRecordError("")
      try {
        const response = await listRLModels()
        setRecordingModels(response.models.filter((model) => model.compatible &&
          (!model.controlled_junction || model.controlled_junction === scenario.engineConfig.controlled_junction)))
      } catch (error) {
        setRecordingModels([])
        setRecordError(error instanceof Error ? error.message : "Unable to load saved models.")
      }
      return
    }
    setIsSaving(true)
    try {
      if (action === "live") {
        await startSimulation({ scenario_id: scenario.id, duration_seconds: 300, control_mode: "fixed-time" })
        setNotice(`"${scenario.name}" started as a live FastAPI simulation.`)
      } else {
        await configureSimulation({ scenario_id: scenario.id, duration_seconds: 300, control_mode: "fixed-time" })
        setNotice(`"${scenario.name}" loaded into the dashboard simulation context.`)
      }
      onOpenDashboard?.()
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to launch scenario.")
    } finally {
      setIsSaving(false)
    }
  }

  async function startRecording() {
    if (!permissions.run) return
    if (!recordingScenario) return
    if (!Number.isInteger(recordDuration) || recordDuration < 1 || recordDuration > 86400 ||
        !Number.isInteger(recordSeed) || recordSeed < 0 || recordSeed > 4294967295) {
      setRecordError("Enter an integer duration from 1 to 86400 seconds and a seed from 0 to 4294967295.")
      return
    }
    setIsSaving(true)
    setRecordError("")
    try {
      const response = await generateTimeline({
        scenario_id: recordingScenario.id,
        duration_seconds: recordDuration,
        seed: recordSeed,
        control_mode: recordControlMode,
      })
      setNotice(`"${recordingScenario.name}" ${recordControlMode} recording started as run #${response.run.id}.`)
      setRecordingScenarioId(null)
      onOpenDashboard?.()
    } catch (error) {
      setRecordError(error instanceof Error ? error.message : "Unable to start recording.")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <main className="smartflow-page scenarios-page">
      <section className="scenarios-hero">
        <div>
          <h1>Scenario Library</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void loadScenarios()} disabled={isLoading}>
            <RotateCcwIcon data-icon="inline-start" />
            {isLoading ? "Refreshing" : "Refresh"}
          </Button>
          <Button onClick={openCreateForm} disabled={isSaving || !nativeOptions || !permissions.create}>
            <PlusIcon data-icon="inline-start" />
            New Scenario
          </Button>
        </div>
      </section>

      <section className="scenario-metric-strip" aria-label="Scenario metrics">
        <ScenarioMetric icon={FolderTreeIcon} label="Total" value={stats.total} hint="SQLite scenarios" />
        <ScenarioMetric icon={BadgeCheckIcon} label="Official" value={stats.official} hint="Approved presets" />
        <ScenarioMetric icon={UserRoundIcon} label="User" value={stats.user} hint="Custom records" />
        <ScenarioMetric icon={ArchiveIcon} label="Active" value={stats.active} hint="Ready to load" />
      </section>

      <div className="scenario-notice">
        <BadgeCheckIcon />
        <span>{notice}</span>
      </div>

      <section className="scenario-workspace">
        <aside className="scenario-filter-rail">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPinnedIcon />
                Scenario Groups
              </CardTitle>
              <CardDescription>{scenarios.length} records from API</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-1">
              {[
                { label: "All Scenarios", value: "all", count: scenarios.length },
                { label: "Official", value: "official", count: stats.official },
                { label: "User Created", value: "user", count: stats.user },
                { label: "Active", value: "active", count: stats.active },
                { label: "Archived", value: "archived", count: scenarios.length - stats.active },
              ].map((item) => (
                <button
                  key={item.value}
                  className={cn("scenario-category-button", category === item.value && "active")}
                  type="button"
                  onClick={() => setCategory(item.value as ScenarioCategory)}
                >
                  <span>{item.label}</span>
                  <Badge variant="secondary">{item.count}</Badge>
                </button>
              ))}
            </CardContent>
          </Card>
        </aside>

        <div className="scenario-library-panel">
          <Card className="scenario-toolbar-card">
            <CardContent className="scenario-toolbar-content">
              <label className="scenario-search-field">
                <SearchIcon />
                <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search scenario name or description" />
              </label>
              <ScenarioSelect
                value={density}
                onChange={(value) => setDensity(value as "all" | ScenarioDensity)}
                options={[
                  { label: "All Density", value: "all" },
                  { label: "Single car", value: "Single" },
                      { label: "Low", value: "Low" },
                  { label: "Medium", value: "Medium" },
                  { label: "High", value: "High" },
                  { label: "Very High", value: "Very High" },
                ]}
              />
              <ScenarioSelect
                value={typeFilter}
                onChange={(value) => setTypeFilter(value as ScenarioTypeFilter)}
                options={[
                  { label: "All Types", value: "all" },
                  { label: "Official", value: "official" },
                  { label: "User", value: "user" },
                ]}
              />
              <ScenarioSelect
                value={stateFilter}
                onChange={(value) => setStateFilter(value as ScenarioStateFilter)}
                options={[
                  { label: "All States", value: "all" },
                  { label: "Active", value: "active" },
                  { label: "Archived", value: "archived" },
                ]}
              />
              <ScenarioSelect
                value={sort}
                onChange={(value) => setSort(value as ScenarioSort)}
                options={[
                  { label: "Name A-Z", value: "name_asc" },
                  { label: "Name Z-A", value: "name_desc" },
                  { label: "Recently Updated", value: "date_desc" },
                  { label: "Oldest Updated", value: "date_asc" },
                  { label: "Highest Density", value: "density_desc" },
                ]}
              />
              <div className="scenario-view-toggle">
                <Button size="icon-sm" variant={viewMode === "cards" ? "default" : "outline"} onClick={() => setViewMode("cards")} aria-label="Card view">
                  <Grid2X2Icon />
                </Button>
                <Button size="icon-sm" variant={viewMode === "table" ? "default" : "outline"} onClick={() => setViewMode("table")} aria-label="Table view">
                  <ListIcon />
                </Button>
              </div>
            </CardContent>
          </Card>

          {isLoading ? (
            <Card className="scenario-empty-state">
              <CardContent>
                <MapPinnedIcon />
                <h3>Loading Scenarios</h3>
                <span>Reading scenario records from the FastAPI bridge.</span>
              </CardContent>
            </Card>
          ) : filteredScenarios.length ? (
            viewMode === "cards" ? (
              <div className="scenario-card-grid">
                {filteredScenarios.map((scenario) => (
                  <ScenarioCard
                    key={scenario.id}
                    scenario={scenario}
                    selectedId={selectedId}
                    permissions={permissions}
                    onArchive={toggleArchiveScenario}
                    onEdit={openEditForm}
                    onLaunch={launchScenario}
                    onView={openView}
                  />
                ))}
              </div>
            ) : (
              <ScenarioTable
                scenarios={filteredScenarios}
                selectedId={selectedId}
                permissions={permissions}
                onArchive={toggleArchiveScenario}
                onEdit={openEditForm}
                onLaunch={launchScenario}
                onView={openView}
              />
            )
          ) : (
            <Card className="scenario-empty-state">
              <CardContent>
                <MapPinnedIcon />
                <h3>No scenarios found</h3>
                <span>Try adjusting your search or filters.</span>
              </CardContent>
            </Card>
          )}
        </div>
      </section>

      <Sheet open={Boolean(selectedScenario)} onOpenChange={(open) => !open && setSelectedId(null)}>
        <SheetContent className="scenario-sheet" side="right">
          {selectedScenario ? (
            <ScenarioDetailSheet
              scenario={selectedScenario}
              permissions={permissions}
              onArchive={toggleArchiveScenario}
              onEdit={openEditForm}
              onLaunch={launchScenario}
            />
          ) : null}
        </SheetContent>
      </Sheet>

      <Sheet open={formMode !== null} onOpenChange={(open) => !open && setFormMode(null)}>
        <SheetContent className="scenario-sheet" side="right">
          <SheetHeader>
            <SheetTitle>{formMode === "edit" ? "Edit Scenario" : "New Scenario"}</SheetTitle>
            <SheetDescription>Configure demand, signal plans and scheduled road changes. Saved settings are shared by live runs, recordings and training.</SheetDescription>
          </SheetHeader>
          <div className="scenario-sheet-scroll">
            <FieldGroup className="px-4 pb-4">
              {formError && <Alert variant="destructive"><AlertDescription>{formError}</AlertDescription></Alert>}
              {!editConfigReady && !isResolving && nativeOptions && <Button variant="outline" onClick={() => {
                setDraft((current) => ({ ...current, intersectionId: nativeOptions.network_id,
                  engineConfig: structuredClone(nativeOptions.defaults) }))
                setEditConfigReady(true)
                setFormError("")
              }}>Replace unsupported settings with native defaults</Button>}
              <Field>
                <FieldLabel htmlFor="scenario-name">Name</FieldLabel>
                <Input id="scenario-name" value={draft.name} maxLength={160} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} />
              </Field>
              <Field>
                <FieldLabel htmlFor="scenario-description">Description</FieldLabel>
                <textarea id="scenario-description" className="scenario-textarea" maxLength={2000} value={draft.description}
                  onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} />
              </Field>
              <p className="text-sm text-muted-foreground">{nativeOptions?.network_name ?? "Loading road network..."}. This network is provisional; demand is synthetic unless identified otherwise.</p>
              <FieldGroup className="grid sm:grid-cols-2">
                <NativeSelect label="Traffic density" value={draft.trafficDensity.toLowerCase()}
                  options={["None", "Single", "Low", "Medium", "High", "Very High"].map((label) => ({ label, value: label.toLowerCase() }))}
                  onChange={(value) => setDraft((current) => ({ ...current, trafficDensity: normalizeDensity(value) }))} />
                <NativeSelect label="Pedestrians" value={draft.pedestrianDensity.toLowerCase()}
                  options={["None", "Low", "Medium", "High"].map((label) => ({ label, value: label.toLowerCase() }))}
                  onChange={(pedestrianDensity) => setDraft((current) => ({ ...current, pedestrianDensity }))} />
                <NativeSelect label="Emergency vehicles" value={draft.emergencyMode.toLowerCase()}
                  options={[{ label: "Disabled", value: "disabled" }, { label: "One ambulance", value: "enabled (1 ambulance)" },
                    { label: "Enabled", value: "enabled" }, { label: "One vehicle", value: "enabled (1 vehicle)" }, { label: "Two vehicles", value: "enabled (2 vehicles)" }]}
                  onChange={(emergencyMode) => setDraft((current) => ({ ...current, emergencyMode }))} />
              </FieldGroup>
              <fieldset className="rounded-lg border p-3 flex flex-col gap-3">
                <legend className="font-medium">Import demand CSV</legend>
                <p className="text-sm text-muted-foreground">Network boundary IDs: {nativeOptions?.boundaries.map((item) => `${item.id} (${item.label})`).join(", ") ?? "loading"}. Junction IDs: {nativeOptions?.junctions.map((item) => item.id).join(", ") ?? "loading"}.</p>
                <NativeSelect label="CSV schema" value={importKind} options={[
                  { value: "trips", label: "Trips: time_s, source, destination, vehicle_type" },
                  { value: "od_counts", label: "OD counts: start_s, end_s, source, destination, count" },
                  { value: "turn_counts", label: "Turn counts: start_s, end_s, source, destination, junction, from_lane, to_lane, count" },
                  { value: "pedestrian_counts", label: "Pedestrians: start_s, end_s, junction, count" },
                ]} onChange={(value) => setImportKind(value as typeof importKind)} />
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" size="sm" disabled={isDownloadingTemplate || !nativeOptions} onClick={() => void downloadImportTemplate(false)}>Download blank template</Button>
                  <Button type="button" variant="outline" size="sm" disabled={isDownloadingTemplate || !nativeOptions} onClick={() => void downloadImportTemplate(true)}>Download synthetic example</Button>
                </div>
                <Alert><AlertDescription>Templates match the selected CSV schema. Synthetic examples use the loaded network's IDs and invented counts; never report them as field observations. A blank template needs at least one data row.</AlertDescription></Alert>
                <p className="text-sm text-muted-foreground">Use exact boundary IDs for source/destination and junction or directed lane IDs where required. Times are seconds from simulation start, not clock times. Counts are non-negative whole numbers; vehicle_type can be car, motorcycle, tricycle, bus, truck or emergency. Keep unknown measurements outside this CSV instead of entering zero.</p>
                {importKind === "turn_counts" && <p className="text-sm text-muted-foreground">Lane IDs (source → target): {nativeOptions?.lanes.map((lane) => `${lane.id} (${lane.source} → ${lane.target})`).join(", ") ?? "loading"}. The supplied boundary route must include the recorded turn; later rerouting may change it.</p>}
                <NativeSelect label="Data provenance" value={importSourceKind} options={[
                  { value: "synthetic", label: "Synthetic sample" }, { value: "observed", label: "Field observation" },
                ]} onChange={(value) => setImportSourceKind(value as typeof importSourceKind)} />
                <Field><FieldLabel htmlFor="import-description">Source description</FieldLabel>
                  <Input id="import-description" value={importDescription} maxLength={500} onChange={(event) => setImportDescription(event.target.value)} /></Field>
                <Field><FieldLabel htmlFor="import-date">Collection or sample date</FieldLabel>
                  <Input id="import-date" type="date" value={importDate} onChange={(event) => setImportDate(event.target.value)} /></Field>
                <Field><FieldLabel htmlFor="import-file">CSV file</FieldLabel>
                  <Input id="import-file" type="file" accept=".csv,text/csv" onChange={(event) => setImportFile(event.target.files?.[0] ?? null)} /></Field>
                {importSourceKind === "observed" && <FieldGroup>
                  <Field><FieldLabel htmlFor="import-collection-start">Collection start (optional)</FieldLabel>
                    <Input id="import-collection-start" placeholder="2026-01-01T07:00:00+08:00" value={importCollectionStart} onChange={(event) => setImportCollectionStart(event.target.value)} /></Field>
                  <Field><FieldLabel htmlFor="import-collection-end">Collection end (optional)</FieldLabel>
                    <Input id="import-collection-end" placeholder="2026-01-01T08:00:00+08:00" value={importCollectionEnd} onChange={(event) => setImportCollectionEnd(event.target.value)} /></Field>
                  <p className="text-sm text-muted-foreground">Enter both timestamps with a UTC offset to declare a collection period. Same-date held-out inputs require disjoint periods. CSV time 0 is the collection start and simulation start, including any warmup.</p>
                </FieldGroup>}
                <p className="text-sm text-muted-foreground">Times are seconds from simulation start. Count bins create evenly spaced arrivals; actual arrival times are unknown. Vehicle imports replace vehicle trips and windows; pedestrian imports replace the pedestrian schedule.</p>
                <Button type="button" variant="outline" disabled={isImporting || !nativeOptions || !editConfigReady} onClick={() => void importCsvToDraft()}>{isImporting ? "Validating..." : "Validate and apply to draft"}</Button>
                {importNotice && <p role="status" className="text-sm">{importNotice}</p>}
              </fieldset>
              {isResolving ? <p role="status">Loading saved native settings...</p> : nativeOptions && editConfigReady &&
                <NativeScenarioControls value={draft.engineConfig} options={nativeOptions}
                  onChange={(engineConfig) => setDraft((current) => ({ ...current, engineConfig }))} />}
            </FieldGroup>
          </div>
          <SheetFooter className="scenario-sheet-footer">
            <Button variant="outline" onClick={() => setFormMode(null)}>Cancel</Button>
            <Button onClick={() => void saveScenarioDraft()} disabled={isSaving || isResolving || !nativeOptions || !editConfigReady ||
              (formMode === "edit" ? !permissions.edit : !permissions.create)}>
              {isSaving ? "Saving..." : "Save Scenario"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={Boolean(recordingScenario)} onOpenChange={(open) => !open && setRecordingScenarioId(null)}>
        <SheetContent className="scenario-sheet" side="right">
          <SheetHeader>
            <SheetTitle>Record scenario</SheetTitle>
            <SheetDescription>{recordingScenario?.name ?? "Saved scenario"}. Choose a controller and matched seed for a comparable timeline.</SheetDescription>
          </SheetHeader>
          <div className="scenario-sheet-scroll">
            <FieldGroup className="px-4 pb-4">
              {recordError && <Alert variant="destructive"><AlertDescription>{recordError}</AlertDescription></Alert>}
              <NativeSelect label="Recording controller" value={recordControlMode} options={[
                { value: "fixed-time", label: "Fixed-time baseline" },
                ...recordingModels.map((model) => ({ value: `${model.algorithm}:${model.id}`, label: `${model.algorithm.toUpperCase()} model #${model.id} · ${model.name ?? "Saved model"}` })),
              ]} onChange={setRecordControlMode} />
              <NativeNumber label="Recording duration (seconds)" value={recordDuration} onChange={setRecordDuration} min={1} max={86400} step={1} />
              <NativeNumber label="Recording seed" value={recordSeed} onChange={setRecordSeed} min={0} max={4294967295} step={1} />
              <p className="text-sm text-muted-foreground">Record the fixed-time baseline and selected model with the same saved scenario, seed and duration. A completed timeline appears in Compare Runs and Runs & Reports.</p>
            </FieldGroup>
          </div>
          <SheetFooter className="scenario-sheet-footer">
            <Button variant="outline" onClick={() => setRecordingScenarioId(null)}>Cancel</Button>
            <Button onClick={() => void startRecording()} disabled={isSaving || !permissions.run}>{isSaving ? "Starting..." : "Start recording"}</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </main>
  )
}

function ScenarioMetric({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  label: string
  value: number
  hint: string
}) {
  return (
    <div className="scenario-strip-metric">
      <Icon />
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
        <small>{hint}</small>
      </div>
    </div>
  )
}

function ScenarioCard({
  scenario,
  selectedId,
  permissions,
  onArchive,
  onEdit,
  onView,
  onLaunch,
}: {
  scenario: ScenarioRecord
  selectedId: number | null
  permissions: ScenarioPermissions
  onArchive: (scenario: ScenarioRecord) => void
  onEdit: (scenario: ScenarioRecord) => void
  onView: (scenario: ScenarioRecord) => void
  onLaunch: (scenario: ScenarioRecord, action: "load" | "live" | "record") => void
}) {
  return (
    <Card className={cn("scenario-card", selectedId === scenario.id && "selected", scenario.isArchived && "archived")}>
      <CardHeader>
        <CardTitle className="scenario-card-title">
          <span>{scenario.name}</span>
        </CardTitle>
        <CardDescription>{scenario.description || "No description provided."}</CardDescription>
        <CardAction>
          <ScenarioStatusBadges scenario={scenario} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="scenario-card-meta-grid">
          <ScenarioMeta icon={MapPinnedIcon} label="Intersection" value={formatIntersection(scenario.intersectionId)} />
          <ScenarioMeta icon={GaugeIcon} label="Traffic Density" value={scenario.trafficDensity} />
          <ScenarioMeta icon={UserRoundIcon} label="Pedestrians" value={scenario.pedestrianDensity} />
          <ScenarioMeta icon={TriangleAlertIcon} label="Emergency" value={scenario.emergencyMode} />
        </div>
        <div className="scenario-card-actions">
          <Button size="sm" disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "load")}>
            <PlayIcon data-icon="inline-start" />
            Load
          </Button>
          <Button size="sm" variant="outline" disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "live")}>
            <BoltIcon data-icon="inline-start" />
            Live
          </Button>
          <Button size="sm" variant="outline" disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "record")}>
            <FilmIcon data-icon="inline-start" />
            Record
          </Button>
          <Button size="icon-sm" variant="outline" disabled={!permissions.edit} onClick={() => onEdit(scenario)} aria-label="Edit scenario">
            <PencilIcon />
          </Button>
          <Button size="icon-sm" variant="outline" disabled={!permissions.edit} onClick={() => onArchive(scenario)} aria-label={scenario.isArchived ? "Restore scenario" : "Archive scenario"}>
            <ArchiveIcon />
          </Button>
          <Button size="icon-sm" variant="ghost" onClick={() => onView(scenario)} aria-label="View details">
            <EyeIcon />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function ScenarioTable({
  scenarios,
  selectedId,
  permissions,
  onArchive,
  onEdit,
  onView,
  onLaunch,
}: {
  scenarios: ScenarioRecord[]
  selectedId: number | null
  permissions: ScenarioPermissions
  onArchive: (scenario: ScenarioRecord) => void
  onEdit: (scenario: ScenarioRecord) => void
  onView: (scenario: ScenarioRecord) => void
  onLaunch: (scenario: ScenarioRecord, action: "load" | "live" | "record") => void
}) {
  return (
    <Card>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Scenario</TableHead>
              <TableHead>Intersection</TableHead>
              <TableHead>Density</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {scenarios.map((scenario) => (
              <TableRow key={scenario.id} data-state={selectedId === scenario.id ? "selected" : undefined}>
                <TableCell>
                  <button className="scenario-table-name" type="button" onClick={() => onView(scenario)}>
                    <span className={cn("scenario-density-dot", scenario.trafficDensity.toLowerCase().replace(" ", "-"))} />
                    <span>
                      <strong>{scenario.name}</strong>
                      <small>{scenario.description}</small>
                    </span>
                  </button>
                </TableCell>
                <TableCell>{formatIntersection(scenario.intersectionId)}</TableCell>
                <TableCell>
                  <Badge variant={densityBadgeVariant(scenario.trafficDensity)}>{scenario.trafficDensity}</Badge>
                </TableCell>
                <TableCell>{scenario.isOfficial ? "Official" : "User"}</TableCell>
                <TableCell>{scenario.isArchived ? "Archived" : "Active"}</TableCell>
                <TableCell>{formatDate(scenario.updatedAt)}</TableCell>
                <TableCell>
                  <div className="scenario-table-actions">
                    <Button size="icon-xs" disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "load")} aria-label="Load dashboard">
                      <PlayIcon />
                    </Button>
                    <Button size="icon-xs" variant="outline" disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "live")} aria-label="Run live">
                      <BoltIcon />
                    </Button>
                    <Button size="icon-xs" variant="outline" disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "record")} aria-label="Pre-record">
                      <FilmIcon />
                    </Button>
                    <Button size="icon-xs" variant="outline" disabled={!permissions.edit} onClick={() => onEdit(scenario)} aria-label="Edit">
                      <PencilIcon />
                    </Button>
                    <Button size="icon-xs" variant="outline" disabled={!permissions.edit} onClick={() => onArchive(scenario)} aria-label={scenario.isArchived ? "Restore" : "Archive"}>
                      <ArchiveIcon />
                    </Button>
                    <Button size="icon-xs" variant="ghost" onClick={() => onView(scenario)} aria-label="View">
                      <EyeIcon />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function ScenarioMeta({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  label: string
  value: string
}) {
  return (
    <div className="scenario-meta-item">
      <Icon />
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  )
}

function ScenarioDetailSheet({
  scenario,
  permissions,
  onArchive,
  onEdit,
  onLaunch,
}: {
  scenario: ScenarioRecord
  permissions: ScenarioPermissions
  onArchive: (scenario: ScenarioRecord) => void
  onEdit: (scenario: ScenarioRecord) => void
  onLaunch: (scenario: ScenarioRecord, action: "load" | "live" | "record") => void
}) {
  return (
    <>
      <SheetHeader>
        <SheetTitle>{scenario.name}</SheetTitle>
        <SheetDescription>{formatIntersection(scenario.intersectionId)} · Scenario ID {scenario.id}</SheetDescription>
      </SheetHeader>
      <div className="scenario-sheet-scroll">
        <div className="flex flex-col gap-4 px-4">
          <ScenarioStatusBadges scenario={scenario} />
          <p className="text-sm leading-6 text-muted-foreground">{scenario.description || "No description provided."}</p>
          <div className="scenario-detail-grid">
            <ScenarioMeta icon={GaugeIcon} label="Traffic Density" value={scenario.trafficDensity} />
            <ScenarioMeta icon={UserRoundIcon} label="Pedestrian Activity" value={scenario.pedestrianDensity} />
            <ScenarioMeta icon={TriangleAlertIcon} label="Emergency Mode" value={scenario.emergencyMode} />
            <ScenarioMeta icon={SlidersHorizontalIcon} label="Road Constraint" value={scenario.roadConstraint} />
            <ScenarioMeta icon={CalendarClockIcon} label="Created" value={formatDate(scenario.createdAt)} />
            <ScenarioMeta icon={CalendarClockIcon} label="Updated" value={formatDate(scenario.updatedAt)} />
          </div>
          <ScenarioSchematic scenario={scenario} />
          <Card>
            <CardHeader>
              <CardTitle>Disruptions</CardTitle>
              <CardDescription>Native disruption schedule and controller configuration.</CardDescription>
            </CardHeader>
            <CardContent><NativeScenarioSummary config={scenario.engineConfig} options={null} /></CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Advanced JSON</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="scenario-json-preview">{JSON.stringify(scenario.engineConfig, null, 2)}</pre>
            </CardContent>
          </Card>
        </div>
      </div>
      <SheetFooter className="scenario-sheet-footer">
        <div className="grid grid-cols-2 gap-2">
          <Button disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "load")}>
            <PlayIcon data-icon="inline-start" />
            Load
          </Button>
          <Button variant="outline" disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "live")}>
            <BoltIcon data-icon="inline-start" />
            Live
          </Button>
          <Button variant="outline" disabled={!permissions.run || scenario.isArchived} onClick={() => onLaunch(scenario, "record")}>
            <FilmIcon data-icon="inline-start" />
            Record
          </Button>
          <Button variant="outline" disabled={!permissions.edit} onClick={() => onEdit(scenario)}>
            <PencilIcon data-icon="inline-start" />
            Edit
          </Button>
          <Button variant="outline" disabled={!permissions.edit} onClick={() => onArchive(scenario)}>
            <ArchiveIcon data-icon="inline-start" />
            {scenario.isArchived ? "Restore" : "Archive"}
          </Button>
        </div>
      </SheetFooter>
    </>
  )
}

function ScenarioSchematic({ scenario }: { scenario: ScenarioRecord }) {
  const intensity = densityOrder[scenario.trafficDensity]

  return (
    <Card className="scenario-schematic-card">
      <CardHeader>
        <CardTitle>Traffic Schematic</CardTitle>
        <CardDescription>Directional pressure preview from the selected density.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="scenario-schematic">
          <div className="scenario-road vertical" />
          <div className="scenario-road horizontal" />
          <div className="scenario-junction">
            <span>{scenario.intersectionId.replace("_", " ").toUpperCase()}</span>
          </div>
          {["N", "E", "S", "W"].map((direction, index) => (
            <span key={direction} className={cn("scenario-direction", direction.toLowerCase(), index < intensity && "active")}>
              {direction}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

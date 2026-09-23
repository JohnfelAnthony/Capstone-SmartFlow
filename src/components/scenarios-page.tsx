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

type ScenarioDensity = "Single" | "Low" | "Medium" | "High" | "Very High"
type ScenarioCategory = "all" | "official" | "user" | "active" | "archived"
type ScenarioTypeFilter = "all" | "official" | "user"
type ScenarioStateFilter = "all" | "active" | "archived"
type ScenarioViewMode = "cards" | "table"
type ScenarioSort = "name_asc" | "name_desc" | "date_desc" | "date_asc" | "density_desc"
type ScenarioFormMode = "create" | "edit"

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
}

type ScenarioDraft = {
  name: string
  description: string
  intersectionId: string
  trafficDensity: ScenarioDensity
  pedestrianDensity: string
  emergencyMode: string
  roadConstraint: string
}

const densityOrder: Record<ScenarioDensity, number> = {
  Single: 0,
  Low: 1,
  Medium: 2,
  High: 3,
  "Very High": 4,
}

const emptyScenarioDraft: ScenarioDraft = {
  name: "",
  description: "",
  intersectionId: "tagum_network",
  trafficDensity: "Medium",
  pedestrianDensity: "Medium",
  emergencyMode: "Disabled",
  roadConstraint: "None",
}

function normalizeDensity(value: string): ScenarioDensity {
  if (value === "Single" || value === "Low" || value === "Medium" || value === "High" || value === "Very High") {
    return value
  }
  return "Medium"
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
    intersectionId: "tagum_network",
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
  }
}

function constraintPayloadFromScenario(scenario?: ScenarioRecord | null) {
  if (!scenario) {
    return {
      lane_closure_config: {},
      construction_config: {},
      accident_config: {},
      flooding_config: {},
    }
  }
  try {
    const parsed = JSON.parse(scenario.constraintsJson) as Partial<ScenarioWritePayload>
    return {
      lane_closure_config: parsed.lane_closure_config ?? {},
      construction_config: parsed.construction_config ?? {},
      accident_config: parsed.accident_config ?? {},
      flooding_config: parsed.flooding_config ?? {},
    }
  } catch {
    return {
      lane_closure_config: {},
      construction_config: {},
      accident_config: {},
      flooding_config: {},
    }
  }
}

function payloadFromDraft(draft: ScenarioDraft, scenario?: ScenarioRecord | null): ScenarioWritePayload {
  const constraints = constraintPayloadFromScenario(scenario)
  return {
    name: draft.name,
    description: draft.description,
    intersection_id: draft.intersectionId,
    traffic_density: draft.trafficDensity,
    pedestrian_density: draft.pedestrianDensity,
    emergency_mode: draft.emergencyMode,
    road_constraint: draft.roadConstraint,
    ...constraints,
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
    <Select value={value} onValueChange={(nextValue) => nextValue !== null && onChange(nextValue)}>
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

export function ScenariosPage({ onOpenDashboard }: { onOpenDashboard?: () => void }) {
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
  const [notice, setNotice] = React.useState("Loading scenarios from SQLite...")
  const [formMode, setFormMode] = React.useState<ScenarioFormMode | null>(null)
  const [editingScenarioId, setEditingScenarioId] = React.useState<number | null>(null)
  const [draft, setDraft] = React.useState<ScenarioDraft>(emptyScenarioDraft)

  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedId) ?? null

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
    void loadScenarios()
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
    setFormMode("create")
    setEditingScenarioId(null)
    setDraft(emptyScenarioDraft)
  }

  function openEditForm(scenario: ScenarioRecord) {
    setFormMode("edit")
    setEditingScenarioId(scenario.id)
    setDraft(draftFromScenario(scenario))
  }

  async function saveScenarioDraft() {
    if (!draft.name.trim()) {
      setNotice("Scenario name is required.")
      return
    }
    setIsSaving(true)
    try {
      if (formMode === "edit" && editingScenarioId !== null) {
        const existingScenario = scenarios.find((scenario) => scenario.id === editingScenarioId)
        const updated = await updateScenario(editingScenarioId, payloadFromDraft(draft, existingScenario))
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
      setNotice(error instanceof Error ? error.message : "Unable to save scenario.")
    } finally {
      setIsSaving(false)
    }
  }

  async function toggleArchiveScenario(scenario: ScenarioRecord) {
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
    if (scenario.isArchived) {
      setNotice(`"${scenario.name}" is archived. Restore it before loading or running.`)
      return
    }
    setIsSaving(true)
    try {
      if (action === "record") {
        const response = await generateTimeline({
          scenario_id: scenario.id,
          duration_seconds: 300,
          control_mode: "fixed-time",
        })
        setNotice(`"${scenario.name}" pre-record timeline started as run #${response.run.id}.`)
      } else if (action === "live") {
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
          <Button onClick={openCreateForm} disabled={isSaving}>
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
            <SheetDescription>Save scenario settings to the existing SQLite scenario table.</SheetDescription>
          </SheetHeader>
          <div className="scenario-sheet-scroll">
            <div className="scenario-form px-4">
              <label className="scenario-form-full">
                <span>Name</span>
                <Input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label className="scenario-form-full">
                <span>Description</span>
                <textarea
                  className="scenario-textarea"
                  value={draft.description}
                  onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
                />
              </label>
              <div className="scenario-form-grid">
                <label>
                  <span>Intersection</span>
                  <ScenarioSelect
                    value={draft.intersectionId}
                    onChange={(value) => setDraft((current) => ({ ...current, intersectionId: value }))}
                    options={[
                      { label: "Tagum — 5 connected junctions", value: "tagum_network" },
                    ]}
                  />
                </label>
                <label>
                  <span>Traffic Density</span>
                  <ScenarioSelect
                    value={draft.trafficDensity}
                    onChange={(value) => setDraft((current) => ({ ...current, trafficDensity: normalizeDensity(value) }))}
                    options={[
                      { label: "Single car", value: "Single" },
                      { label: "Low", value: "Low" },
                      { label: "Medium", value: "Medium" },
                      { label: "High", value: "High" },
                      { label: "Very High", value: "Very High" },
                    ]}
                  />
                </label>
                <label>
                  <span>Pedestrians</span>
                  <ScenarioSelect
                    value={draft.pedestrianDensity}
                    onChange={(value) => setDraft((current) => ({ ...current, pedestrianDensity: value }))}
                    options={[
                      { label: "None", value: "None" },
                      { label: "Single car", value: "Single" },
                      { label: "Low", value: "Low" },
                      { label: "Medium", value: "Medium" },
                      { label: "High", value: "High" },
                    ]}
                  />
                </label>
                <label>
                  <span>Emergency Mode</span>
                  <ScenarioSelect
                    value={draft.emergencyMode}
                    onChange={(value) => setDraft((current) => ({ ...current, emergencyMode: value }))}
                    options={[
                      { label: "Disabled", value: "Disabled" },
                      { label: "Enabled (1 Ambulance)", value: "Enabled (1 Ambulance)" },
                      { label: "Enabled (2 Vehicles)", value: "Enabled (2 Vehicles)" },
                    ]}
                  />
                </label>
                <label>
                  <span>Road Constraint</span>
                  <ScenarioSelect
                    value={draft.roadConstraint}
                    onChange={(value) => setDraft((current) => ({ ...current, roadConstraint: value }))}
                    options={[
                      { label: "None", value: "None" },
                      { label: "Lane Closure", value: "Lane Closure" },
                      { label: "Construction", value: "Construction" },
                      { label: "Accident", value: "Accident" },
                      { label: "Flooding", value: "Flooding" },
                      { label: "Temporary Blockage", value: "Temporary Blockage" },
                    ]}
                  />
                </label>
              </div>
            </div>
          </div>
          <SheetFooter className="scenario-sheet-footer">
            <Button variant="outline" onClick={() => setFormMode(null)}>Cancel</Button>
            <Button onClick={() => void saveScenarioDraft()} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save Scenario"}
            </Button>
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
  onArchive,
  onEdit,
  onView,
  onLaunch,
}: {
  scenario: ScenarioRecord
  selectedId: number | null
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
          <Button size="sm" onClick={() => onLaunch(scenario, "load")}>
            <PlayIcon data-icon="inline-start" />
            Load
          </Button>
          <Button size="sm" variant="outline" onClick={() => onLaunch(scenario, "live")}>
            <BoltIcon data-icon="inline-start" />
            Live
          </Button>
          <Button size="sm" variant="outline" onClick={() => onLaunch(scenario, "record")}>
            <FilmIcon data-icon="inline-start" />
            Record
          </Button>
          <Button size="icon-sm" variant="outline" onClick={() => onEdit(scenario)} aria-label="Edit scenario">
            <PencilIcon />
          </Button>
          <Button size="icon-sm" variant="outline" onClick={() => onArchive(scenario)} aria-label={scenario.isArchived ? "Restore scenario" : "Archive scenario"}>
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
  onArchive,
  onEdit,
  onView,
  onLaunch,
}: {
  scenarios: ScenarioRecord[]
  selectedId: number | null
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
                    <Button size="icon-xs" onClick={() => onLaunch(scenario, "load")} aria-label="Load dashboard">
                      <PlayIcon />
                    </Button>
                    <Button size="icon-xs" variant="outline" onClick={() => onLaunch(scenario, "live")} aria-label="Run live">
                      <BoltIcon />
                    </Button>
                    <Button size="icon-xs" variant="outline" onClick={() => onLaunch(scenario, "record")} aria-label="Pre-record">
                      <FilmIcon />
                    </Button>
                    <Button size="icon-xs" variant="outline" onClick={() => onEdit(scenario)} aria-label="Edit">
                      <PencilIcon />
                    </Button>
                    <Button size="icon-xs" variant="outline" onClick={() => onArchive(scenario)} aria-label={scenario.isArchived ? "Restore" : "Archive"}>
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
  onArchive,
  onEdit,
  onLaunch,
}: {
  scenario: ScenarioRecord
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
              <CardDescription>Read from the existing SQLite scenario configuration fields.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2">
              <DisruptionSummary label="Lane Closure" value={scenario.laneClosure} />
              <DisruptionSummary label="Construction" value={scenario.construction} />
              <DisruptionSummary label="Accident" value={scenario.accident} />
              <DisruptionSummary label="Flooding" value={scenario.flooding} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Advanced JSON</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="scenario-json-preview">{scenario.constraintsJson}</pre>
            </CardContent>
          </Card>
        </div>
      </div>
      <SheetFooter className="scenario-sheet-footer">
        <div className="grid grid-cols-2 gap-2">
          <Button onClick={() => onLaunch(scenario, "load")}>
            <PlayIcon data-icon="inline-start" />
            Load
          </Button>
          <Button variant="outline" onClick={() => onLaunch(scenario, "live")}>
            <BoltIcon data-icon="inline-start" />
            Live
          </Button>
          <Button variant="outline" onClick={() => onLaunch(scenario, "record")}>
            <FilmIcon data-icon="inline-start" />
            Record
          </Button>
          <Button variant="outline" onClick={() => onEdit(scenario)}>
            <PencilIcon data-icon="inline-start" />
            Edit
          </Button>
          <Button variant="outline" onClick={() => onArchive(scenario)}>
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

function DisruptionSummary({ label, value }: { label: string; value: DisruptionConfig }) {
  return (
    <div className="scenario-disruption-summary">
      <span>{label}</span>
      <strong>{value.enabled ? "Enabled" : "Disabled"}</strong>
      <small>{value.enabled ? `${value.approach} approach` : "No active disruption"}</small>
    </div>
  )
}

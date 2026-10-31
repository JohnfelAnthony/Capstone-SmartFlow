import * as React from "react"
import { DownloadIcon, FlaskConicalIcon, PlusIcon, RefreshCcwIcon, Trash2Icon } from "lucide-react"
import { listRuns } from "@/api/runs"
import type { SimulationRunRecord } from "@/api/simulation"
import {
  downloadFitRecord, getFitRecord, listFitRecords, rawRunMetrics, saveFitRecord,
  type FitDraft, type FitRecord, type Measurement, type MetricDefinition,
} from "@/api/research"
import { NativeNumber, NativeSelect } from "@/components/native-scenario-controls"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { controlLabel } from "@/lib/control-labels"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

const blankDraft: FitDraft = {
  name: "", site_id: "", purpose: "calibration", source_kind: "observed", source_reference: "",
  source_sha256: "", collection_start: "", collection_end: "", run_id: 0, calibration_id: null,
  measurement_start: 0, measurement_seconds: 0, definitions_confirmed: false, measurements: [],
  parameter_changes: "", notes: "",
}
function measurementFor(metric: MetricDefinition): Measurement {
  return { metric: metric.key, location: metric.key === "local_reference" ? "" : "Whole network",
    definition: metric.definition, unit: metric.key === "local_reference" ? "" : metric.unit,
    observed: 0, tolerance: 0, tolerance_mode: "absolute", simulated: null, simulation_method: "" }
}
function numberText(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : "—"
}
function TextField({ label, value, onChange, description, multiline = false, disabled = false, required = false, maxLength = 1200, placeholder }: {
  label: string; value: string; onChange: (value: string) => void; description?: string; multiline?: boolean;
  disabled?: boolean; required?: boolean; maxLength?: number; placeholder?: string
}) {
  const id = React.useId()
  const props = { id, value, disabled, required, maxLength, placeholder, onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(event.target.value) }
  return <Field data-disabled={disabled}><FieldLabel htmlFor={id}>{label}</FieldLabel>
    {multiline ? <Textarea {...props} rows={3} /> : <Input {...props} />}
    {description && <FieldDescription>{description}</FieldDescription>}
  </Field>
}

export function CalibrationValidationPage({ initialRecordId, canEdit, canExport, onOpenScenarios }: {
  initialRecordId?: number | null; canEdit: boolean; canExport: boolean; onOpenScenarios: () => void
}) {
  const [records, setRecords] = React.useState<FitRecord[]>([])
  const [metrics, setMetrics] = React.useState<MetricDefinition[]>([])
  const [runs, setRuns] = React.useState<SimulationRunRecord[]>([])
  const [draft, setDraft] = React.useState<FitDraft>(blankDraft)
  const [selected, setSelected] = React.useState<FitRecord | null>(null)
  const [tab, setTab] = React.useState(initialRecordId ? "history" : "new")
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [notice, setNotice] = React.useState("")
  const [error, setError] = React.useState("")
  const selectedRun = runs.find((run) => run.id === draft.run_id)
  const runMetrics = selectedRun ? rawRunMetrics(selectedRun) : {}
  const definitionLocked = draft.purpose === "validation"
  const calibrations = records.filter((record) => record.purpose === "calibration")

  React.useEffect(() => {
    let mounted = true
    Promise.all([listFitRecords(), Promise.all(["no-signal", "fixed-time"].map((controlMode) => listRuns({ status: "completed", controlMode, limit: 1000 })))
        .then((lists) => ({ runs: lists.flatMap((list) => list.runs).sort((a, b) => b.id - a.id) })),
      initialRecordId ? getFitRecord(initialRecordId) : Promise.resolve(null)])
      .then(([history, baselines, opened]) => {
        if (!mounted) return
        setRecords(opened && !history.records.some((record) => record.id === opened.id) ? [opened, ...history.records] : history.records)
        setMetrics(history.metrics); setRuns(baselines.runs); setSelected(opened)
        setDraft((current) => current.measurements.length ? current : { ...current, measurements: [measurementFor(history.metrics[0])] })
      }).catch((cause) => { if (mounted) setError(cause instanceof Error ? cause.message : "Unable to load research records.") })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [initialRecordId])

  function update(patch: Partial<FitDraft>) {
    setDraft((current) => ({ ...current, ...patch, definitions_confirmed: false }))
  }
  function updateMeasurement(index: number, patch: Partial<Measurement>) {
    setDraft((current) => ({ ...current, definitions_confirmed: false,
      measurements: current.measurements.map((row, i) => i === index ? { ...row, ...patch } : row) }))
  }
  function selectRun(id: number) {
    const run = runs.find((item) => item.id === id)
    const raw = run ? rawRunMetrics(run) : {}
    update({ run_id: id, measurement_start: Number(raw.measurement_start ?? 0), measurement_seconds: Number(raw.measurement_seconds ?? 0) })
  }
  function selectCalibration(id: number) {
    const parent = records.find((record) => record.id === id)
    update({ calibration_id: id, ...(parent ? { site_id: parent.site_id, source_kind: parent.source_kind,
      measurements: parent.measurements.map((row) => ({ ...row, observed: 0, simulated: null, simulation_method: "" })) } : {}) })
  }
  async function save(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("")
    try {
      const record = await saveFitRecord(draft)
      setRecords((current) => [record, ...current]); setSelected(record); setTab("history")
      setDraft((current) => ({ ...current, definitions_confirmed: false }))
      setNotice(`Saved ${record.purpose} record #${record.id}. Its settings and comparison results are frozen.`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to save comparison.") }
    finally { setSaving(false) }
  }
  async function exportRecord(format: "csv" | "json") {
    if (!selected) return
    setError("")
    try { await downloadFitRecord(selected.id, format); setNotice(`${format.toUpperCase()} exported for record #${selected.id}.`) }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Export failed.") }
  }
  function startValidation(record: FitRecord) {
    setDraft({ ...blankDraft, purpose: "validation", name: `${record.name} — independent validation`, site_id: record.site_id,
      source_kind: record.source_kind, calibration_id: record.id,
      measurements: record.measurements.map((row) => ({ ...row, observed: 0, simulated: null, simulation_method: "" })) })
    setTab("new"); setError(""); setNotice("Enter a new reference source and collection period, then select a baseline with the calibrated settings.")
  }

  return <main className="flex min-w-0 flex-col gap-6 p-4 lg:p-6">
    <div><h1 className="text-2xl font-semibold">Calibration &amp; Validation</h1>
      <p className="text-muted-foreground">Compare simulated runs of the measured condition with measured references, document tuning, and check an independent period.</p></div>
    <Alert><FlaskConicalIcon /><AlertTitle>Evidence before optimization</AlertTitle><AlertDescription>
      Calibration records support parameter review. Validation keeps the calibrated settings and tolerances, using a separate source and period.
      A numerical fit does not establish field accuracy. Synthetic references remain labeled as software fixtures.
    </AlertDescription></Alert>
    {error && <Alert variant="destructive"><AlertTitle>Comparison needs attention</AlertTitle><AlertDescription role="alert">{error}</AlertDescription></Alert>}
    {notice && <Alert><AlertDescription role="status">{notice}</AlertDescription></Alert>}
    {loading ? <Skeleton className="h-48 w-full" /> : <Tabs value={tab} onValueChange={(value) => setTab(String(value))}>
      <TabsList><TabsTrigger value="new">New comparison</TabsTrigger><TabsTrigger value="history">Saved records ({records.length})</TabsTrigger></TabsList>
      <TabsContent value="new" className="mt-4">
        {!canEdit && <Alert className="mb-4"><AlertDescription>Viewing only. Scenario edit permission is required to save a research record.</AlertDescription></Alert>}
        {!runs.length ? <Empty><EmptyHeader><EmptyMedia variant="icon"><FlaskConicalIcon /></EmptyMedia><EmptyTitle>Record a baseline first</EmptyTitle>
          <EmptyDescription>Complete a no-signal recording (or a fixed-time one where the site has a signal) in Scenarios. It will provide saved metrics and reproducible settings for comparison.</EmptyDescription></EmptyHeader><EmptyContent><Button onClick={onOpenScenarios}>Open Scenarios</Button></EmptyContent></Empty> :
          <form onSubmit={save} className="flex flex-col gap-6">
            <Card><CardHeader><CardTitle>1. Reference and purpose</CardTitle><CardDescription>Use a stable study-site identifier and cite the recording or reviewed observation sheet.</CardDescription></CardHeader>
              <CardContent><FieldGroup className="grid md:grid-cols-2">
                <Field><FieldLabel>Purpose</FieldLabel><ToggleGroup variant="outline" value={[draft.purpose]} onValueChange={(values) => values[0] && update({ purpose: values[0] as FitDraft["purpose"], calibration_id: null })} aria-label="Comparison purpose"><ToggleGroupItem value="calibration">Calibration</ToggleGroupItem><ToggleGroupItem value="validation">Validation</ToggleGroupItem></ToggleGroup></Field>
                <Field><FieldLabel>Reference type</FieldLabel><ToggleGroup disabled={definitionLocked} variant="outline" value={[draft.source_kind]} onValueChange={(values) => values[0] && update({ source_kind: values[0] as FitDraft["source_kind"] })} aria-label="Reference type"><ToggleGroupItem value="observed">Field observation</ToggleGroupItem><ToggleGroupItem value="synthetic">Synthetic fixture</ToggleGroupItem></ToggleGroup></Field>
                {definitionLocked && <NativeSelect label="Calibration record" value={String(draft.calibration_id ?? "")} options={[{ value: "", label: "Choose a saved calibration" }, ...calibrations.map((record) => ({ value: String(record.id), label: `#${record.id} · ${record.name} · ${record.site_id}` }))]} onChange={(value) => selectCalibration(Number(value))} />}
                <TextField label="Record name" value={draft.name} onChange={(name) => update({ name })} required maxLength={160} />
                <TextField label="Study site" value={draft.site_id} onChange={(site_id) => update({ site_id })} required disabled={definitionLocked} maxLength={160} placeholder="Site and direction/corridor ID" />
                <TextField label="Reference source" value={draft.source_reference} onChange={(source_reference) => update({ source_reference })} required placeholder="Recording ID, sheet version, reviewer and extraction method" />
                <TextField label="Source SHA256 (optional)" value={draft.source_sha256} onChange={(source_sha256) => update({ source_sha256 })} maxLength={64} description="Record the source file hash when available. Files are not uploaded here." />
                <TextField label="Collection start" value={draft.collection_start} onChange={(collection_start) => update({ collection_start })} required maxLength={80} placeholder="2026-10-04T07:00:00+08:00" description="ISO timestamp with UTC offset. This marks t=0, before any warmup." />
                <TextField label="Collection end" value={draft.collection_end} onChange={(collection_end) => update({ collection_end })} required maxLength={80} placeholder="2026-10-04T08:00:00+08:00" description="The recording must cover warmup and the measured period." />
              </FieldGroup></CardContent></Card>
            <Card><CardHeader><CardTitle>2. Simulated run of the measured condition</CardTitle><CardDescription>For a site without a traffic light, choose its no-signal run. Values come from the saved run. Edit scenario settings and record another run to test a parameter change.</CardDescription></CardHeader>
              <CardContent className="flex flex-col gap-4"><FieldGroup><NativeSelect label="Completed baseline run" value={String(draft.run_id || "")} options={[{ value: "", label: "Choose a completed no-signal or fixed-time run" }, ...runs.map((run) => ({ value: String(run.id), label: `Run #${run.id} · ${controlLabel(run.control_mode)} · scenario #${run.scenario_id ?? "—"} · ${run.start_time}` }))]} onChange={(value) => selectRun(Number(value))} /></FieldGroup>
                {selectedRun && <><dl className="grid grid-cols-2 gap-3 md:grid-cols-4"><dt>Measurement start</dt><dd>{numberText(runMetrics.measurement_start)} s</dd><dt>Measured duration</dt><dd>{numberText(runMetrics.measurement_seconds)} s</dd><dt>Pending vehicles</dt><dd>{numberText(runMetrics.pending_demand)}</dd><dt>Unfinished vehicles</dt><dd>{numberText(runMetrics.unfinished_vehicles)}</dd></dl>
                  <FieldDescription>Count, wait, queue and travel-time metrics use different populations. Match the definition below; a local stop-line count is not network throughput.</FieldDescription></>}
                <Button variant="outline" type="button" onClick={onOpenScenarios}>Open scenario library</Button>
              </CardContent></Card>
            <Card><CardHeader><CardTitle>3. Matched measurements</CardTitle><CardDescription>Enter observed values and choose tolerances before validation. Use local/custom measurements for a single stop line, approach or queue snapshot.</CardDescription></CardHeader>
              <CardContent className="flex flex-col gap-6">{draft.measurements.map((row, index) => <FieldGroup key={index} className="grid md:grid-cols-2">
                <NativeSelect label={`Measure ${index + 1}`} value={row.metric} options={metrics.map((metric) => ({ value: metric.key, label: metric.label }))} disabled={definitionLocked} onChange={(key) => { const metric = metrics.find((item) => item.key === key); if (metric) updateMeasurement(index, measurementFor(metric)) }} />
                <TextField label={`Location ${index + 1}`} value={row.location} onChange={(location) => updateMeasurement(index, { location })} required disabled={definitionLocked} maxLength={180} />
                <TextField label={`Definition ${index + 1}`} value={row.definition} onChange={(definition) => updateMeasurement(index, { definition })} multiline required disabled={definitionLocked} />
                <TextField label={`Unit ${index + 1}`} value={row.unit} onChange={(unit) => updateMeasurement(index, { unit })} required disabled={definitionLocked || row.metric !== "local_reference"} maxLength={60} />
                <NativeNumber label={`Observed value ${index + 1}`} value={row.observed} onChange={(observed) => updateMeasurement(index, { observed })} max={1e12} step={.001} />
                <Field><FieldLabel>Simulated value</FieldLabel><p>{row.metric === "local_reference" ? "Enter a matched extraction below." : `${numberText(runMetrics[row.metric])} ${row.unit}`}</p><FieldDescription>{metrics.find((metric) => metric.key === row.metric)?.definition}</FieldDescription></Field>
                <Field><FieldLabel>Tolerance basis</FieldLabel><ToggleGroup disabled={definitionLocked} variant="outline" value={[row.tolerance_mode]} onValueChange={(values) => values[0] && updateMeasurement(index, { tolerance_mode: values[0] as Measurement["tolerance_mode"] })} aria-label={`Tolerance basis ${index + 1}`}><ToggleGroupItem value="absolute">Absolute</ToggleGroupItem><ToggleGroupItem value="percent">Percent</ToggleGroupItem></ToggleGroup></Field>
                <NativeNumber label={`Tolerance ${index + 1} (${row.tolerance_mode === "percent" ? "%" : row.unit})`} value={row.tolerance} onChange={(tolerance) => updateMeasurement(index, { tolerance })} max={1e12} step={.001} disabled={definitionLocked} />
                {row.metric === "local_reference" && <><Field><FieldLabel htmlFor={`local-value-${index}`}>Simulated local value {index + 1}</FieldLabel><Input id={`local-value-${index}`} type="number" min={0} step="any" required value={row.simulated ?? ""} onChange={(event) => updateMeasurement(index, { simulated: event.target.value === "" ? null : Number(event.target.value) })} /></Field>
                  <TextField label={`Simulation extraction method ${index + 1}`} value={row.simulation_method} onChange={(simulation_method) => updateMeasurement(index, { simulation_method })} required multiline placeholder="Timeline frames, approach ID, sample times and calculation" /></>}
                {!definitionLocked && <Button variant="ghost" type="button" disabled={draft.measurements.length === 1} onClick={() => update({ measurements: draft.measurements.filter((_, i) => i !== index) })}><Trash2Icon data-icon="inline-start" />Remove measure {index + 1}</Button>}
              </FieldGroup>)}
                {!definitionLocked && <Button variant="outline" type="button" disabled={draft.measurements.length >= 50} onClick={() => update({ measurements: [...draft.measurements, measurementFor(metrics[0])] })}><PlusIcon data-icon="inline-start" />Add measurement</Button>}
              </CardContent></Card>
            <Card><CardHeader><CardTitle>4. Tuning and review notes</CardTitle><CardDescription>Record the before/after values and reason for each iteration. Saving adds an immutable record; scenario settings are edited in Scenarios.</CardDescription></CardHeader>
              <CardContent><FieldGroup>
                <TextField label="Parameter changes and rationale" multiline value={draft.parameter_changes} onChange={(parameter_changes) => update({ parameter_changes })} maxLength={6000} placeholder="Green time: 30 → 35 s; reason, prior record ID and expected effect" />
                <TextField label="Reference quality and review notes" multiline value={draft.notes} onChange={(notes) => update({ notes })} maxLength={6000} placeholder="Visibility, sampling, excluded events, reviewer and limitations" />
                <Field orientation="horizontal"><Checkbox id="matched-measurements" checked={draft.definitions_confirmed} onCheckedChange={(checked) => setDraft((current) => ({ ...current, definitions_confirmed: checked }))} /><FieldLabel htmlFor="matched-measurements">I checked matching locations, populations, units, definitions and measurement windows.</FieldLabel></Field>
                <Button type="submit" disabled={!canEdit || saving || !draft.run_id || !draft.definitions_confirmed || (definitionLocked && !draft.calibration_id)}>{saving ? "Saving comparison…" : `Save ${draft.purpose} record`}</Button>
              </FieldGroup></CardContent></Card>
          </form>}
      </TabsContent>
      <TabsContent value="history" className="mt-4"><div className="flex flex-col gap-6">
        {!records.length ? <Empty><EmptyHeader><EmptyTitle>No saved comparisons yet</EmptyTitle><EmptyDescription>Save a baseline comparison to begin a documented calibration history.</EmptyDescription></EmptyHeader><EmptyContent><Button onClick={() => setTab("new")}>New comparison</Button></EmptyContent></Empty> : <Card><CardHeader><CardTitle>Comparison history</CardTitle><CardDescription>Latest 200 records. Search finds older records by name or site.</CardDescription></CardHeader><CardContent>
          <Table><TableHeader><TableRow><TableHead>Record</TableHead><TableHead>Site / purpose</TableHead><TableHead>Reference</TableHead><TableHead>Fit check</TableHead><TableHead>Review</TableHead></TableRow></TableHeader><TableBody>{records.map((record) => <TableRow key={record.id} data-state={selected?.id === record.id ? "selected" : undefined}><TableCell>#{record.id} · {record.name}</TableCell><TableCell>{record.site_id}<br />{record.purpose}</TableCell><TableCell><Badge variant="outline">{record.source_kind === "synthetic" ? "Synthetic fixture" : "Declared observation"}</Badge></TableCell><TableCell><Badge variant={record.within_tolerance ? "secondary" : "destructive"}>{record.within_tolerance ? "Within tolerance" : "Outside tolerance"}</Badge></TableCell><TableCell><Button variant="outline" size="sm" onClick={() => setSelected(record)}>View record #{record.id}</Button></TableCell></TableRow>)}</TableBody></Table>
        </CardContent></Card>}
        {selected && <Card><CardHeader><CardTitle>Record #{selected.id}: {selected.name}</CardTitle><CardDescription>{selected.purpose} · {selected.site_id} · {selected.created_at} · saved by user #{selected.created_by ?? "deleted"}</CardDescription></CardHeader><CardContent className="flex flex-col gap-5">
          <Alert><AlertTitle>{selected.source_kind === "synthetic" ? "Synthetic software fixture" : "Researcher-declared field reference"}</AlertTitle><AlertDescription>{selected.assessment}</AlertDescription></Alert>
          <dl className="grid grid-cols-1 gap-2 break-words md:grid-cols-2"><dt>Reference source</dt><dd>{selected.source_reference}</dd><dt>Collection period</dt><dd>{selected.collection_start} → {selected.collection_end}</dd><dt>Baseline run / seed</dt><dd>#{selected.run_id} / {selected.snapshot.seed ?? "—"}</dd><dt>Measurement window</dt><dd>{numberText(selected.measurement_start)} s start · {numberText(selected.measurement_seconds)} s duration</dd><dt>Engine / network</dt><dd>{String(selected.snapshot.experiment.engine_version)} / {String(selected.snapshot.experiment.network_id)}</dd><dt>Network SHA256</dt><dd className="break-all">{String(selected.snapshot.experiment.network_sha256)}</dd>{selected.calibration_id && <><dt>Calibrated settings</dt><dd>Record #{selected.calibration_id}</dd></>}</dl>
          <Table><TableHeader><TableRow><TableHead>Measurement</TableHead><TableHead>Observed</TableHead><TableHead>Simulated</TableHead><TableHead>Sim − obs</TableHead><TableHead>Absolute error</TableHead><TableHead>Error %</TableHead><TableHead>Tolerance / result</TableHead></TableRow></TableHeader><TableBody>{selected.comparisons.map((row, index) => <TableRow key={index}><TableCell><p>{row.metric} · {row.location}</p><p className="text-muted-foreground">{row.definition}</p>{row.simulation_method && <p>{row.simulation_method}</p>}</TableCell><TableCell>{numberText(row.observed)} {row.unit}</TableCell><TableCell>{numberText(row.simulated)} {row.unit}</TableCell><TableCell>{numberText(row.difference)}</TableCell><TableCell>{numberText(row.absolute_error)}</TableCell><TableCell>{row.percent_error === null ? "Undefined: zero reference" : `${numberText(row.percent_error)}%`}</TableCell><TableCell>{row.tolerance} {row.tolerance_mode === "percent" ? "%" : row.unit}<br /><Badge variant={row.within_tolerance ? "secondary" : "destructive"}>{row.within_tolerance ? "Within tolerance" : "Outside tolerance"}</Badge></TableCell></TableRow>)}</TableBody></Table>
          <div className="flex flex-col gap-2"><p className="whitespace-pre-wrap">Parameter changes: {selected.parameter_changes || "None recorded"}</p><p className="whitespace-pre-wrap">Review notes: {selected.notes || "None recorded"}</p></div>
          <div className="flex flex-wrap gap-3"><Button variant="outline" disabled={!canExport} onClick={() => void exportRecord("csv")}><DownloadIcon data-icon="inline-start" />Export CSV</Button><Button variant="outline" disabled={!canExport} onClick={() => void exportRecord("json")}><DownloadIcon data-icon="inline-start" />Export JSON</Button>{selected.purpose === "calibration" && <Button disabled={!canEdit} onClick={() => startValidation(selected)}><RefreshCcwIcon data-icon="inline-start" />Validate on independent reference</Button>}</div>
          {!canExport && <FieldDescription>Run-report export permission is required to download records.</FieldDescription>}
        </CardContent></Card>}
      </div></TabsContent>
    </Tabs>}
  </main>
}

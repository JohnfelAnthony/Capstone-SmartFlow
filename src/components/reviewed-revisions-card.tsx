import * as React from "react"
import { API_BASE_URL, apiRequest } from "@/api/client"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { DesktopSiteValidationCard } from "@/components/desktop-site-validation-card"
import { DesktopStudyInputsCard } from "@/components/desktop-study-inputs-card"

type Revision = { id: string; revision?: string; survey_id?: string; take_id?: string; publication_status?: string; error?: string | null }
type ConversionPreview = {
  message: string
  network_id: string
  network_sha256: string
  summary: { trips: number; by_class: Record<string, number>; excluded_by_class: Record<string, number>; pedestrian_starts: number; travel_time_follow_up: string }
  timing: { measurement_start_s: number; measurement_duration_s: number; demand_end_s: number }
  provenance: { mapping_sha256: string; manifest_sha256: string }
}

export function ReviewedRevisionsCard() {
  const [file, setFile] = React.useState<File | null>(null)
  const [revisions, setRevisions] = React.useState<Revision[]>([])
  const [message, setMessage] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [selected, setSelected] = React.useState("")
  const [mapping, setMapping] = React.useState<File | null>(null)
  const [origin, setOrigin] = React.useState("0")
  const [start, setStart] = React.useState("0")
  const [end, setEnd] = React.useState("")
  const [preview, setPreview] = React.useState<ConversionPreview | null>(null)
  const [previewBusy, setPreviewBusy] = React.useState(false)
  const [scenarioName, setScenarioName] = React.useState("")
  const [collectedOn, setCollectedOn] = React.useState("")
  const [sourceKind, setSourceKind] = React.useState("")
  const [creating, setCreating] = React.useState(false)
  const [scenarioRefresh, setScenarioRefresh] = React.useState(0)
  const requestVersion = React.useRef(0)

  function clearPreview() { requestVersion.current++; setPreview(null); setPreviewBusy(false); setMessage("") }

  const refresh = React.useCallback(async () => {
    const result = await apiRequest<{ revisions: Revision[] }>("/api/desktop/reviewed-revisions")
    setRevisions(result.revisions)
  }, [])

  React.useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) void refresh().catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Unable to load reviewed revisions.")) })
    return () => { active = false }
  }, [refresh])

  async function upload() {
    if (!file) return
    if (file.size > 32 * 1024 * 1024) {
      setMessage("The ZIP must be 32 MB or smaller.")
      return
    }
    setBusy(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/desktop/reviewed-revisions`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/zip" }, body: file,
      })
      const result = await response.json()
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Import failed.")
      setFile(null)
      await refresh()
      setMessage(result.message)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to import the ZIP.")
    } finally {
      setBusy(false)
    }
  }

  async function previewConversion() {
    if (!selected || !mapping) return
    const version = requestVersion.current
    setPreviewBusy(true); setPreview(null); setMessage("")
    try {
      if (mapping.size > 2 * 1024 * 1024) throw new Error("The mapping must be 2 MB or smaller.")
      const parsed: unknown = JSON.parse(await mapping.text())
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Choose a site mapping JSON object.")
      if (![origin, start, end].every((value) => value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0)) throw new Error("Enter non-negative video times in seconds.")
      const result = await apiRequest<ConversionPreview>(`/api/desktop/reviewed-revisions/${encodeURIComponent(selected)}/conversion-preview`, {
        method: "POST", body: { mapping: parsed, origin_s: Number(origin), start_s: Number(start), end_s: Number(end) },
      })
      if (requestVersion.current === version) setPreview(result)
    } catch (error) {
      if (requestVersion.current === version) setMessage(error instanceof Error ? error.message : "Unable to preview conversion.")
    } finally {
      if (requestVersion.current === version) setPreviewBusy(false)
    }
  }

  async function createScenario() {
    if (!preview || !mapping || !selected) return
    const version = requestVersion.current
    setCreating(true); setMessage("")
    try {
      const parsed: unknown = JSON.parse(await mapping.text())
      const response = await apiRequest<{ scenario_id: number; message: string; audit_warning?: string }>(`/api/desktop/reviewed-revisions/${encodeURIComponent(selected)}/create-scenario`, {
        method: "POST", body: { mapping: parsed, origin_s: Number(origin), start_s: Number(start), end_s: Number(end),
          name: scenarioName, collected_on: collectedOn, source_kind: sourceKind,
          expected_network_sha256: preview.network_sha256, expected_mapping_sha256: preview.provenance.mapping_sha256,
          expected_manifest_sha256: preview.provenance.manifest_sha256 },
      })
      if (requestVersion.current === version) { setPreview(null); setScenarioRefresh((value) => value + 1); setMessage(`${response.message} Scenario #${response.scenario_id}.${response.audit_warning ? ` ${response.audit_warning}` : ""}`) }
    } catch (error) {
      if (requestVersion.current === version) setMessage(error instanceof Error ? error.message : "Unable to create the scenario.")
    } finally {
      setCreating(false)
    }
  }

  return <><Card><CardHeader><CardTitle>Reviewed Field Observer revisions</CardTitle>
    <CardDescription>Import the reviewed ZIP exported by Field Observer. Its files and manifest are preserved in local data and backups. Import does not validate the site or enable training.</CardDescription></CardHeader>
    <CardContent className="flex flex-col gap-3">
      {message && <Alert><AlertDescription role="status">{message}</AlertDescription></Alert>}
      <label htmlFor="reviewed-zip" className="text-sm font-medium">Reviewed revision ZIP</label>
      <Input id="reviewed-zip" type="file" accept=".zip,application/zip" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      <Button className="self-start" onClick={() => void upload()} disabled={!file || busy}>{busy ? "Checking…" : "Import reviewed ZIP"}</Button>
      <div><strong className="text-sm">Retained revisions ({revisions.length})</strong>
        {revisions.length > 0 && <ul className="mt-2 space-y-1 text-sm">{revisions.map((revision) => <li key={revision.id}>
          {revision.error ? `Needs attention: ${revision.error}` : `${revision.survey_id || "Survey not named"} · ${revision.take_id || "Take not named"} · ${revision.revision || "Revision"} · ${revision.publication_status || "status not supplied"}`}
        </li>)}</ul>}</div>
      <FieldGroup><Field><FieldLabel htmlFor="conversion-revision">Revision to preview</FieldLabel>
        <select id="conversion-revision" disabled={creating} className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={selected} onChange={(event) => { clearPreview(); setSelected(event.target.value) }}>
          <option value="">Select a reviewed revision</option>
          {revisions.filter((revision) => !revision.error).map((revision) => <option key={revision.id} value={revision.id}>{revision.survey_id || "Unnamed survey"} · {revision.take_id || "Unnamed take"} · {revision.revision || revision.id}</option>)}
        </select></Field>
        <Field><FieldLabel htmlFor="conversion-mapping">Reviewed site mapping JSON</FieldLabel><Input id="conversion-mapping" disabled={creating} type="file" accept=".json,application/json" onChange={(event) => { clearPreview(); setMapping(event.target.files?.[0] ?? null) }} /></Field>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field><FieldLabel htmlFor="conversion-origin">Origin (video seconds)</FieldLabel><Input id="conversion-origin" disabled={creating} type="number" min="0" step="any" value={origin} onChange={(event) => { clearPreview(); setOrigin(event.target.value) }} /></Field>
          <Field><FieldLabel htmlFor="conversion-start">Window start (seconds)</FieldLabel><Input id="conversion-start" disabled={creating} type="number" min="0" step="any" value={start} onChange={(event) => { clearPreview(); setStart(event.target.value) }} /></Field>
          <Field><FieldLabel htmlFor="conversion-end">Window end (seconds)</FieldLabel><Input id="conversion-end" disabled={creating} type="number" min="0" step="any" value={end} onChange={(event) => { clearPreview(); setEnd(event.target.value) }} /></Field>
        </div>
        <Button variant="outline" className="self-start" disabled={!selected || !mapping || previewBusy || creating} onClick={() => void previewConversion()}>{previewBusy ? "Checking…" : "Preview demand conversion"}</Button>
      </FieldGroup>
      {preview && <div className="flex flex-col gap-1 rounded-md border p-3 text-sm" role="status">
        <p>{preview.message}</p><p>Site: {preview.network_id}. Vehicles: {preview.summary.trips}; pedestrian starts: {preview.summary.pedestrian_starts}.</p>
        <p>Vehicle classes: {Object.entries(preview.summary.by_class).map(([name, count]) => `${name}: ${count}`).join(", ") || "none"}.</p>
        {preview.summary.pedestrian_starts > 0 && <p>Pedestrian starts are grouped into 60-second bins and distributed evenly within each bin.</p>}
        <p>Excluded: {Object.entries(preview.summary.excluded_by_class).map(([name, count]) => `${name}: ${count}`).join(", ") || "none"}.</p>
        <p>Measurement starts at {preview.timing.measurement_start_s} s and lasts {preview.timing.measurement_duration_s} s; follow-up: {preview.summary.travel_time_follow_up}.</p>
        <p className="break-all">Mapping fingerprint: {preview.provenance.mapping_sha256}</p>
        <FieldGroup><Field><FieldLabel htmlFor="conversion-name">New scenario name</FieldLabel><Input id="conversion-name" value={scenarioName} maxLength={150} onChange={(event) => setScenarioName(event.target.value)} /></Field>
          <Field><FieldLabel htmlFor="conversion-date">Collection date</FieldLabel><Input id="conversion-date" type="date" value={collectedOn} onChange={(event) => setCollectedOn(event.target.value)} /></Field>
          <Field><FieldLabel htmlFor="conversion-source">Evidence type</FieldLabel><select id="conversion-source" className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={sourceKind} onChange={(event) => setSourceKind(event.target.value)}>
            <option value="">Choose the source type</option><option value="observed">Reviewed field observations</option><option value="synthetic">Synthetic test data</option></select></Field>
          <Button className="self-start" disabled={creating || !scenarioName.trim() || !collectedOn || !sourceKind} onClick={() => void createScenario()}>{creating ? "Creating…" : "Create provisional scenario"}</Button>
        </FieldGroup>
      </div>}
    </CardContent></Card><DesktopStudyInputsCard /><DesktopSiteValidationCard revisions={revisions} refreshKey={scenarioRefresh} /></>
}

import * as React from "react"

import { importFieldObserverCounts, type FieldCountsSummary, type NativeScenarioConfig } from "@/api/native-scenario"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const FILES = ["manifest.json", "events.csv", "coverage.csv", "reviewed_bins.csv", "lines.json"]

type Preview = { engineConfig: NativeScenarioConfig; summary: FieldCountsSummary; source: string }

/** "Import counts from Field Observer": the five files of a reviewed revision become the scenario's demand. The user sees what was
 * read before anything is applied, and nothing is saved until the scenario is. */
export function FieldCountsImport({ networkId, config, disabled, onUse }: {
  networkId: string; config: NativeScenarioConfig; disabled: boolean; onUse: (config: NativeScenarioConfig, notice: string) => void
}) {
  const [busy, setBusy] = React.useState(false)
  const [problem, setProblem] = React.useState("")
  const [preview, setPreview] = React.useState<Preview | null>(null)

  async function choose(list: FileList | null) {
    if (!list?.length) return
    setBusy(true)
    setProblem("")
    setPreview(null)
    try {
      const files: Record<string, string> = {}
      for (const file of Array.from(list)) if (FILES.includes(file.name)) files[file.name] = await file.text()
      const missing = FILES.filter((name) => !(name in files))
      if (missing.length) throw new Error(`Choose all five files of the revision together. Missing: ${missing.join(", ")}.`)
      const response = await importFieldObserverCounts({ network_id: networkId, engine_config: config, files })
      setPreview({ engineConfig: response.engine_config, summary: response.summary, source: `${response.summary.source.take_id} ${response.summary.source.revision}` })
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "Unable to read the Field Observer export.")
    } finally {
      setBusy(false)
    }
  }

  const summary = preview?.summary
  return <Field>
    <FieldLabel htmlFor="field-counts-files">Import counts from Field Observer (optional)</FieldLabel>
    <Input id="field-counts-files" type="file" multiple accept=".csv,.json,text/csv,application/json" disabled={disabled || busy}
      onChange={(event) => { void choose(event.target.files); event.target.value = "" }} />
    <FieldDescription>
      Open the reviewed revision folder and select its five files together: {FILES.join(", ")}. Counts per class, approach and turn, in the export's time bins,
      replace this scenario's vehicle demand. An incomplete bin is refused, never read as zero. The scenario's approach names are south, north, east and west; the
      export's counting lines must use them.
    </FieldDescription>
    {busy && <p role="status" className="text-sm">Reading the export...</p>}
    {problem && <Alert variant="destructive"><AlertDescription>{problem}</AlertDescription></Alert>}
    {summary && preview && <section aria-label="Counts read from Field Observer" className="mt-2 flex flex-col gap-3 rounded-md border p-3 text-sm">
      <p><strong>{summary.vehicles} vehicles</strong> over {Math.round(summary.span_seconds)} s in {summary.bins} bin(s) of {summary.bin_seconds} s
        ({summary.vehicles_per_hour} per hour), from {preview.source}. They are not saved until you save the scenario. The counts cover the first {Math.round(summary.span_seconds)} s
        of a run; no vehicles arrive after that, so use a run no longer than this.</p>
      <Table>
        <TableHeader><TableRow><TableHead>Approach</TableHead><TableHead>Class</TableHead><TableHead className="text-right">Vehicles</TableHead></TableRow></TableHeader>
        <TableBody>{Object.entries(summary.by_approach_class).flatMap(([approach, classes]) => Object.entries(classes).map(([kind, count]) =>
          <TableRow key={`${approach}-${kind}`}><TableCell>{approach}</TableCell><TableCell>{kind}</TableCell><TableCell className="text-right">{count}</TableCell></TableRow>))}</TableBody>
      </Table>
      <p>Turns: {Object.entries(summary.turns).map(([turn, count]) => `${turn} ${count}`).join("; ")}.</p>
      {summary.class_mapping.filter((item) => item.pending_team_decision).map((item) =>
        <Alert key={item.field_class}><AlertDescription><strong>{item.field_class}</strong> ({item.vehicles}): {item.note}</AlertDescription></Alert>)}
      {Object.keys(summary.not_simulated).length > 0 && <p>Not simulated, left out: {Object.entries(summary.not_simulated).map(([kind, count]) => `${kind} ${count}`).join(", ")}.</p>}
      {summary.not_counted_at_the_end > 0 && <p>{summary.not_counted_at_the_end} vehicle(s) that arrived in the last minute of the footage had no exit yet and are not counted.</p>}
      <p className="text-muted-foreground">{summary.limits}</p>
      <div className="flex gap-2">
        <Button type="button" size="sm" onClick={() => { onUse(preview.engineConfig, `${summary.vehicles} vehicles from ${preview.source}. Save the scenario to keep them.`); setPreview(null) }}>Use these counts</Button>
        <Button type="button" size="sm" variant="outline" onClick={() => setPreview(null)}>Discard</Button>
      </div>
    </section>}
  </Field>
}

import * as React from "react"
import { apiRequest } from "@/api/client"
import { listScenarios, type ApiScenario } from "@/api/scenarios"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type Revision = { id: string; revision?: string; survey_id?: string; take_id?: string; error?: string | null }
type Job = { id: string; status: "running" | "completed" | "failed" | "interrupted"; site: string; purpose: string; error: string | null; persistence_warning?: string;
  result: null | { status: string; report_file: string; gate: { open: boolean; reasons: string[] }; decision: { reasons: string[] } } }

export function DesktopSiteValidationCard({ revisions, refreshKey }: { revisions: Revision[]; refreshKey: number }) {
  const [scenarios, setScenarios] = React.useState<ApiScenario[]>([])
  const [scenarioId, setScenarioId] = React.useState("")
  const [revisionId, setRevisionId] = React.useState("")
  const [purpose, setPurpose] = React.useState("calibration")
  const [origin, setOrigin] = React.useState("0")
  const [start, setStart] = React.useState("0")
  const [end, setEnd] = React.useState("")
  const [jobs, setJobs] = React.useState<Job[]>([])
  const [error, setError] = React.useState("")
  const [submitting, setSubmitting] = React.useState(false)
  const running = jobs.some((job) => job.status === "running")

  React.useEffect(() => {
    let active = true
    void listScenarios().then((response) => { if (active) setScenarios(response.scenarios.filter((scenario) => scenario.network_id === "tagum_site_a" || scenario.network_id === "tagum_site_b")) })
      .catch((cause: unknown) => { if (active) setError(cause instanceof Error ? cause.message : "Unable to load scenarios.") })
    return () => { active = false }
  }, [refreshKey])

  React.useEffect(() => {
    let active = true
    async function refresh() {
      try {
        const result = await apiRequest<{ jobs: Job[] }>("/api/desktop/site-validation-jobs")
        if (active) setJobs(result.jobs)
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : "Unable to load validation jobs.") }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  async function startValidation() {
    if (![origin, start, end].every((value) => value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0)) {
      setError("Enter non-negative video times in seconds."); return
    }
    setSubmitting(true); setError("")
    try {
      const job = await apiRequest<Job>("/api/desktop/site-validation-jobs", { method: "POST", body: {
        scenario_id: Number(scenarioId), revision_id: revisionId, purpose,
        origin_s: Number(origin), start_s: Number(start), end_s: Number(end),
      } })
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)])
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to start validation.") }
    finally { setSubmitting(false) }
  }

  return <Card><CardHeader><CardTitle>Site validation job</CardTitle><CardDescription>Runs the no-signal model against a reviewed revision using the saved site mapping and pre-registered criteria. Independent validation also requires the site ledger and a held-out recording. No values are invented when evidence is missing.</CardDescription></CardHeader>
    <CardContent className="flex flex-col gap-4">
      <Alert><AlertDescription>Prepare the site's mapping, validation criteria and independence ledger in the desktop study data before starting. A calibration or synthetic test cannot open the independent-validation gate. Validation can take considerable time and occupies the simulation workload.</AlertDescription></Alert>
      {error && <Alert variant="destructive"><AlertDescription role="alert">{error}</AlertDescription></Alert>}
      <FieldGroup><Field><FieldLabel htmlFor="validation-scenario">Scenario</FieldLabel><select id="validation-scenario" className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}><option value="">Select a study-site scenario</option>{scenarios.map((scenario) => <option key={scenario.id} value={scenario.id}>{scenario.name} · {scenario.network_id}</option>)}</select></Field>
        <Field><FieldLabel htmlFor="validation-revision">Reviewed revision</FieldLabel><select id="validation-revision" className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={revisionId} onChange={(event) => setRevisionId(event.target.value)}><option value="">Select a reviewed revision</option>{revisions.filter((revision) => !revision.error).map((revision) => <option key={revision.id} value={revision.id}>{revision.survey_id || "Unnamed survey"} · {revision.take_id || "Unnamed take"} · {revision.revision || revision.id}</option>)}</select></Field>
        <Field><FieldLabel htmlFor="validation-purpose">Purpose</FieldLabel><select id="validation-purpose" className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={purpose} onChange={(event) => setPurpose(event.target.value)}><option value="calibration">Calibration / development</option><option value="validation">Independent validation</option></select></Field>
        <div className="grid gap-3 sm:grid-cols-3"><Field><FieldLabel htmlFor="validation-origin">Origin (video seconds)</FieldLabel><Input id="validation-origin" type="number" min="0" step="any" value={origin} onChange={(event) => setOrigin(event.target.value)} /></Field>
          <Field><FieldLabel htmlFor="validation-start">Window start (seconds)</FieldLabel><Input id="validation-start" type="number" min="0" step="any" value={start} onChange={(event) => setStart(event.target.value)} /></Field>
          <Field><FieldLabel htmlFor="validation-end">Window end (seconds)</FieldLabel><Input id="validation-end" type="number" min="0" step="any" value={end} onChange={(event) => setEnd(event.target.value)} /></Field></div>
        <Button className="self-start" disabled={!scenarioId || !revisionId || submitting || running} onClick={() => void startValidation()}>{submitting ? "Starting…" : running ? "Validation running…" : "Run site check"}</Button>
      </FieldGroup>
      {jobs.map((job) => <div key={job.id} className="rounded-md border p-3 text-sm" role="status"><p>{job.site} · {job.purpose} · {job.status}</p>
        {job.error && <p>{job.error}</p>}{job.persistence_warning && <p>{job.persistence_warning}</p>}{job.result && <><p>Result: {job.result.status}. Independent gate: {job.result.gate.open ? "open" : "closed"}.</p><p>Report: {job.result.report_file}</p>
          <ul>{[...job.result.decision.reasons, ...job.result.gate.reasons].map((reason, index) => <li key={index}>{reason}</li>)}</ul></>}</div>)}
    </CardContent></Card>
}

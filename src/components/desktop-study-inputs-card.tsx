import * as React from "react"
import { apiRequest } from "@/api/client"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

type Kind = "mapping" | "criteria" | "ledger"
type InputStatus = { filename: string; sha256: string | null }
type Status = { inputs: Record<Kind, InputStatus> }

export function DesktopStudyInputsCard() {
  const [site, setSite] = React.useState("tagum_site_a")
  const [kind, setKind] = React.useState<Kind>("mapping")
  const [file, setFile] = React.useState<File | null>(null)
  const [status, setStatus] = React.useState<Status | null>(null)
  const [message, setMessage] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [refresh, setRefresh] = React.useState(0)

  React.useEffect(() => {
    let active = true
    void apiRequest<Status>(`/api/desktop/study-inputs/${site}`).then((result) => { if (active) setStatus(result) })
      .catch((error: unknown) => { if (active) setMessage(error instanceof Error ? error.message : "Could not read study inputs.") })
    return () => { active = false }
  }, [site, refresh])

  async function importFile() {
    if (!file || !status) return
    if (!window.confirm(`Import ${kind} for ${site}? Previous input is retained. This can change which validation reports are current.`)) return
    setBusy(true); setMessage("")
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error("The JSON file must be 2 MB or smaller.")
      const parsed: unknown = JSON.parse(await file.text())
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Choose a JSON object.")
      const result = await apiRequest<{ message: string; audit_warning?: string }>(`/api/desktop/study-inputs/${site}/${kind}`, {
        method: "POST", body: { document: parsed, expected_sha256: status.inputs[kind].sha256 },
      })
      setFile(null); setStatus(null); setRefresh((value) => value + 1)
      setMessage(`${result.message}${result.audit_warning ? ` ${result.audit_warning}` : ""}`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not import the study input.")
      setStatus(null); setRefresh((value) => value + 1)
    } finally { setBusy(false) }
  }

  return <Card><CardHeader><CardTitle>Study inputs</CardTitle><CardDescription>Import the reviewed site mapping, adviser-approved criteria and independence ledger as JSON. Importing them does not verify their accuracy or establish independence.</CardDescription></CardHeader>
    <CardContent className="flex flex-col gap-4">
      <Alert><AlertDescription>Changing these inputs can make earlier validation results stale. The previous file is retained in desktop backups. Criteria imports update only the selected site.</AlertDescription></Alert>
      {message && <Alert><AlertDescription role="status">{message}</AlertDescription></Alert>}
      <FieldGroup><Field><FieldLabel htmlFor="study-input-site">Site</FieldLabel><select id="study-input-site" disabled={busy} className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={site} onChange={(event) => { setStatus(null); setSite(event.target.value); setMessage("") }}><option value="tagum_site_a">Site A</option><option value="tagum_site_b">Site B</option></select></Field>
        <Field><FieldLabel htmlFor="study-input-kind">Input type</FieldLabel><select id="study-input-kind" disabled={busy} className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={kind} onChange={(event) => setKind(event.target.value as Kind)}><option value="mapping">Reviewed site mapping</option><option value="criteria">Pre-registered criteria</option><option value="ledger">Independence ledger</option></select></Field>
        <Field><FieldLabel htmlFor="study-input-file">JSON file</FieldLabel><Input id="study-input-file" disabled={busy} type="file" accept=".json,application/json" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></Field>
        <p className="break-all text-sm text-muted-foreground">Current {status?.inputs[kind].filename ?? "input"}: {status ? status.inputs[kind].sha256 ?? "not present" : "loading…"}</p>
        <Button className="self-start" disabled={!file || !status || busy} onClick={() => void importFile()}>{busy ? "Importing…" : "Import study input"}</Button>
      </FieldGroup>
    </CardContent></Card>
}

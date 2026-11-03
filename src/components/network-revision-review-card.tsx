import * as React from "react"
import { previewNetworkRevision, type NetworkRevisionReview } from "@/api/network-revision"
import type { VisualNetwork } from "@/api/visual-network"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

function Overview({ label, visual, bounds }: { label: string; visual: VisualNetwork; bounds: [number, number, number, number] }) {
  const [left, bottom, right, top] = bounds
  const margin = Math.max(right - left, top - bottom, 1) * .05
  return <figure className="min-w-0"><figcaption className="mb-2 text-sm font-medium">{label}</figcaption>
    <svg role="img" aria-label={`${label}: schematic of lanes and islands`} viewBox={`${left-margin} ${-top-margin} ${right-left+2*margin} ${top-bottom+2*margin}`} className="h-48 w-full rounded border bg-muted">
      {visual.roads.flatMap((road) => road.lanes.map((lane) => <polyline key={lane.id} points={lane.shape.map((point) => `${point.x},${-point.y}`).join(" ")} fill="none" stroke="currentColor" strokeWidth={Math.max(lane.width, .5)} />))}
      {visual.islands?.map((island) => <polygon key={island.id} points={island.shape.map((point) => `${point.x},${-point.y}`).join(" ")} fill="var(--color-primary)" />)}
    </svg></figure>
}

function Comparison({ result }: { result: NetworkRevisionReview }) {
  const old = result.installed_visual.bounds
  const next = result.validation.visual?.bounds ?? old
  const bounds: [number, number, number, number] = [Math.min(old.min_x, next.min_x), Math.min(old.min_y, next.min_y), Math.max(old.max_x, next.max_x), Math.max(old.max_y, next.max_y)]
  return <div className="flex flex-col gap-4">
    <Alert><AlertDescription>{result.message} The diagrams are schematic and do not establish traffic safety or field accuracy.</AlertDescription></Alert>
    <div className="grid gap-4 sm:grid-cols-2"><Overview label="Installed network" visual={result.installed_visual} bounds={bounds} />
      {result.validation.visual ? <Overview label="Proposed draft" visual={result.validation.visual} bounds={bounds} /> : <p className="text-sm text-muted-foreground">Draft geometry cannot be previewed until the structural errors are corrected.</p>}</div>
    <div className="text-sm"><p>Structure: {result.validation.structurally_valid ? "valid" : "needs attention"}. Full vehicle clearance: not checked.</p>
      <p className="break-all">Installed fingerprint: {result.installed_sha256}</p><p className="break-all">Draft fingerprint: {result.candidate_sha256 ?? "unavailable"}</p></div>
    <div><h3 className="text-sm font-semibold">Changes</h3><ul className="text-sm">{Object.entries(result.changes).map(([name, change]) => <li key={name}>{name}: {change.available ? `${change.added.length} added, ${change.removed.length} removed, ${change.modified.length} modified` : change.reason}</li>)}</ul></div>
    <div><h3 className="text-sm font-semibold">Affected saved scenarios: {result.affected_scenarios.length}</h3>
      <ul className="text-sm">{result.affected_scenarios.map((scenario) => <li key={scenario.id}>{scenario.name}{scenario.archived ? " (archived)" : ""}</li>)}</ul></div>
    <div><h3 className="text-sm font-semibold">Review issues</h3><ul className="flex max-h-64 flex-col gap-1 overflow-auto text-sm">{result.validation.issues.map((issue, index) => <li key={index}>{issue.severity}: {issue.message}</li>)}</ul></div>
  </div>
}

export function NetworkRevisionReviewCard() {
  const [file, setFile] = React.useState<File | null>(null)
  const [result, setResult] = React.useState<NetworkRevisionReview | null>(null)
  const [error, setError] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const selection = React.useRef(0)
  async function review() {
    if (!file) return
    const request = selection.current
    setBusy(true); setError(""); setResult(null)
    try {
      if (file.size > 8 * 1024 * 1024) throw new Error("Choose a draft or review bundle no larger than 8 MB.")
      const parsed: unknown = JSON.parse(await file.text())
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("The file must contain a network draft or road-editor review bundle.")
      const document = parsed as Record<string, unknown>
      const network = document.kind === "unvalidated_road_editor_review" ? document.network : document
      if (!network || typeof network !== "object" || Array.isArray(network)) throw new Error("The review bundle does not contain a network draft.")
      const draft = network as Record<string, unknown>
      if (draft.id !== "tagum_site_a" && draft.id !== "tagum_site_b") throw new Error("Choose a draft for Site A or Site B.")
      const response = await previewNetworkRevision(draft.id, draft)
      if (selection.current === request) setResult(response)
    } catch (reason) {
      if (selection.current === request) setError(reason instanceof Error ? reason.message : "Could not review the draft.")
    } finally {
      if (selection.current === request) setBusy(false)
    }
  }
  return <Card><CardHeader><CardTitle>Review road network draft</CardTitle><CardDescription>Choose a JSON draft or review bundle exported from the separate Road Editor. This review does not install it.</CardDescription></CardHeader>
    <CardContent><FieldGroup><Field><FieldLabel htmlFor="network-review-file">Draft file</FieldLabel><Input id="network-review-file" type="file" accept=".json,application/json" onChange={(event) => { selection.current++; setFile(event.target.files?.[0] ?? null); setResult(null); setError(""); setBusy(false) }} /></Field>
      <Button className="self-start" disabled={!file || busy} onClick={() => void review()}>{busy ? "Reviewing…" : "Review draft"}</Button>
      {error && <Alert variant="destructive"><AlertDescription role="alert">{error}</AlertDescription></Alert>}
      {result && <Comparison result={result} />}
    </FieldGroup></CardContent></Card>
}

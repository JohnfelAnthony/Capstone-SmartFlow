import * as React from "react"

import { checkClosures, type ClosureReport, type NativeScenarioConfig, type NativeScenarioOptions } from "@/api/native-scenario"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { describeRule, groupRoads, readClosures, ruleProblem, writeClosures, type ClosureRule } from "@/lib/closures"

const CHECK_DELAY_MS = 250

function DetourBadge({ report, laneId }: { report: ClosureReport | null; laneId: string }) {
  const piece = report?.pieces[laneId]
  if (!piece) return <Badge variant="outline">checking…</Badge>
  if (piece.trips_using === 0) return <Badge variant="outline" title="No trip's usual route uses this piece, so closing it changes nothing unless traffic is detoured onto it.">not on a usual route</Badge>
  return piece.has_detour
    ? <Badge variant="secondary" title={`All ${piece.trips_using} trips that normally use this piece can still reach their destination.`}>has a detour</Badge>
    : <Badge variant="destructive" title={`${piece.trips_without_route} of ${piece.trips_using} trips that normally use this piece would have no route. Those vehicles divert to the nearest open exit; demand that enters here waits.`}>no detour</Badge>
}

/** Choose closed roads by street: either direction or both, the whole run or from a start to an end time. The detour status is the real routing check. */
export function ClosurePicker({ options, config, onChange, onProblem, disabled = false }: {
  options: NativeScenarioOptions; config: NativeScenarioConfig; onChange: (config: NativeScenarioConfig) => void
  onProblem: (message: string | null) => void; disabled?: boolean
}) {
  const { rules, locked } = React.useMemo(() => readClosures(config), [config])
  const [report, setReport] = React.useState<ClosureReport | null>(null)
  const [checkError, setCheckError] = React.useState("")
  const groups = React.useMemo(() => groupRoads(options.lanes), [options.lanes])
  const selection = JSON.stringify([config.closed_lanes ?? [], (config.events ?? []).filter(event => event.closed !== undefined)])

  React.useEffect(() => {
    let current = true
    const timer = window.setTimeout(() => {
      const [closed, events] = JSON.parse(selection)
      checkClosures(options.network_id, closed, events)
        .then(result => { if (current) { setReport(result); setCheckError(""); onProblem(result.valid ? null : result.message) } })
        .catch(error => { if (current) { setCheckError(error instanceof Error ? error.message : "Unable to check these closures."); onProblem(null) } })
    }, CHECK_DELAY_MS)
    return () => { current = false; window.clearTimeout(timer) }
  }, [options.network_id, selection, onProblem])

  const update = (next: Record<string, ClosureRule>) => onChange(writeClosures(config, next, locked))
  const setClosed = (laneId: string, closed: boolean) => {
    const next = { ...rules }
    if (closed) next[laneId] = { start: 0, end: null }
    else delete next[laneId]
    update(next)
  }
  const setTime = (laneId: string, key: keyof ClosureRule, text: string) => {
    const value = text.trim() === "" ? (key === "end" ? null : 0) : Number(text)
    update({ ...rules, [laneId]: { ...rules[laneId], [key]: value } as ClosureRule })
  }

  return <Field>
    <FieldLabel>Closed roads</FieldLabel>
    <FieldDescription>Close a road in one direction or both. A closed road takes no new vehicles; traffic that can no longer reach its destination goes to the nearest open exit, and demand that enters on a closed road waits. Each closed piece below says whether a detour exists.</FieldDescription>
    {checkError && <Alert variant="destructive"><AlertDescription>{checkError}</AlertDescription></Alert>}
    {report && !report.valid && report.message && <Alert variant="destructive" role="alert"><AlertDescription>{report.message}</AlertDescription></Alert>}
    <div className="flex flex-col gap-2" role="group" aria-label="Closed roads">
      {groups.map(group => <div key={group.roadId} className="rounded-lg border p-2.5" data-testid={`road-${group.roadId}`}>
        <p className="text-sm font-medium">{group.title}</p>
        <div className="mt-1.5 flex flex-col gap-1.5">
          {group.lanes.map(lane => {
            const rule = rules[lane.id]
            const isLocked = locked.includes(lane.id)
            const problem = rule ? ruleProblem(rule) : null
            return <div key={lane.id} className="flex flex-col gap-1.5">
              <label className="flex flex-wrap items-center gap-2 text-sm">
                <Checkbox checked={Boolean(rule) || isLocked} disabled={disabled || isLocked} aria-label={`Close ${group.title}, ${lane.direction}`}
                  onCheckedChange={checked => setClosed(lane.id, checked === true)} />
                <span className="capitalize">{lane.direction}</span>
                <span className="text-xs text-muted-foreground">{lane.kind === "entry" ? "(vehicles enter here)" : lane.kind === "exit" ? "(vehicles leave here)" : ""}</span>
                <DetourBadge report={report} laneId={lane.id} />
                {rule ? <Badge variant="outline">{describeRule(rule)}</Badge> : null}
                {isLocked ? <Badge variant="outline">several timed changes (kept as saved)</Badge> : null}
              </label>
              {rule ? <div className="ml-6 grid max-w-sm grid-cols-2 gap-2">
                <Field data-invalid={Boolean(problem)}>
                  <FieldLabel htmlFor={`start-${lane.id}`}>Closes at (s)</FieldLabel>
                  <Input id={`start-${lane.id}`} type="number" min={0} step={1} value={rule.start} disabled={disabled} aria-invalid={Boolean(problem)}
                    onChange={event => setTime(lane.id, "start", event.target.value)} />
                </Field>
                <Field data-invalid={Boolean(problem)}>
                  <FieldLabel htmlFor={`end-${lane.id}`}>Reopens at (s)</FieldLabel>
                  <Input id={`end-${lane.id}`} type="number" min={0} step={1} value={rule.end ?? ""} placeholder="end of run" disabled={disabled} aria-invalid={Boolean(problem)}
                    onChange={event => setTime(lane.id, "end", event.target.value)} />
                </Field>
                {problem ? <FieldDescription className="col-span-2 text-destructive">{problem}</FieldDescription> : null}
              </div> : null}
            </div>
          })}
        </div>
      </div>)}
    </div>
    {report && report.selection.trips_without_route > 0 && report.valid
      ? <p className="text-sm text-muted-foreground" role="status">{report.selection.trips_without_route} of {report.selection.trips} entry-to-exit trips would lose their usual destination under this selection; those vehicles divert to an open exit.</p> : null}
  </Field>
}

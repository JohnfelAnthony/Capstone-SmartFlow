import * as React from "react"
import { ChevronDownIcon } from "lucide-react"
import { getCompareSignals, type CompareSignals, type SignalEvidence } from "@/api/compare"
import { SESSION_RESTORED_EVENT } from "@/api/client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { formatMetric } from "@/lib/metrics"

function label(phase: string) { return phase.replace(/_GREEN$|_YELLOW$/g, "").replaceAll("_", " ").toLowerCase() }
const MISSING_STAGES = new Set(["unknown", "unsignalized"])

function Timeline({ evidence, name, start, end }: { evidence: SignalEvidence; name: "Baseline" | "Compared"; start: number; end: number }) {
  return <div className="compare-signal-row"><strong><i data-run={name.toLowerCase()} />{name}</strong><div className="compare-signal-track" aria-label={`${name} signal timeline`}>
    {evidence.segments.map((segment, index) => {
      const a = Math.max(start, segment.start), b = Math.min(end, segment.end)
      if (b <= a) return null
      const service = label(segment.phase), share = (b-a) / (end-start)
      const isGreen = !MISSING_STAGES.has(segment.stage) && segment.stage !== "yellow" && segment.stage !== "red"
      return <span key={index} data-stage={segment.stage} data-service={service}
        style={{ left: `${100 * (a-start)/(end-start)}%`, width: `${100 * share}%` }}
        title={`${service} ${segment.stage}: ${a.toFixed(1)}–${b.toFixed(1)} s`}>
        {isGreen && share > 1/12 ? service : isGreen && share > 1/25 ? service.slice(0,1).toUpperCase() : ""}
      </span>
    })}
  </div></div>
}

export const CompareSignalsCard = React.memo(function CompareSignalsCard({ left, right }: { left: number; right: number }) {
  const [result, setResult] = React.useState<{ ids: string; data?: CompareSignals; error?: string } | null>(null)
  const [revision, retry] = React.useReducer((n: number) => n+1, 0)
  const ids = `${left}:${right}`
  React.useEffect(() => {
    window.addEventListener(SESSION_RESTORED_EVENT, retry)
    return () => window.removeEventListener(SESSION_RESTORED_EVENT, retry)
  }, [])
  React.useEffect(() => {
    const request = new AbortController()
    getCompareSignals(left, right, request.signal)
      .then(data => { if (!request.signal.aborted) setResult({ ids, data }) })
      .catch(error => {
        if (!request.signal.aborted) setResult({ ids, error: error instanceof Error ? error.message : "Unable to load signal evidence." })
      })
    return () => request.abort()
  }, [left,right,ids,revision])
  const data = result?.ids === ids ? result.data : undefined
  const error = result?.ids === ids ? result.error : undefined
  const end = data ? Math.min(data.end, data.start + 120) : 0
  const phases = data ? [...new Set([...data.left.phases, ...data.right.phases].map(p => p.phase))] : []
  const shown = data ? [...data.left.segments, ...data.right.segments].filter(s => s.end > data.start && s.start < end) : []
  const hasMissing = shown.some(s => MISSING_STAGES.has(s.stage))
  const ticks = data ? Array.from({ length: Math.floor((end - data.start) / 30) + 1 }, (_, i) => data.start + 30 * i) : []
  const longest = data ? Math.max(1, ...[...data.left.phases, ...data.right.phases].map(p => p.mean_seconds ?? 0)) : 1
  return <Card className="compare-signal-card">
    <CardHeader><CardTitle>How the signal changed</CardTitle>
      <CardDescription>Which road had the green light. An RL signal changes its choices as traffic changes, so it may not repeat a fixed cycle.</CardDescription></CardHeader>
    <CardContent className="flex flex-col gap-4">
      {error ? <p role="alert">{error} <Button variant="outline" size="sm" onClick={retry}>Retry signal evidence</Button></p> : !data ? <p role="status">Reading recorded signal phases…</p> : <>
        <div className="compare-legend" aria-label="Signal colours">
          {phases.map(phase => <span key={phase} className="capitalize"><i data-service={label(phase)} />{label(phase)}</span>)}
          <span><i data-stage="yellow" />Switching (yellow and all-red)</span>
          {hasMissing ? <span><i data-stage="unknown" />No signal or not recorded</span> : null}
        </div>
        <div className="flex flex-col gap-2">
          <Timeline evidence={data.left} name="Baseline" start={data.start} end={end} />
          <Timeline evidence={data.right} name="Compared" start={data.start} end={end} />
          <div className="compare-signal-axis">{ticks.map(tick => <span key={tick} style={{ left: `${100 * (tick - data.start) / (end - data.start || 1)}%` }}>{tick} s</span>)}</div>
        </div>
        {phases.length ? <div className="flex flex-col gap-2">
          <strong className="text-sm">Average green time per road</strong>
          <p className="text-sm text-muted-foreground">A longer bar means the road keeps its green longer each time it is served.</p>
          {phases.map(phase => <div className="compare-green-row" key={phase}><span className="capitalize">{label(phase)}</span><div>
            {(["left","right"] as const).map(side => {
              const mean = data[side].phases.find(p => p.phase === phase)?.mean_seconds ?? null
              return <span className="compare-kpi-bar" key={side}>
                <span className="compare-kpi-track"><i data-run={side === "left" ? "baseline" : "compared"} style={{ width: `${100 * (mean ?? 0) / longest}%` }} /></span>
                <strong>{mean === null ? "No full green" : `${formatMetric(mean, 1)} s`}</strong>
              </span>
            })}
          </div></div>)}
        </div> : <p>No complete signal evidence is available for these runs.</p>}
        {phases.length ? <Collapsible>
          <CollapsibleTrigger render={<Button variant="ghost" size="sm" />}><ChevronDownIcon data-icon="inline-start" />Show ranges and counts</CollapsibleTrigger>
          <CollapsibleContent><div className="overflow-x-auto"><table className="compare-signal-table">
            <caption>Complete green durations across the full recording window</caption>
            <thead><tr><th>Served approach</th><th>Baseline mean (range)</th><th>Compared mean (range)</th></tr></thead>
            <tbody>{phases.map(phase => <tr key={phase}><th className="capitalize">{label(phase)}</th>{(["left","right"] as const).map(side => {
              const p = data[side].phases.find(p=>p.phase===phase)
              return <td key={side}>{p?.mean_seconds != null ? `${formatMetric(p.mean_seconds,1)} s (${formatMetric(p.min_seconds,1)}–${formatMetric(p.max_seconds,1)}), n=${p.complete_count}` : "No complete green observed"}</td>
            })}</tr>)}</tbody>
          </table></div></CollapsibleContent>
        </Collapsible> : null}
        <p className="text-xs text-muted-foreground">The timeline shows the first {formatMetric(end-data.start,0)} s. Greens cut off at the edges or by a gap are left out of the averages. Missing signal record: baseline {data.left.unavailable_seconds} s, compared {data.right.unavailable_seconds} s. The PDF includes timings, results and research limits.</p>
      </>}
    </CardContent>
  </Card>
})

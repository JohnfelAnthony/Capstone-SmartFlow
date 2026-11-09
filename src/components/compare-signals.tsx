import * as React from "react"
import { getCompareSignals, type CompareSignals, type SignalEvidence } from "@/api/compare"
import { SESSION_RESTORED_EVENT } from "@/api/client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { formatMetric } from "@/lib/metrics"

function label(phase: string) { return phase.replace(/_GREEN$|_YELLOW$/g, "").replaceAll("_", " ").toLowerCase() }
function Timeline({ evidence, name, start, end }: { evidence: SignalEvidence; name: string; start: number; end: number }) {
  return <div className="compare-signal-row"><strong>{name}</strong><div className="compare-signal-track" aria-label={`${name} signal timeline`}>
    {evidence.segments.map((segment, index) => {
      const a = Math.max(start, segment.start), b = Math.min(end, segment.end)
      if (b <= a) return null
      const service = label(segment.phase)
      return <span key={index} data-stage={segment.stage} data-service={service}
        style={{ left: `${100 * (a-start)/(end-start)}%`, width: `${100 * (b-a)/(end-start)}%` }}
        title={`${service} ${segment.stage}: ${a.toFixed(1)}–${b.toFixed(1)} s`}>
        {b-a > (end-start)/25 && segment.stage === "green" ? service.slice(0,1).toUpperCase() : ""}
      </span>
    })}
  </div></div>
}

export function CompareSignalsCard({ left, right }: { left: number; right: number }) {
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
  return <Card>
    <CardHeader><CardTitle>How the signal changed</CardTitle>
      <CardDescription>Actual recorded services. RL changes its choices during the run; it may have no fixed cycle.</CardDescription></CardHeader>
    <CardContent className="flex flex-col gap-4">
      {error ? <p role="alert">{error} <Button variant="outline" size="sm" onClick={retry}>Retry signal evidence</Button></p> : !data ? <p role="status">Reading recorded signal phases…</p> : <>
        <p className="text-sm text-muted-foreground">First {formatMetric(end-data.start,0)} s of shared coverage · N / E / S / W = served approach · yellow = clearance · red = all-red</p>
        <Timeline evidence={data.left} name="Baseline" start={data.start} end={end} />
        <Timeline evidence={data.right} name="Compared" start={data.start} end={end} />
        <div className="compare-signal-axis"><span>{data.start} s</span><span>{end} s</span></div>
        <div className="overflow-x-auto"><table className="compare-signal-table">
          <caption>Complete green durations across the full recording window</caption>
          <thead><tr><th>Served approach</th><th>Baseline mean (range)</th><th>Compared mean (range)</th></tr></thead>
          <tbody>{phases.map(phase => <tr key={phase}><th className="capitalize">{label(phase)}</th>{(["left","right"] as const).map(side => {
            const p = data[side].phases.find(p=>p.phase===phase)
            return <td key={side}>{p?.mean_seconds != null ? `${formatMetric(p.mean_seconds,1)} s (${formatMetric(p.min_seconds,1)}–${formatMetric(p.max_seconds,1)}), n=${p.complete_count}` : "No complete green observed"}</td>
          })}</tr>)}</tbody>
        </table></div>
        {!phases.length ? <p>No complete signal evidence is available for these runs.</p> : null}
        <p className="text-xs text-muted-foreground">Partial greens at the edges and beside gaps are excluded. Missing signal coverage: baseline {data.left.unavailable_seconds} s; compared {data.right.unavailable_seconds} s. Grey denotes no signal or missing recording. The PDF includes timings, results and research limits.</p>
      </>}
    </CardContent>
  </Card>
}

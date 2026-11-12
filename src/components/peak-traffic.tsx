import type { PeakCountsSummary } from "@/api/native-scenario"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

const TYPES = ["car", "motorcycle", "tricycle", "bus", "truck"] as const
const TYPE_LABELS: Record<string, string> = { car: "Car", motorcycle: "Motorcycle", tricycle: "Tricycle", bus: "Bus", truck: "Truck" }

function videoLength(seconds: number) {
  const whole = Math.round(seconds)
  return `${Math.floor(whole / 60)} min ${whole % 60} s`
}

/** The owner's chosen layout ("version A", 2026-11-13): one card with the totals, run-length numbers, vehicle mix, roads and assumptions. */
export function PeakTrafficCard({ summary, stale }: { summary: PeakCountsSummary; stale?: boolean }) {
  const mixTotal = TYPES.reduce((sum, kind) => sum + (summary.by_type[kind] ?? 0), 0)
  const method = summary.method === "manual" ? "Manual count" : `Automatic detector count${summary.reviewed ? "" : ", not reviewed"}`
  const value = (count: number, assumed: boolean) => assumed ? <span className="text-muted-foreground">≈ {count}</span> : <strong>{count}</strong>
  return <section aria-label="Peak-traffic video count" className="flex flex-col gap-3 rounded-lg border p-3 text-sm">
    {stale && <Alert><AlertDescription>The site's video count changed after this scenario was saved. Choose Peak traffic again to use the current count.</AlertDescription></Alert>}
    <div><Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-300">Video counts, assumed routes</Badge></div>
    <p className="text-muted-foreground">
      {method} of {summary.video.file} · {videoLength(summary.video.seconds)} · {summary.counted_vehicles.toLocaleString()} vehicles counted
      {summary.assumed_vehicles > 0 && <>, {summary.assumed_vehicles} assumed</>}
    </p>
    <p><span className="text-2xl font-semibold tabular-nums">{Math.round(summary.vehicles_per_hour).toLocaleString()}</span> vehicles per hour</p>
    <div>
      <ul className="flex flex-wrap gap-2" aria-label="Vehicles arriving during a run">
        {(["5", "10", "15"] as const).map((minutes) => <li key={minutes} className="rounded-full border px-2.5 py-0.5 tabular-nums">{minutes} min ≈ {summary.entering[minutes]}</li>)}
      </ul>
      <p className="mt-1 text-xs text-muted-foreground">Vehicles arriving at the edge of the network in that much run time, after the warm-up. When the roads are full, some wait outside; how many get through depends on congestion and the controller.</p>
    </div>
    <div>
      <div className="flex h-3.5 overflow-hidden rounded" role="img" aria-label={`Vehicle mix: ${TYPES.map((kind) => `${TYPE_LABELS[kind]} ${summary.by_type[kind] ?? 0}`).join(", ")}`}>
        {TYPES.map((kind, index) => <div key={kind} style={{ width: `${100 * (summary.by_type[kind] ?? 0) / Math.max(1, mixTotal)}%`, background: `var(--chart-${index + 1})` }} />)}
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {TYPES.map((kind, index) => <li key={kind} className="flex items-center gap-1"><span className="size-2.5 rounded-sm" style={{ background: `var(--chart-${index + 1})` }} />{TYPE_LABELS[kind]} {summary.by_type[kind] ?? 0}</li>)}
      </ul>
    </div>
    <Table>
      <TableHeader><TableRow><TableHead>Road</TableHead><TableHead className="text-right">Arriving</TableHead><TableHead className="text-right">Leaving</TableHead></TableRow></TableHeader>
      <TableBody>{summary.roads.map((road) => <TableRow key={road.approach}>
        <TableCell className="whitespace-normal"><span className="capitalize">{road.approach}</span> <span className="text-muted-foreground">· {road.name}</span></TableCell>
        <TableCell className="text-right tabular-nums">{value(road.arriving, road.arriving_assumed)}</TableCell>
        <TableCell className="text-right tabular-nums">{value(road.leaving, road.leaving_assumed)}</TableCell>
      </TableRow>)}</TableBody>
    </Table>
    <p className="-mt-1 text-xs text-muted-foreground">Bold numbers were counted in the video; ≈ numbers follow from the assumed routes.</p>
    <p>{summary.pedestrians ? `Pedestrians: ${summary.pedestrians.counted} in the video (≈ ${Math.round(summary.pedestrians.per_hour)} per hour).` : "Pedestrians: not counted at this site."}</p>
    <details open className="text-muted-foreground">
      <summary className="cursor-pointer">What is assumed</summary>
      <ul className="mt-1 ml-4 list-disc space-y-1">{summary.notes.map((note) => <li key={note}>{note}</li>)}</ul>
    </details>
  </section>
}

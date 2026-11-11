import { useEffect, useRef, type ReactNode } from "react"
import { BanIcon, XIcon } from "lucide-react"
import type { ClosureOverride, ClosureResponse, RouteContext, RoutePreview } from "@/api/routes"
import { Button } from "@/components/ui/button"
import { RESPONSE_LABELS } from "@/lib/closures"
import { describeRoad, type EndRole, type EndStep, type RouteEnd } from "@/lib/route-ends"
import { cn } from "@/lib/utils"

const plannerHints: Record<ClosureResponse, string> = {
  side_street: "Drivers whose usual route is cut take the detour that exists.",
  side_street_adaptive: "This setting applies across the network. The preview shows the route with no simulated queues.",
  nearest_exit: "The engine chooses an open exit by routing cost, which can still be the intended destination.",
  share: "The map assumes sharing is established. In a live run, the engine clears the lanes first. This layout is hypothetical.",
  wait: "Arrivals stay outside the network while this direction is closed. A whole-run closure has no reopening.",
}
const mainChoices: Array<{ value: ClosureResponse; label: string }> = [
  { value: "side_street", label: "Use a side street" },
  { value: "nearest_exit", label: "Go to another open exit" },
  { value: "wait", label: "Wait outside" },
]
const extraChoices: ClosureResponse[] = ["side_street_adaptive", "share"]

export function Step({ number, title, note, active, onActivate, children }: {
  number: number; title: string; note?: string; active?: boolean; onActivate?: () => void; children: ReactNode
}) {
  return <li aria-current={active ? "step" : undefined} className="flex gap-3 border-b py-3 pl-3 last:border-b-0">
    <span aria-hidden="true" className={cn("flex size-6 flex-none items-center justify-center rounded-full text-xs font-medium",
      active ? "bg-primary text-primary-foreground ring-4 ring-primary/20" : "bg-muted text-muted-foreground")}>{number}</span>
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      <div>
        {onActivate
          ? <button type="button" onClick={onActivate} className={cn("text-left text-sm underline-offset-2 hover:underline", active ? "font-semibold" : "font-medium")}>{title}</button>
          : <h3 className="text-sm font-medium">{title}</h3>}
        {note ? <p className="text-sm text-muted-foreground">{note}</p> : null}
      </div>
      {children}
    </div>
  </li>
}

export function EndPills({ roles, step, onPick }: {
  roles: ReadonlyArray<{ end: RouteEnd; role: EndRole }>; step: EndStep; onPick: (key: string, step: EndStep) => void
}) {
  const chosen = step === "start" ? "start" : "destination"
  return <div className="flex flex-wrap gap-2" role="group" aria-label={step === "start" ? "Start" : "Destination"}>
    {roles.map(({ end, role }) => <Button key={end.key} size="sm" variant={role === chosen ? "default" : "outline"}
      aria-pressed={role === chosen} disabled={role === "unavailable" || (step === "start" ? !end.entryId : !end.destinationId)}
      className="h-auto min-h-8 whitespace-normal text-left" onClick={() => onPick(end.key, step)}>{end.label}</Button>)}
  </div>
}

export function ChosenEnd({ label, onChange }: { label: string; onChange: () => void }) {
  return <Button size="sm" variant="outline" className="h-auto min-h-8 w-fit whitespace-normal text-left" onClick={onChange}>
    {label}<span className="text-muted-foreground"> · Change</span>
  </Button>
}

export function ClosureStep({ context, closures, selectedLaneId, preview, ready, coordinationNotice, onSelect, onToggle, onRespond }: {
  context: RouteContext; closures: ClosureOverride | undefined; selectedLaneId: string | null; preview: RoutePreview | null
  ready: boolean; coordinationNotice: string
  onSelect: (laneId: string | null) => void; onToggle: (laneId: string) => void; onRespond: (laneId: string, response: ClosureResponse) => void
}) {
  const card = useRef<HTMLDivElement>(null)
  // On a phone the panel is below the map, so bring the picked road's card into view.
  useEffect(() => { if (selectedLaneId) card.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }) }, [selectedLaneId])
  const roads = new Map(context.roads.map(road => [road.lane_id, road]))
  const closed = closures?.closed_lanes ?? []
  const selected = selectedLaneId ? roads.get(selectedLaneId) : undefined
  const selectedClosed = !!selected && closed.includes(selected.lane_id)
  const options = selected ? preview?.response_options[selected.lane_id] : undefined
  const response = selected ? preview?.effective_closures.closure_responses[selected.lane_id] ?? closures?.closure_responses[selected.lane_id] : undefined
  const enabled = (value: ClosureResponse) => !!options?.some(option => option.value === value && option.enabled)
  const blocked = options?.filter(option => !option.enabled) ?? []
  const choice = (value: ClosureResponse, label: string) => <Button key={value} size="sm" aria-pressed={response === value}
    variant={response === value ? "default" : "outline"} disabled={!enabled(value)} onClick={() => onRespond(selected!.lane_id, value)}>{label}</Button>
  return <div className="flex flex-col gap-3">
    {closed.length ? <ul className="flex flex-wrap gap-2" aria-label="Closed roads">
      {closed.map(lane => <li key={lane}><Button size="sm" variant="outline" className="h-auto min-h-8 whitespace-normal text-left"
        aria-label={`Reopen ${roads.get(lane) ? describeRoad(roads.get(lane)!) : lane}`} onClick={() => onToggle(lane)}>
        <BanIcon data-icon="inline-start" />{roads.get(lane) ? describeRoad(roads.get(lane)!) : lane}<XIcon data-icon="inline-end" />
      </Button></li>)}
    </ul> : null}
    {selected ? <div ref={card} className="flex flex-col gap-2 rounded-lg border p-3" aria-label="Selected road">
      <p className="text-sm font-medium">{describeRoad(selected)}</p>
      {selectedClosed ? <>
        <p className="text-sm text-muted-foreground">What should traffic do?</p>
        <div className="flex flex-wrap gap-2">{mainChoices.map(item => choice(item.value, item.label))}</div>
        <details className="text-sm text-muted-foreground">
          <summary className="cursor-pointer">More choices</summary>
          <div className="mt-2 flex flex-wrap gap-2">{extraChoices.map(value => choice(value, RESPONSE_LABELS[value]))}</div>
          {blocked.length ? <ul className="mt-2 flex flex-col gap-1">{blocked.map(option =>
            <li key={option.value}><strong>{RESPONSE_LABELS[option.value]}</strong> · {option.reason}</li>)}</ul> : null}
        </details>
        {response ? <p className="text-sm text-muted-foreground">{plannerHints[response]}</p> : null}
        {coordinationNotice ? <p role="status" className="text-sm">{coordinationNotice}</p> : null}
      </> : null}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={selectedClosed ? "outline" : "destructive"} disabled={!ready} onClick={() => onToggle(selected.lane_id)}>
          {selectedClosed ? "Reopen this road" : "Close this road"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onSelect(null)}>Done</Button>
      </div>
    </div> : <p className="text-sm text-muted-foreground">{closed.length ? "Click another road to close it, or a closed road above to reopen it." : "No roads are closed. Click a road on the map to close it."}</p>}
  </div>
}

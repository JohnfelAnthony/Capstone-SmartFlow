import type { ClosureOverride, ClosureResponse, RoutePreview } from "@/api/routes"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { RESPONSE_LABELS } from "@/lib/closures"
import type { EndStep, RouteEnd } from "@/lib/route-ends"

const responseHints: Record<ClosureResponse, string> = {
  side_street: "Drivers use an open detour when one is available.",
  side_street_adaptive: "This setting applies across the network. The preview uses no simulated queues.",
  nearest_exit: "The routing cost determines which open exit drivers use.",
  share: "The preview assumes sharing is established. In a live run, the engine clears the lanes first. This layout is hypothetical.",
  wait: "Arrivals wait outside the network while this direction is closed.",
}

export function TripEndpoint({ step, label, active, disabled, onChange }: {
  step: EndStep; label?: string; active: boolean; disabled: boolean; onChange: () => void
}) {
  const name = step === "start" ? "Start" : "Destination"
  return <li className="route-trip-endpoint" aria-current={active ? "step" : undefined}>
    <span className="route-trip-letter" data-endpoint={step} aria-hidden="true">{step === "start" ? "A" : "B"}</span>
    <div className="min-w-0 flex-1">
      <p className="font-medium">{name}</p>
      <p className="text-sm text-muted-foreground">{label ?? (active ? "Choose on map" : "Choose a start first")}</p>
    </div>
    {label && !active ? <Button size="sm" variant="ghost" aria-label={`Change ${name.toLowerCase()}`}
      disabled={disabled} onClick={onChange}>Change</Button> : null}
  </li>
}

export function EndpointList({ step, ends, onPick }: {
  step: EndStep; ends: readonly RouteEnd[]; onPick: (key: string) => void
}) {
  return <details className="route-planner-details">
    <summary>Choose {step === "start" ? "a start" : "a destination"} from a list</summary>
    <ul className="flex flex-col gap-1 pt-2">
      {ends.map(end => <li key={end.key}>
        <Button size="sm" variant="outline" className="h-auto min-h-8 w-full justify-start whitespace-normal text-left"
          onClick={() => onPick(end.key)}>{end.label}</Button>
      </li>)}
    </ul>
  </details>
}

export function RoadActions({ laneId, segmentDirections, closures, preview, coordinationNotice, onSetClosure, onRespond }: {
  laneId: string; segmentDirections: readonly string[]; closures: ClosureOverride | undefined; preview: RoutePreview | null
  coordinationNotice: string
  onSetClosure: (laneIds: readonly string[], closed: boolean) => void
  onRespond: (laneId: string, response: ClosureResponse) => void
}) {
  const closed = closures?.closed_lanes ?? []
  const selectedClosed = closed.includes(laneId)
  const segmentClosed = segmentDirections.every(direction => closed.includes(direction))
  const options = preview?.response_options[laneId] ?? []
  const response = preview?.effective_closures.closure_responses[laneId] ?? closures?.closure_responses[laneId]

  return <div className="flex flex-col gap-2" aria-label="Road actions">
    <p className="text-sm text-muted-foreground">{selectedClosed ? "Closed in this preview" : "Open in this preview"}</p>
    <Button size="sm" variant={selectedClosed ? "outline" : "destructive"}
      onClick={() => onSetClosure([laneId], !selectedClosed)}>
      {selectedClosed ? "Reopen this direction" : "Close this direction"}
    </Button>
    {segmentDirections.length > 1 ? <Button size="sm" variant="outline"
      onClick={() => onSetClosure(segmentDirections, !segmentClosed)}>
      {segmentClosed ? "Reopen both directions" : "Close both directions"}
    </Button> : null}
    {selectedClosed && options.length ? <details className="route-planner-details">
      <summary>Traffic response options</summary>
      <div className="flex flex-col gap-2 pt-2">
        <ToggleGroup variant="outline" size="sm" className="flex-wrap" aria-label="Traffic response" value={response ? [response] : []}
          onValueChange={([value]) => { if (value) onRespond(laneId, value as ClosureResponse) }}>
          {options.map(option => <ToggleGroupItem key={option.value} value={option.value} disabled={!option.enabled}
            title={option.reason ?? undefined}>{RESPONSE_LABELS[option.value]}</ToggleGroupItem>)}
        </ToggleGroup>
        {response ? <p className="text-sm text-muted-foreground">{responseHints[response]}</p> : null}
        {options.some(option => !option.enabled) ? <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
          {options.filter(option => !option.enabled).map(option => <li key={option.value}>{RESPONSE_LABELS[option.value]} · {option.reason}</li>)}
        </ul> : null}
      </div>
    </details> : null}
    {coordinationNotice ? <p role="status" className="text-sm">{coordinationNotice}</p> : null}
  </div>
}

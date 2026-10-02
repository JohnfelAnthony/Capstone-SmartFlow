import * as React from "react"
import { ArrowDownIcon, ArrowUpIcon, PlusIcon, TrashIcon } from "lucide-react"
import type { LaneEvent, NativeScenarioConfig, NativeScenarioOptions, SignalPlan } from "@/api/native-scenario"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export function NativeSelect({ label, value, options, onChange, disabled = false }: {
  label: string; value: string; options: Array<{ value: string; label: string; disabled?: boolean }>
  onChange: (value: string) => void; disabled?: boolean
}) {
  const id = React.useId()
  return <Field data-disabled={disabled}>
    <FieldLabel htmlFor={id}>{label}</FieldLabel>
    <Select items={options} value={value} onValueChange={(next) => next !== null && onChange(next)} disabled={disabled}>
      <SelectTrigger id={id} className="w-full"><SelectValue /></SelectTrigger>
      <SelectContent><SelectGroup>{options.map((option) =>
        <SelectItem key={option.value} value={option.value} disabled={option.disabled}>{option.label}</SelectItem>
      )}</SelectGroup></SelectContent>
    </Select>
  </Field>
}

export function NativeNumber({ label, value, onChange, min = 0, max = 86400, step = .1, disabled = false }: {
  label: string; value: number; onChange: (value: number) => void
  min?: number; max?: number; step?: number; disabled?: boolean
}) {
  const id = React.useId()
  const invalid = !Number.isFinite(value) || value < min || value > max
  return <Field data-invalid={invalid} data-disabled={disabled}>
    <FieldLabel htmlFor={id}>{label}</FieldLabel>
    <Input id={id} type="number" min={min} max={max} step={step} value={value}
      aria-invalid={invalid} disabled={disabled} onChange={(event) => onChange(Number(event.target.value))} />
    {invalid && <FieldDescription>Enter a value from {min} to {max}.</FieldDescription>}
  </Field>
}

export function NativeScenarioControls({ value, options, onChange }: {
  value: NativeScenarioConfig; options: NativeScenarioOptions; onChange: (value: NativeScenarioConfig) => void
}) {
  const [editingJunction, setEditingJunction] = React.useState("")
  const selected = value.controlled_junction ?? options.defaults.controlled_junction ?? options.junctions[0].id
  const junction = options.junctions.find((item) => item.id === (editingJunction || selected)) ?? options.junctions[0]
  const plan: SignalPlan = { ...junction.default_plan, green_seconds: value.green_seconds ?? junction.default_plan.green_seconds, ...value.signal_plans?.[junction.id] }
  const events = value.events ?? []
  const closedLanes = value.closed_lanes ?? []
  const slowLanes = value.slow_lanes ?? {}
  function updatePlan(patch: Partial<SignalPlan>) {
    onChange({ ...value, signal_plans: { ...value.signal_plans, [junction.id]: { ...plan, ...patch } } })
  }
  function updateEvent(index: number, patch: Partial<LaneEvent>) {
    onChange({ ...value, events: events.map((event, current) => current === index ? { ...event, ...patch } : event) })
  }
  function setInitialSpeed(lane: string, percent: number) {
    const next = { ...slowLanes }
    if (percent === 100) delete next[lane]
    else next[lane] = percent / 100
    onChange({ ...value, slow_lanes: next })
  }
  function movePhase(index: number, direction: number) {
    const order = [...plan.phase_order]
    ;[order[index], order[index + direction]] = [order[index + direction], order[index]]
    updatePlan({ phase_order: order })
  }
  return <FieldGroup>
    <FieldSet>
      <FieldLegend>Signal control</FieldLegend>
      <FieldDescription>Select the junction a trained policy will control. Fixed-time runs use the saved plans at every signalized junction.</FieldDescription>
      <NativeSelect label="Junction for RL" value={selected}
        options={options.junctions.map((item) => ({ value: item.id, label: item.label }))}
        onChange={(controlled_junction) => { onChange({ ...value, controlled_junction }); setEditingJunction(controlled_junction) }} />
      <NativeSelect label="Edit signal plan for" value={junction.id}
        options={options.junctions.map((item) => ({ value: item.id, label: item.label }))} onChange={setEditingJunction} />
      <NativeSelect label="Junction control" value={plan.mode}
        options={[{ value: "signalized", label: "Traffic signals" }, { value: "all_way_stop", label: "All-way stop" }]}
        onChange={(mode) => updatePlan({ mode: mode as SignalPlan["mode"] })} />
      {plan.mode === "signalized" ? <>
        <FieldGroup className="grid sm:grid-cols-2">
          <NativeNumber label="Fixed green (seconds)" value={plan.green_seconds} min={5} max={180} onChange={(green_seconds) => updatePlan({ green_seconds })} />
          <NativeNumber label="Minimum green (seconds)" value={plan.minimum_green} min={5} max={60} onChange={(minimum_green) => updatePlan({ minimum_green })} />
          <NativeNumber label="Maximum green (seconds)" value={plan.maximum_green} min={10} max={180} onChange={(maximum_green) => updatePlan({ maximum_green })} />
          <NativeNumber label="Yellow (seconds)" value={plan.yellow_seconds} min={2} max={6} onChange={(yellow_seconds) => updatePlan({ yellow_seconds })} />
          <NativeNumber label="All-red clearance (seconds)" value={plan.all_red_seconds} min={1} max={10} onChange={(all_red_seconds) => updatePlan({ all_red_seconds })} />
          <NativeNumber label="Cycle offset (seconds)" value={plan.offset_seconds} max={3600} onChange={(offset_seconds) => updatePlan({ offset_seconds })} />
        </FieldGroup>
        {!(plan.minimum_green <= plan.green_seconds && plan.green_seconds <= plan.maximum_green) &&
          <Alert variant="destructive"><AlertDescription>Minimum green must be at most fixed green, and fixed green must be at most maximum green.</AlertDescription></Alert>}
        <Field>
          <FieldLabel>Phase order</FieldLabel>
          <ol className="flex flex-col gap-2">{plan.phase_order.map((phase, index) => <li key={phase} className="flex items-center gap-2">
            <span className="flex-1">{index + 1}. {phase === "pedestrian" ? "Pedestrian crossing" : `${phase} approach`}</span>
            <Button type="button" size="icon-sm" variant="outline" disabled={index === 0} aria-label={`Move ${phase} earlier`} onClick={() => movePhase(index, -1)}><ArrowUpIcon /></Button>
            <Button type="button" size="icon-sm" variant="outline" disabled={index === plan.phase_order.length - 1} aria-label={`Move ${phase} later`} onClick={() => movePhase(index, 1)}><ArrowDownIcon /></Button>
          </li>)}</ol>
          <FieldDescription>Every available approach and the protected crossing appears once. Pedestrian clearance and emergency priority remain enforced.</FieldDescription>
        </Field>
      </> : <Alert><AlertDescription>Vehicles stop before taking turns. This junction cannot host an RL signal controller while set to all-way stop.</AlertDescription></Alert>}
      <div className="flex flex-col gap-2" aria-label="Configured junction controllers">
        {options.junctions.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm">{item.label}</span>
          <Badge variant="outline">{value.signal_plans?.[item.id]?.mode === "all_way_stop" ? "All-way stop" : item.id === selected ? "RL candidate / fixed-time baseline" : "Fixed-time"}</Badge>
        </div>)}
      </div>
    </FieldSet>

    <FieldSet>
      <FieldLegend>Routing</FieldLegend>
      <NativeSelect label="Routing strategy" value={value.routing_mode ?? "adaptive"}
        options={[{ value: "adaptive", label: "Adaptive travel-time routing" }, { value: "static", label: "Static routes with closure detours" }]}
        onChange={(routing_mode) => onChange({ ...value, routing_mode: routing_mode as "adaptive" | "static" })} />
      <FieldGroup className="grid sm:grid-cols-2">
        <NativeNumber label="Route check interval (seconds)" value={value.reroute_interval ?? 15} min={1} max={300} onChange={(reroute_interval) => onChange({ ...value, reroute_interval })} />
        <NativeNumber label="Required improvement (%)" value={(value.reroute_improvement ?? .15) * 100} min={0} max={90} onChange={(percent) => onChange({ ...value, reroute_improvement: percent / 100 })} />
      </FieldGroup>
      <FieldDescription>Congestion rerouting requires a useful improvement and observes the interval. Closures can force a detour; vehicles wait if no route is available.</FieldDescription>
    </FieldSet>

    <FieldSet>
      <FieldLegend>Scheduled road changes</FieldLegend>
      <FieldDescription>Times are seconds from simulation start, including any training warmup. Closures prevent new entry; vehicles already on the lane can leave. A speed value of 100% restores normal speed.</FieldDescription>
      {!events.length && <p className="text-sm text-muted-foreground">No scheduled changes.</p>}
      {events.map((event, index) => <FieldSet key={index} className="rounded-lg border p-3">
        <FieldLegend>Road change {index + 1}</FieldLegend>
        <NativeSelect label={`Road / direction for change ${index + 1}`} value={event.lane_id}
          options={options.lanes.map((lane) => ({ value: lane.id, label: lane.label }))} onChange={(lane_id) => updateEvent(index, { lane_id })} />
        <FieldGroup className="grid sm:grid-cols-2">
          <NativeNumber label={`Time for change ${index + 1} (seconds)`} value={event.time} onChange={(time) => updateEvent(index, { time })} />
          <NativeSelect label={`Access for change ${index + 1}`} value={event.closed === undefined ? "unchanged" : event.closed ? "closed" : "open"}
            options={[{ value: "unchanged", label: "Keep current access" }, { value: "closed", label: "Close to entry" }, { value: "open", label: "Reopen lane" }]}
            onChange={(access) => updateEvent(index, { closed: access === "unchanged" ? undefined : access === "closed" })} />
          <NativeSelect label={`Speed change ${index + 1}`} value={event.speed_factor === undefined ? "unchanged" : "set"}
            options={[{ value: "unchanged", label: "Keep current speed" }, { value: "set", label: "Set speed percentage" }]}
            onChange={(speed) => updateEvent(index, { speed_factor: speed === "unchanged" ? undefined : .5 })} />
          {event.speed_factor !== undefined && <NativeNumber label={`Speed for change ${index + 1} (%)`} value={event.speed_factor * 100} min={5} max={100}
            onChange={(percent) => updateEvent(index, { speed_factor: percent / 100 })} />}
        </FieldGroup>
        {event.closed === undefined && event.speed_factor === undefined && <Alert variant="destructive"><AlertDescription>Choose an access change or a speed change.</AlertDescription></Alert>}
        <Button type="button" variant="outline" onClick={() => onChange({ ...value, events: events.filter((_, current) => current !== index) })}>
          <TrashIcon data-icon="inline-start" />Remove change {index + 1}
        </Button>
      </FieldSet>)}
      <Button type="button" variant="outline" onClick={() => onChange({ ...value, events: [...events, { time: 0, lane_id: options.lanes[0].id, closed: true }] })}>
        <PlusIcon data-icon="inline-start" />Add road change
      </Button>
    </FieldSet>

    <details>
      <summary className="cursor-pointer text-sm font-medium">Initial road conditions ({new Set([...closedLanes, ...Object.keys(slowLanes)]).size} restrictions)</summary>
      <FieldGroup className="mt-4">
        <FieldDescription>Set conditions at time zero. Scheduled events can later replace these conditions.</FieldDescription>
        {options.lanes.map((lane) => <FieldSet key={lane.id} className="rounded-lg border p-3">
          <FieldLegend variant="label">{lane.label}</FieldLegend>
          <Field orientation="horizontal">
            <Checkbox id={`closed-${lane.id}`} checked={closedLanes.includes(lane.id)} onCheckedChange={(checked) => onChange({ ...value,
              closed_lanes: checked ? [...new Set([...closedLanes, lane.id])] : closedLanes.filter((id) => id !== lane.id) })} />
            <FieldLabel htmlFor={`closed-${lane.id}`}>Closed to entry</FieldLabel>
          </Field>
          <NativeNumber label={`Initial speed ${lane.id} (%)`} value={(slowLanes[lane.id] ?? 1) * 100} min={5} max={100} onChange={(percent) => setInitialSpeed(lane.id, percent)} />
        </FieldSet>)}
      </FieldGroup>
    </details>
  </FieldGroup>
}

export function NativeScenarioSummary({ config, options }: { config: NativeScenarioConfig; options: NativeScenarioOptions | null }) {
  const junction = config.controlled_junction ?? options?.defaults.controlled_junction
  const label = options?.junctions.find((item) => item.id === junction)?.label ?? junction ?? "Default junction"
  const laneLabel = (id: string) => options?.lanes.find((lane) => lane.id === id)?.label ?? id
  return <div className="flex flex-col gap-3 text-sm">
    <p><strong>RL candidate:</strong> {label}. Other junctions use their saved fixed-time or all-way-stop plans.</p>
    <p><strong>Routing:</strong> {config.routing_mode ?? "adaptive"}. <strong>Scheduled changes:</strong> {config.events?.length ?? 0}.</p>
    {(config.closed_lanes ?? []).map((lane) => <p key={lane}>Initially closed: {laneLabel(lane)}</p>)}
    {Object.entries(config.slow_lanes ?? {}).map(([lane, factor]) => <p key={lane}>Initial speed: {laneLabel(lane)} — {Math.round(factor * 100)}%</p>)}
    {[...(config.events ?? [])].sort((a, b) => a.time - b.time).map((event, index) => <p key={index}>
      At {event.time}s: {laneLabel(event.lane_id)} — {event.closed === undefined ? "" : event.closed ? "close entry" : "reopen"}
      {event.speed_factor === undefined ? "" : ` ${Math.round(event.speed_factor * 100)}% speed`}
    </p>)}
  </div>
}

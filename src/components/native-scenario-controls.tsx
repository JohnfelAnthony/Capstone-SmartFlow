import * as React from "react"
import { ArrowDownIcon, ArrowUpIcon, LinkIcon, PlusIcon, TrashIcon, UnlinkIcon } from "lucide-react"
import type { LaneEvent, NativeScenarioConfig, NativeScenarioOptions, SignalPlan } from "@/api/native-scenario"
import { designSignalPlan, type SignalDesignResult } from "@/api/signal-design"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { automaticMaximumRed, fixedTimeRed, groupWithNext, MAXIMUM_RED_BOUNDS, movePhase as movePhaseOf, phaseKey, splitGroup } from "@/lib/signal-plan"
import { matchingMixPreset, mixShares } from "@/lib/vehicle-mix"

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
  const ownRed = fixedTimeRed(plan)
  const customMaximumRed = plan.maximum_red_seconds !== undefined
  function setMaximumRedMode(mode: string) {
    const next = { ...plan }
    if (mode === "custom") next.maximum_red_seconds = Math.min(automaticMaximumRed(plan), MAXIMUM_RED_BOUNDS.max)
    else delete next.maximum_red_seconds
    onChange({ ...value, signal_plans: { ...value.signal_plans, [junction.id]: next } })
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
  function movePhase(index: number, direction: -1 | 1) {
    updatePlan(movePhaseOf(plan, index, direction))
  }
  function regroup(edit: ReturnType<typeof groupWithNext>) {
    if (edit) updatePlan({ phase_order: edit.phase_order, phase_greens: edit.phase_greens })
  }
  function setPhaseGreens(enabled: boolean) {
    updatePlan({ phase_greens: enabled ? plan.phase_order.map(() => plan.green_seconds) : undefined })
  }
  const [flows, setFlows] = React.useState<Record<string, number>>({})
  const [design, setDesign] = React.useState<{ result?: SignalDesignResult; error?: string; busy?: boolean }>({})
  async function designWithWebster() {
    setDesign({ busy: true })
    const shares = mixShares(value.vehicle_mix ?? options.defaults.vehicle_mix ?? {})
    const approach_counts = Object.fromEntries(junction.approaches.map((approach) => [approach,
      Object.fromEntries(shares.map(({ type, percent }) => [type, (flows[approach] ?? 0) * percent / 100]))]))
    try {
      const response = await designSignalPlan({ network_id: options.network_id, junction: junction.id, phase_order: plan.phase_order, approach_counts,
        base_plan: { yellow_seconds: plan.yellow_seconds, all_red_seconds: plan.all_red_seconds, minimum_green: plan.minimum_green, maximum_green: plan.maximum_green } })
      updatePlan({ phase_order: response.plan.phase_order, phase_greens: response.plan.phase_greens })
      setDesign({ result: response.result })
    } catch (error) {
      setDesign({ error: error instanceof Error ? error.message : "The design could not be made." })
    }
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
        options={[{ value: "signalized", label: "Traditional signal (fixed-time)" }, { value: "all_way_stop", label: "All-way stop" }]}
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
        <FieldGroup className="grid sm:grid-cols-2">
          <Field>
            <NativeSelect label="Pedestrian phase" value={plan.pedestrian_phase ?? "on_call"}
              options={[{ value: "on_call", label: "On call" }, { value: "every_cycle", label: "Every cycle" }]}
              onChange={(pedestrian_phase) => updatePlan({ pedestrian_phase: pedestrian_phase as SignalPlan["pedestrian_phase"] })} />
            <FieldDescription>On call skips the walk phase when nobody is waiting. Fixed-time and RL control follow the same rule.</FieldDescription>
          </Field>
          <Field>
            <NativeSelect label="Maximum red" value={customMaximumRed ? "custom" : "automatic"}
              options={[{ value: "automatic", label: `Automatic (${automaticMaximumRed(plan)} s)` }, { value: "custom", label: "Custom" }]}
              onChange={setMaximumRedMode} />
            <FieldDescription>A waiting approach always gets green within this time, under any controller. Automatic is 120 s, or this plan’s own red ({ownRed} s) if longer.</FieldDescription>
          </Field>
          {customMaximumRed && <NativeNumber label="Custom maximum red (seconds)" value={plan.maximum_red_seconds ?? 0}
            min={MAXIMUM_RED_BOUNDS.min} max={MAXIMUM_RED_BOUNDS.max} onChange={(maximum_red_seconds) => updatePlan({ maximum_red_seconds })} />}
        </FieldGroup>
        {customMaximumRed && (plan.maximum_red_seconds ?? 0) < ownRed &&
          <Alert variant="destructive"><AlertDescription>Maximum red must be at least this plan’s own fixed-time red ({ownRed} s), or the fixed-time baseline would be interrupted.</AlertDescription></Alert>}
        <Field>
          <FieldLabel>Phase order</FieldLabel>
          <ol className="flex flex-col gap-2">{plan.phase_order.map((phase, index) => {
            const key = phaseKey(phase)
            const label = key === "pedestrian" ? "Pedestrian crossing" : Array.isArray(phase) ? `${phase.join(" + ")} approaches together` : `${phase} approach`
            return <li key={key} className="flex flex-wrap items-center gap-2">
              <span className="min-w-40 flex-1">{index + 1}. {label}</span>
              {plan.phase_greens && <Input type="number" min={plan.minimum_green} max={plan.maximum_green} step={.1} className="w-24" aria-label={`Green for ${label} (seconds)`}
                value={plan.phase_greens[index] ?? plan.green_seconds}
                onChange={(event) => updatePlan({ phase_greens: plan.phase_greens?.map((green, position) => position === index ? Number(event.target.value) : green) })} />}
              <Button type="button" size="icon-sm" variant="outline" disabled={index === 0} aria-label={`Move ${key} earlier`} onClick={() => movePhase(index, -1)}><ArrowUpIcon /></Button>
              <Button type="button" size="icon-sm" variant="outline" disabled={index === plan.phase_order.length - 1} aria-label={`Move ${key} later`} onClick={() => movePhase(index, 1)}><ArrowDownIcon /></Button>
              {Array.isArray(phase)
                ? <Button type="button" size="icon-sm" variant="outline" aria-label={`Split ${key}`} onClick={() => regroup(splitGroup(plan, index))}><UnlinkIcon /></Button>
                : key !== "pedestrian" && groupWithNext(plan, index) !== null && <Button type="button" size="icon-sm" variant="outline" aria-label={`Give ${key} and the next phase one shared green`} onClick={() => regroup(groupWithNext(plan, index))}><LinkIcon /></Button>}
            </li>
          })}</ol>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={plan.phase_greens !== undefined} onCheckedChange={(checked) => setPhaseGreens(checked === true)} />A different green for each phase</label>
          <FieldDescription>Every available approach and the protected crossing appears once. Approaches in one phase may enter together; turns that cross are kept apart by the junction rules, not by a protected phase. Pedestrian clearance remains enforced.</FieldDescription>
        </Field>
        <Field>
          <FieldLabel>Design with Webster</FieldLabel>
          <FieldDescription>Enter the expected vehicles per hour on each approach. The classes follow this scenario's vehicle mix. The result uses provisional passenger-car equivalents and saturation flows and needs field review before any claim.</FieldDescription>
          <FieldGroup className="grid sm:grid-cols-2">{junction.approaches.map((approach) =>
            <NativeNumber key={approach} label={`${approach} (vehicles per hour)`} value={flows[approach] ?? 0} min={0} max={20000} step={10}
              onChange={(next) => setFlows({ ...flows, [approach]: next })} />)}</FieldGroup>
          <Button type="button" variant="outline" disabled={design.busy} onClick={() => void designWithWebster()}>Design with Webster</Button>
          {design.error && <Alert variant="destructive"><AlertDescription>{design.error}</AlertDescription></Alert>}
          {design.result && <Alert><AlertDescription>Provisional plan: {design.result.cycle_seconds} s cycle, greens {design.result.phase_greens.join(", ")} s (Webster cycle {design.result.webster_cycle_seconds} s, flow ratio {design.result.total_flow_ratio.toFixed(2)}).
            {design.result.warnings.map((warning) => ` ${warning}.`)}</AlertDescription></Alert>}
        </Field>
      </> : <Alert><AlertDescription>Vehicles stop before taking turns. This junction cannot host an RL signal controller while set to all-way stop.</AlertDescription></Alert>}
      <div className="flex flex-col gap-2" aria-label="Configured junction controllers">
        {options.junctions.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm">{item.label}</span>
          <Badge variant="outline">{value.signal_plans?.[item.id]?.mode === "all_way_stop" ? "All-way stop" : item.id === selected ? "RL candidate / fixed-time baseline" : "Traditional signal"}</Badge>
        </div>)}
      </div>
    </FieldSet>

    <FieldSet>
      <FieldLegend>Vehicle mix</FieldLegend>
      <NativeSelect label="Vehicle mix" value={matchingMixPreset(value.vehicle_mix, options.vehicle_mix_presets) ?? "custom"}
        options={[...Object.entries(options.vehicle_mix_presets).map(([key, preset]) => ({ value: key, label: preset.label })),
          { value: "custom", label: "Custom (saved)", disabled: true }]}
        onChange={(key) => onChange({ ...value, vehicle_mix: { ...options.vehicle_mix_presets[key].mix } })} />
      {value.vehicle_mix && <FieldDescription>
        {mixShares(value.vehicle_mix).map(({ type, percent }) => `${type[0].toUpperCase()}${type.slice(1)} ${Math.round(percent)}%`).join(" · ")}.
        {" "}Tagum shares are a provisional estimate, not a count.
      </FieldDescription>}
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

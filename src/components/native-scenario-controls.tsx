import * as React from "react"
import type { NativeScenarioConfig, NativeScenarioOptions } from "@/api/native-scenario"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
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

export function NativeScenarioSummary({ config, options }: { config: NativeScenarioConfig; options: NativeScenarioOptions | null }) {
  const junction = config.controlled_junction ?? options?.defaults.controlled_junction
  const label = options?.junctions.find((item) => item.id === junction)?.label ?? junction ?? "Default junction"
  const laneLabel = (id: string) => options?.lanes.find((lane) => lane.id === id)?.label ?? id
  const routing = config.routing_mode === "adaptive"
    ? "Avoid jams (adaptive): drivers steer around congestion as well as closed roads, in this whole scenario."
    : options?.routing_follows_closure_choice ? "Drivers are rerouted around closed roads only, not around congestion."
    : `${config.routing_mode ?? "adaptive"}.`
  return <div className="flex flex-col gap-3 text-sm">
    <p><strong>RL candidate:</strong> {label}. Other junctions use their saved fixed-time or all-way-stop plans.</p>
    <p><strong>Routing:</strong> {routing} <strong>Scheduled changes:</strong> {config.events?.length ?? 0}.</p>
    {Object.entries(config.slow_lanes ?? {}).map(([lane, factor]) => <p key={lane}>Initial speed: {laneLabel(lane)} — {Math.round(factor * 100)}%</p>)}
    {[...(config.events ?? [])].filter((event) => event.speed_factor !== undefined).sort((a, b) => a.time - b.time).map((event, index) => <p key={index}>
      At {event.time}s: {laneLabel(event.lane_id)} — {Math.round((event.speed_factor ?? 1) * 100)}% speed
    </p>)}
  </div>
}

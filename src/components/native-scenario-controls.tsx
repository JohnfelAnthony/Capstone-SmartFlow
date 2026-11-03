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

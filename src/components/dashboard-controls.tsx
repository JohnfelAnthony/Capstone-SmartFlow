import * as React from "react"
import { PauseIcon, PlayIcon, RotateCcwIcon, Settings2Icon, SquareIcon } from "lucide-react"

import type { ApiScenario } from "@/api/scenarios"
import type { NativeScenarioConfig } from "@/api/native-scenario"
import type { RLModelRecord } from "@/api/rl"
import type { SimulationRunRecord, SimulationStatePayload } from "@/api/simulation"
import { NativeSelect } from "@/components/native-scenario-controls"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { Slider } from "@/components/ui/slider"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

const durationOptions = [
  { label: "5 minutes", value: "300" },
  { label: "10 minutes", value: "600" },
  { label: "15 minutes", value: "900" },
]
const speedOptions = [0.25, 0.5, 1, 2, 4].map((value) => ({ value: String(value), label: `${value}× speed` }))

function CompactSelect({ label, value, options, disabled, onChange, className }: {
  label: string; value: string; options: Array<{ value: string; label: string; disabled?: boolean }>
  disabled?: boolean; onChange: (value: string) => void; className?: string
}) {
  return <Select items={options} value={value} onValueChange={(next) => next !== null && onChange(next)} disabled={disabled}>
    <SelectTrigger size="sm" aria-label={label} className={className}><SelectValue placeholder={label} /></SelectTrigger>
    <SelectContent><SelectGroup>{options.map((option) =>
      <SelectItem key={option.value} value={option.value} disabled={option.disabled}>{option.label}</SelectItem>)}</SelectGroup></SelectContent>
  </Select>
}

export type DashboardControlsProps = {
  simulation: SimulationStatePayload | null
  scenarios: ApiScenario[]
  selectedScenarioId: string
  scenarioConfig: NativeScenarioConfig | null
  models: RLModelRecord[]
  controlMode: string
  seed: string
  durationSeconds: string
  recordedRuns: SimulationRunRecord[]
  selectedRecordedRunId: string
  isBusy: boolean
  canOperate: boolean
  canTakeOver: boolean
  status: string
  onScenarioChange: (value: string) => void
  onControlModeChange: (value: string) => void
  onSeedChange: (value: string) => void
  onDurationChange: (value: string) => void
  onApply: () => void
  onSpeedChange: (value: number) => void
  onRecordedRunChange: (value: string) => void
  onLoadRecording: () => void
  onStartPlayback: () => void
  onSeekPlayback: (frameIndex: number) => void
  onStart: () => void
  onPause: () => void
  onStop: () => void
  onReset: () => void
  onTakeOver: () => void
}

export function DashboardControls(props: DashboardControlsProps) {
  const { simulation, isBusy, canOperate } = props
  const [setupOpen, setSetupOpen] = React.useState(false)
  const [replayChosen, setReplayChosen] = React.useState(false)
  const [draggedFrame, setDraggedFrame] = React.useState<number | null>(null)
  const status = simulation?.status ?? "stopped"
  const isRunning = status === "running"
  const isPaused = status === "paused"
  const isActive = isRunning || isPaused
  const isPlayback = simulation?.control_mode === "playback"
  const showReplay = isPlayback || replayChosen
  const frameCount = Number(simulation?.state.playback?.frame_count ?? 0) || 0
  const frameIndex = Math.min(Number(simulation?.state.playback?.frame_index ?? 0) || 0, Math.max(frameCount - 1, 0))
  const selectedRecording = props.recordedRuns.find((run) => String(run.id) === props.selectedRecordedRunId)
  const canLoadRecording = selectedRecording?.status === "completed"
  const controllerOptions = [
    { label: "Fixed-time plan (baseline)", value: "fixed-time" },
    ...props.models.filter((model) => model.compatible && model.controlled_junction === props.scenarioConfig?.controlled_junction)
      .map((model) => ({ label: `${model.algorithm} model #${model.id} · ${model.name ?? "trained policy"}`, value: `${model.algorithm.toLowerCase()}:${model.id}` })),
  ]
  const isLocked = isBusy || !canOperate

  function handleSourceChange(values: string[]) {
    const next = values[0]
    if (!next) return
    setReplayChosen(next === "replay")
    if (next === "live" && isPlayback) props.onReset()
  }

  return <Card size="sm">
    <CardContent className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <ToggleGroup value={[showReplay ? "replay" : "live"]} onValueChange={handleSourceChange} variant="outline" size="sm" aria-label="Simulation source" disabled={isLocked || isActive}>
          <ToggleGroupItem value="live">Live</ToggleGroupItem>
          <ToggleGroupItem value="replay">Replay</ToggleGroupItem>
        </ToggleGroup>

        {showReplay ? <>
          <CompactSelect label="Recording" value={props.selectedRecordedRunId} disabled={isLocked || props.recordedRuns.length === 0} onChange={props.onRecordedRunChange} className="w-56"
            options={props.recordedRuns.map((run) => ({ value: String(run.id), label: `#${run.id} ${run.scenario_name ?? "Recorded run"}`, disabled: run.status !== "completed" }))} />
          <Button size="sm" variant="outline" disabled={isLocked || !canLoadRecording} onClick={props.onLoadRecording}>Load</Button>
          <Button size="sm" disabled={isLocked || !isPlayback || isRunning} onClick={props.onStartPlayback}><PlayIcon data-icon="inline-start" />Play</Button>
          <Button size="sm" variant="outline" disabled={isLocked || !isRunning} onClick={props.onPause}><PauseIcon data-icon="inline-start" />Pause</Button>
          <div className="flex min-w-48 flex-1 items-center gap-3">
            <Slider aria-label="Recording position" min={0} max={Math.max(frameCount - 1, 0)} value={[draggedFrame ?? frameIndex]} disabled={isLocked || !isPlayback || frameCount <= 1}
              onValueChange={(next) => setDraggedFrame(Array.isArray(next) ? next[0] : next)}
              onValueCommitted={(next) => { setDraggedFrame(null); props.onSeekPlayback(Array.isArray(next) ? next[0] : next) }} />
            <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">{frameCount > 0 ? `${frameIndex + 1}/${frameCount}` : "0/0"}</span>
          </div>
        </> : <>
          <Button size="sm" disabled={isLocked || !props.selectedScenarioId || isRunning} onClick={isPaused ? props.onPause : props.onStart}>
            <PlayIcon data-icon="inline-start" />{isPaused ? "Resume" : "Start"}
          </Button>
          <Button size="sm" variant="outline" disabled={isLocked || !isRunning} onClick={props.onPause}><PauseIcon data-icon="inline-start" />Pause</Button>
          <Button size="sm" variant="outline" disabled={isLocked || !isActive} onClick={props.onStop}><SquareIcon data-icon="inline-start" />Stop</Button>
          <Button size="icon-sm" variant="ghost" disabled={isLocked} onClick={props.onReset} aria-label="Reset simulation" title="Reset simulation"><RotateCcwIcon /></Button>
        </>}

        <CompactSelect label="Speed" value={String(simulation?.speed_multiplier ?? 1)} options={speedOptions} disabled={isLocked} onChange={(next) => props.onSpeedChange(Number(next))} />

        <Sheet open={setupOpen} onOpenChange={setSetupOpen}>
          <SheetTrigger render={<Button size="sm" variant="outline" className="ml-auto" />}><Settings2Icon data-icon="inline-start" />Setup</SheetTrigger>
          <SheetContent className="overflow-y-auto">
            <SheetHeader>
              <SheetTitle>Simulation setup</SheetTitle>
              <SheetDescription>Choose what to simulate and which signal controller to test. Edit roads, demand and events on the Scenarios page.</SheetDescription>
            </SheetHeader>
            <FieldGroup className="px-4">
              <NativeSelect label="Scenario" value={props.selectedScenarioId} disabled={isLocked || isActive || props.scenarios.length === 0} onChange={props.onScenarioChange}
                options={props.scenarios.map((scenario) => ({ label: scenario.name, value: String(scenario.id) }))} />
              <NativeSelect label="Signal controller" value={props.controlMode} disabled={isLocked || isActive || isPlayback} onChange={props.onControlModeChange} options={controllerOptions} />
              <NativeSelect label="Duration" value={props.durationSeconds} disabled={isLocked || isActive} onChange={props.onDurationChange} options={durationOptions} />
              <Field>
                <FieldLabel htmlFor="run-seed">Random seed</FieldLabel>
                <Input id="run-seed" type="number" min="0" max="4294967295" step="1" value={props.seed} disabled={isLocked || isActive || isPlayback} onChange={(event) => props.onSeedChange(event.target.value)} />
                <FieldDescription>Use the same seed for the fixed-time and RL runs so their results can be compared fairly.</FieldDescription>
              </Field>
              {props.canTakeOver ? <Alert>
                <AlertDescription className="flex flex-col gap-2">
                  Another user controls the shared simulation.
                  <Button size="sm" variant="destructive" disabled={isBusy} onClick={props.onTakeOver}>Take over (stop and reset)</Button>
                </AlertDescription>
              </Alert> : null}
            </FieldGroup>
            <SheetFooter>
              <Button disabled={isLocked || isActive || !props.selectedScenarioId} onClick={() => { props.onApply(); setSetupOpen(false) }}>Apply setup</Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant={isRunning ? "default" : "outline"}>{isPlayback ? "Replay" : status}</Badge>
        <span>{props.status}</span>
      </div>
    </CardContent>
  </Card>
}

import * as React from "react"
import { ChevronDownIcon, PauseIcon, PlayIcon, RotateCcwIcon, SquareIcon } from "lucide-react"

import type { ApiScenario } from "@/api/scenarios"
import type { NativeScenarioConfig, NativeScenarioOptions } from "@/api/native-scenario"
import type { RLModelRecord } from "@/api/rl"
import type { SimulationRunRecord, SimulationStatePayload } from "@/api/simulation"
import { NativeSelect } from "@/components/native-scenario-controls"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { isRlControl } from "@/lib/control-labels"

const durationOptions = [
  { label: "5 minutes", value: "300" },
  { label: "10 minutes", value: "600" },
  { label: "15 minutes", value: "900" },
]
const speedOptions = [0.25, 0.5, 1, 2, 4].map((value) => ({ value: String(value), label: `${value}×` }))
const METHODS = [
  { value: "no-signal", label: "No signal", description: "Today" },
  { value: "fixed-time", label: "Fixed-time", description: "Saved plan" },
  { value: "ql", label: "QL", description: "Tabular" },
  { value: "dql", label: "DQL", description: "Deep Q-Learning" },
  { value: "ppo", label: "PPO", description: "Policy gradient" },
]
const clock = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`

/** Play/pause/stop, speed and the elapsed clock; sits in the map card's bottom bar. */
export function SimControlBar({ simulation, elapsedSeconds, isBusy, canOperate, canStart, onStart, onStartPlayback, onPause, onStop, onReset, onSpeedChange, onSeekPlayback }: {
  simulation: SimulationStatePayload | null; elapsedSeconds: number; isBusy: boolean; canOperate: boolean; canStart: boolean
  onStart: () => void; onStartPlayback: () => void; onPause: () => void; onStop: () => void; onReset: () => void
  onSpeedChange: (value: number) => void; onSeekPlayback: (frameIndex: number) => void
}) {
  const [draggedFrame, setDraggedFrame] = React.useState<number | null>(null)
  const status = simulation?.status ?? "stopped"
  const isRunning = status === "running", isPaused = status === "paused", isActive = isRunning || isPaused
  const isPlayback = simulation?.control_mode === "playback"
  const isLocked = isBusy || !canOperate
  const frameCount = Number(simulation?.state.playback?.frame_count ?? 0) || 0
  const frameIndex = Math.min(Number(simulation?.state.playback?.frame_index ?? 0) || 0, Math.max(frameCount - 1, 0))
  const durationSeconds = simulation?.duration_seconds ?? 0
  const canPlay = isPaused || (isPlayback ? !isRunning : canStart && !isActive)
  return <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
    {isRunning
      ? <Button size="sm" disabled={isLocked} onClick={onPause}><PauseIcon data-icon="inline-start" />Pause</Button>
      : <Button size="sm" disabled={isLocked || !canPlay} onClick={isPaused ? onPause : isPlayback ? onStartPlayback : onStart}><PlayIcon data-icon="inline-start" />{isPaused ? "Resume" : "Play"}</Button>}
    <Button size="sm" variant="outline" disabled={isLocked || !isActive} onClick={onStop}><SquareIcon data-icon="inline-start" />Stop</Button>
    <Button size="icon-sm" variant="ghost" disabled={isLocked} onClick={onReset} aria-label="Reset simulation" title="Reset simulation"><RotateCcwIcon /></Button>
    <Select items={speedOptions} value={String(simulation?.speed_multiplier ?? 1)} onValueChange={(next) => next !== null && onSpeedChange(Number(next))} disabled={isLocked}>
      <SelectTrigger size="sm" aria-label="Playback speed"><SelectValue /></SelectTrigger>
      <SelectContent><SelectGroup>{speedOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectGroup></SelectContent>
    </Select>
    <div className="flex min-w-44 flex-1 items-center gap-3">
      <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">{clock(elapsedSeconds)} / {clock(durationSeconds)}</span>
      {isPlayback
        ? <Slider aria-label="Recording position" min={0} max={Math.max(frameCount - 1, 0)} value={[draggedFrame ?? frameIndex]} disabled={isLocked || frameCount <= 1}
            onValueChange={(next) => setDraggedFrame(Array.isArray(next) ? next[0] : next)}
            onValueCommitted={(next) => { setDraggedFrame(null); onSeekPlayback(Array.isArray(next) ? next[0] : next) }} />
        : <Slider aria-label="Run progress" min={0} max={Math.max(durationSeconds, 1)} value={[Math.min(elapsedSeconds, durationSeconds)]} disabled />}
    </div>
    {isPlayback ? <Badge variant="secondary">Replay</Badge> : null}
  </div>
}

/** Centred over the idle map: the one place to pick what to run or which recording to replay. */
export function SetupCard({ scenarios, selectedScenarioId, durationSeconds, seed, controllerLabel, recordedRuns, selectedRecordedRunId, isBusy, canOperate, canTakeOver,
  onScenarioChange, onDurationChange, onSeedChange, onStart, onRecordedRunChange, onLoadRecording, onTakeOver }: {
  scenarios: ApiScenario[]; selectedScenarioId: string; durationSeconds: string; seed: string; controllerLabel: string
  recordedRuns: SimulationRunRecord[]; selectedRecordedRunId: string; isBusy: boolean; canOperate: boolean; canTakeOver: boolean
  onScenarioChange: (value: string) => void; onDurationChange: (value: string) => void; onSeedChange: (value: string) => void; onStart: () => void
  onRecordedRunChange: (value: string) => void; onLoadRecording: () => void; onTakeOver: () => void
}) {
  const isLocked = isBusy || !canOperate
  const completedRecordings = recordedRuns.filter((run) => run.status === "completed")
  return <Card className="w-full max-w-md shadow-lg">
    <CardHeader>
      <CardTitle>Simulation setup</CardTitle>
      <CardDescription>Edit roads, demand and events on the Scenarios page.</CardDescription>
    </CardHeader>
    <CardContent>
      <Tabs defaultValue="new">
        <TabsList className="w-full">
          <TabsTrigger value="new">New run</TabsTrigger>
          <TabsTrigger value="replay">Replay recording</TabsTrigger>
        </TabsList>
        <TabsContent value="new">
          <FieldGroup className="pt-2">
            <NativeSelect label="Scenario" value={selectedScenarioId} disabled={isLocked || scenarios.length === 0} onChange={onScenarioChange}
              options={scenarios.map((scenario) => ({ label: scenario.name, value: String(scenario.id) }))} />
            <NativeSelect label="Duration" value={durationSeconds} disabled={isLocked} onChange={onDurationChange} options={durationOptions} />
            <p className="text-sm text-muted-foreground">Controller: <span className="text-foreground">{controllerLabel}</span>. Change it in Signal control.</p>
            <Collapsible>
              <CollapsibleTrigger render={<Button variant="ghost" size="sm" className="-ml-2" />}><ChevronDownIcon data-icon="inline-start" />Advanced</CollapsibleTrigger>
              <CollapsibleContent>
                <Field className="pt-2">
                  <FieldLabel htmlFor="run-seed">Random seed</FieldLabel>
                  <Input id="run-seed" type="number" min="0" max="4294967295" step="1" value={seed} disabled={isLocked} onChange={(event) => onSeedChange(event.target.value)} />
                  <FieldDescription>Use the same seed for fixed-time and RL runs so their results compare fairly.</FieldDescription>
                </Field>
              </CollapsibleContent>
            </Collapsible>
            <Button disabled={isLocked || !selectedScenarioId} onClick={onStart}><PlayIcon data-icon="inline-start" />Start simulation</Button>
          </FieldGroup>
        </TabsContent>
        <TabsContent value="replay">
          <FieldGroup className="pt-2">
            <NativeSelect label="Recording" value={selectedRecordedRunId} disabled={isLocked || completedRecordings.length === 0} onChange={onRecordedRunChange}
              options={completedRecordings.map((run) => ({ value: String(run.id), label: `#${run.id} ${run.scenario_name ?? "Recorded run"}` }))} />
            {completedRecordings.length === 0 ? <p className="text-sm text-muted-foreground">No completed recordings yet.</p> : null}
            <Button disabled={isLocked || !completedRecordings.some((run) => String(run.id) === selectedRecordedRunId)} onClick={onLoadRecording}>Load recording</Button>
          </FieldGroup>
        </TabsContent>
      </Tabs>
      {canTakeOver ? <Alert className="mt-4">
        <AlertDescription className="flex flex-col gap-2">
          Another user controls the shared simulation.
          <Button size="sm" variant="destructive" disabled={isBusy} onClick={onTakeOver}>Take over (stop and reset)</Button>
        </AlertDescription>
      </Alert> : null}
    </CardContent>
  </Card>
}

/** RL methods are offered only when a compatible trained model exists; RL always controls one junction. */
export function SignalControlCard({ simulation, models, controlMode, scenarioConfig, nativeOptions, isLocked, onControlModeChange }: {
  simulation: SimulationStatePayload | null; models: RLModelRecord[]; controlMode: string; scenarioConfig: NativeScenarioConfig | null
  nativeOptions: NativeScenarioOptions | null; isLocked: boolean; onControlModeChange: (value: string) => void
}) {
  const controlledJunction = scenarioConfig?.controlled_junction
  const compatibleModels = models.filter((model) => model.compatible && model.controlled_junction === controlledJunction)
  const latestModel = (method: string) => compatibleModels.filter((model) => model.algorithm.toLowerCase() === method).sort((a, b) => b.id - a.id)[0]
  const isPlayback = simulation?.control_mode === "playback"
  const isActive = simulation?.status === "running" || simulation?.status === "paused"
  const activeMode = isPlayback ? simulation?.state.playback?.source_controller ?? "playback" : isActive ? simulation?.control_mode ?? controlMode : controlMode
  const selectedMethod = activeMode.split(":")[0]
  const usesRl = isRlControl(selectedMethod)
  const junctionLabel = nativeOptions?.junctions.find((junction) => junction.id === controlledJunction)?.label ?? controlledJunction ?? "the selected junction"
  const junctionNumber = /^J\d+/.exec(junctionLabel)?.[0] ?? junctionLabel
  const statusText = isPlayback ? `Replaying ${simulation?.state.playback?.source_controller_label ?? "a recording"}`
    : isActive ? `${simulation?.status === "running" ? "Running" : "Paused"}${usesRl ? " (RL inference)" : ""}` : "Idle"
  function chooseMethod(values: string[]) {
    const method = values[0]
    if (!method) return
    if (method === "fixed-time" || method === "no-signal") { onControlModeChange(method); return }
    const model = latestModel(method)
    if (model) onControlModeChange(`${method}:${model.id}`)
  }
  return <Card size="sm">
    <CardHeader>
      <CardTitle>Signal control</CardTitle>
      <CardDescription>{selectedMethod === "no-signal" ? "Every junction runs without signals; vehicles go in order of arrival." : usesRl ? `RL on ${junctionLabel}; other junctions run fixed-time.` : "Every junction runs its saved fixed-time plan."}</CardDescription>
    </CardHeader>
    <CardContent>
      <ToggleGroup value={[selectedMethod]} onValueChange={chooseMethod} variant="outline" className="grid w-full grid-cols-5" aria-label="Signal controller" disabled={isLocked || isActive || isPlayback}>
        {METHODS.map((method) => {
          const unavailable = isRlControl(method.value) && !latestModel(method.value)
          return <ToggleGroupItem key={method.value} value={method.value} disabled={unavailable} className="h-auto flex-col gap-0 py-1.5"
            title={unavailable ? `No trained ${method.label} model for ${junctionNumber} yet` : method.description}>
            <span className="text-sm font-medium">{method.label}</span>
            <span className="text-[10px] text-muted-foreground">{method.description}</span>
          </ToggleGroupItem>
        })}
      </ToggleGroup>
    </CardContent>
    <CardFooter className="flex items-center gap-2 text-xs text-muted-foreground">
      <Badge variant={isActive ? "default" : "outline"}>{statusText}</Badge>
      {compatibleModels.length === 0 ? <span>Train a model in RL Training to enable QL/DQL/PPO.</span> : null}
    </CardFooter>
  </Card>
}

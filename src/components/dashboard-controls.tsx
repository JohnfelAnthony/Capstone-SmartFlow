import * as React from "react"
import { ChevronDownIcon, PauseIcon, PlayIcon, RotateCcwIcon, SquareIcon } from "lucide-react"

import type { ApiScenario } from "@/api/scenarios"
import type { RLModelRecord } from "@/api/rl"
import type { SimulationRunRecord, SimulationStatePayload } from "@/api/simulation"
import { NativeSelect } from "@/components/native-scenario-controls"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { NO_SIGNAL_LABEL } from "@/lib/control-labels"

const durationOptions = [
  { label: "5 minutes", value: "300" },
  { label: "10 minutes", value: "600" },
  { label: "15 minutes", value: "900" },
]
const speedOptions = [0.25, 0.5, 1, 2, 4].map((value) => ({ value: String(value), label: `${value}×` }))
const RL_METHODS = ["ql", "dql", "ppo"]
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
export function SetupCard({ scenarios, selectedScenarioId, durationSeconds, seed, controlMode, models, controlledJunction, recordedRuns, selectedRecordedRunId, isBusy, canOperate, canTakeOver,
  onScenarioChange, onDurationChange, onSeedChange, onControlModeChange, onStart, onRecordedRunChange, onLoadRecording, onTakeOver }: {
  scenarios: ApiScenario[]; selectedScenarioId: string; durationSeconds: string; seed: string; controlMode: string; models: RLModelRecord[]; controlledJunction: string | undefined
  recordedRuns: SimulationRunRecord[]; selectedRecordedRunId: string; isBusy: boolean; canOperate: boolean; canTakeOver: boolean
  onScenarioChange: (value: string) => void; onDurationChange: (value: string) => void; onSeedChange: (value: string) => void; onControlModeChange: (value: string) => void; onStart: () => void
  onRecordedRunChange: (value: string) => void; onLoadRecording: () => void; onTakeOver: () => void
}) {
  const isLocked = isBusy || !canOperate
  const completedRecordings = recordedRuns.filter((run) => run.status === "completed")
  // RL is offered only with a compatible trained model; each method runs its latest one.
  const compatibleModels = models.filter((model) => model.compatible && model.controlled_junction === controlledJunction)
  const rlOptions = RL_METHODS.flatMap((method) => {
    const latest = compatibleModels.filter((model) => model.algorithm.toLowerCase() === method).sort((a, b) => b.id - a.id)[0]
    return latest ? [{ value: `${method}:${latest.id}`, label: `${latest.algorithm} model #${latest.id}` }] : []
  })
  const controlOptions = [{ value: "no-signal", label: NO_SIGNAL_LABEL }, { value: "fixed-time", label: "Traditional fixed-time plan" }, ...rlOptions]
  // A finished run can leave a mode this scenario no longer offers; still name it rather than show a blank.
  if (!controlOptions.some((option) => option.value === controlMode)) controlOptions.push({ value: controlMode, label: controlMode })
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
            <div className="flex flex-col gap-2">
              <NativeSelect label="Signal control" value={controlMode} disabled={isLocked} onChange={onControlModeChange} options={controlOptions} />
              {rlOptions.length === 0 ? <FieldDescription>Train a model in RL Training to enable QL, DQL and PPO.</FieldDescription> : null}
            </div>
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

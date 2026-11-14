import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"
import { SetupCard, SimControlBar } from "@/components/dashboard-controls"
import { blockedStartMessage } from "@/lib/control-labels"

const scenario = { id: 1, name: "Site A peak", network_id: "tagum_site_a", engine_config: {} } as never
const setupProps = {
  scenarios: [scenario], selectedScenarioId: "1", durationSeconds: "300", seed: "42", controlMode: "fixed-time", models: [], controlledJunction: undefined,
  recordedRuns: [], selectedRecordedRunId: "", isBusy: false, canOperate: true, canTakeOver: false,
  onScenarioChange: vi.fn(), onDurationChange: vi.fn(), onSeedChange: vi.fn(), onControlModeChange: vi.fn(), onStart: vi.fn(),
  onRecordedRunChange: vi.fn(), onLoadRecording: vi.fn(), onTakeOver: vi.fn(),
}
const startButton = (html: string) => html.match(/<button[^>]*>(?:(?!<\/button>).)*(Start simulation|Preparing traffic…)<\/button>/)?.[0] ?? ""
const isDisabled = (button: string | undefined) => /^<button[^>]*\sdisabled=""/.test(button ?? "")

describe("dashboard setup card", () => {
  it("explains why Start is unavailable while training holds the workload slot, and links to RL Training", () => {
    const html = renderToStaticMarkup(createElement(SetupCard, { ...setupProps, blockingWorkload: "training/evaluation", onOpenTraining: vi.fn() }))
    expect(html).toContain("Start is unavailable")
    expect(html).toContain("An RL training or evaluation job is running")
    expect(html).toContain("Open RL Training")
    expect(isDisabled(startButton(html))).toBe(true)
  })

  it("keeps Start enabled and shows no alert when nothing else is running", () => {
    const html = renderToStaticMarkup(createElement(SetupCard, setupProps))
    expect(html).not.toContain("Start is unavailable")
    expect(isDisabled(startButton(html))).toBe(false)
  })

  it("omits the training link when the user cannot open RL Training, and names other workloads", () => {
    const html = renderToStaticMarkup(createElement(SetupCard, { ...setupProps, blockingWorkload: "training/evaluation" }))
    expect(html).not.toContain("Open RL Training")
    expect(blockedStartMessage("recording")).toContain("A recording is being generated")
    expect(blockedStartMessage("road network revision")).toContain("SmartFlow is busy with road network revision")
  })

  it("shows a spinner on Start while the server prepares traffic", () => {
    const html = renderToStaticMarkup(createElement(SetupCard, { ...setupProps, isStarting: true }))
    expect(startButton(html)).toContain("Preparing traffic…")
    expect(startButton(html)).toContain("animate-spin")
  })
})

describe("dashboard control bar", () => {
  it("disables Play when a start is not possible and spins while preparing", () => {
    const common = { simulation: null, elapsedSeconds: 0, isBusy: false, canOperate: true, onStart: vi.fn(), onStartPlayback: vi.fn(), onPause: vi.fn(), onStop: vi.fn(), onReset: vi.fn(), onSpeedChange: vi.fn(), onSeekPlayback: vi.fn() }
    const blocked = renderToStaticMarkup(createElement(SimControlBar, { ...common, canStart: false }))
    expect(isDisabled(blocked.match(/<button[^>]*>(?:(?!<\/button>).)*Play<\/button>/)?.[0])).toBe(true)
    const preparing = renderToStaticMarkup(createElement(SimControlBar, { ...common, canStart: true, isPreparing: true }))
    expect(preparing.match(/<button[^>]*>(?:(?!<\/button>).)*Play<\/button>/)?.[0]).toContain("animate-spin")
  })
})

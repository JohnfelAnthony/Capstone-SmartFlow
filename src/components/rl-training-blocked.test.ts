import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"
import { TrainingBlockedAlert } from "@/components/rl-training-page"
import { blockedTrainingMessage } from "@/lib/control-labels"

describe("RL Training blocked by another workload", () => {
  it("says a live simulation holds the slot and links to the Dashboard", () => {
    const html = renderToStaticMarkup(createElement(TrainingBlockedAlert, { workload: "live simulation", onOpenDashboard: vi.fn() }))
    expect(html).toContain("Training is unavailable")
    expect(html).toContain("A live simulation is running")
    expect(html).toContain("Open Dashboard")
  })

  it("offers no Dashboard link for a recording, which the Dashboard cannot stop", () => {
    const html = renderToStaticMarkup(createElement(TrainingBlockedAlert, { workload: "recording", onOpenDashboard: vi.fn() }))
    expect(html).toContain("A recording is being generated")
    expect(html).not.toContain("Open Dashboard")
    expect(blockedTrainingMessage("live simulation")).toContain("training or evaluation can start when it finishes or is stopped")
  })
})

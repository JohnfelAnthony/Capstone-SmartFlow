import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { expect, it, vi } from "vitest"

vi.mock("@/api/visual-network", () => ({ getVisualNetwork: vi.fn(() => new Promise(() => undefined)) }))
const { SimulationVisualization } = await import("@/simulation/simulation-visualization")

it("holds the workspace footprint with a skeleton instead of a bare loading line before the network arrives", () => {
  const html = renderToStaticMarkup(createElement(SimulationVisualization, { frame: null, networkId: null, networkPending: true, runKey: "idle", laneStreets: {} }))
  expect(html).toContain("sf-sim-layout")
  expect(html).toContain("sf-scene-viewport")
  expect(html).toContain('aria-label="Loading the simulation map"')
  expect(html).not.toContain("Loading native network")
})

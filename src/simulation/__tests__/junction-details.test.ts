import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { expect, it } from "vitest"
import { JunctionMiniMap } from "@/simulation/junction-details"
import { normalizeSceneGeometry } from "@/simulation/scene-geometry"
import { signalMovements } from "@/simulation/scene-summary"
import { crossNetwork } from "./geometry-fixture"

it("marks turns on both directions unavailable while a shared road drains", () => {
  const network = crossNetwork()
  for (const [from, to] of [["north-in", "west-out"], ["west-in", "north-out"]]) {
    const start = network.roads.find(road => road.lanes[0].id === from)!.shape.at(-1)!
    const end = network.roads.find(road => road.lanes[0].id === to)!.shape[0]
    const shape = [start, end]
    network.internal_lanes.push({
      index: 0, function: "internal", toward_intersection: true, away_from_intersection: true, shape,
      lanes: [{ id: from + "->" + to, index: 0, width: 3.3, allow: "passenger", disallow: "",
        source_length: 18, clip_start_position: 0, clip_end_position: 18, shape }],
    })
  }
  const geometry = normalizeSceneGeometry(network)
  const diagram = renderToStaticMarkup(createElement(JunctionMiniMap, {
    geometry, junctionId: "J", movements: signalMovements(geometry, "J", null),
    closed: new Set(["north-in", "north-out"]), shared: new Set(["north-in"]), summary: "Shared road draining",
  }))
  expect(diagram.match(/class="sf-mini-turn-unavailable"/g)).toHaveLength(2)
})

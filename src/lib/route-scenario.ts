import type { ClosureOverride, RouteSource } from "@/api/routes"
import type { NativeScenarioConfig } from "@/api/native-scenario"
import { writeClosures } from "@/lib/closures"

/** What the Route Planner hands to the New Scenario form: the site, an optional saved scenario to copy, and the closed roads. */
export type RouteScenarioDraft = {
  networkId: string
  baseScenarioId: number | null
  baseScenarioName: string | null
  closedLanes: string[]
  closureResponses: Record<string, string>
}

/** The planner's closures apply for the whole run, so they replace every closure (timed or not) in `config`. Speed events and all other settings stay. */
export function closuresIntoConfig(config: NativeScenarioConfig, draft: Pick<RouteScenarioDraft, "closedLanes" | "closureResponses">): NativeScenarioConfig {
  const wholeRun = Object.fromEntries(draft.closedLanes.map(lane => [lane, { start: 0, end: null }]))
  const next = writeClosures(structuredClone(config), wholeRun, [])
  const closed = new Set(draft.closedLanes)
  return { ...next, closure_responses: Object.fromEntries(Object.entries(draft.closureResponses).filter(([lane]) => closed.has(lane))) }
}

export function routeScenarioDraft({ source, context, closures, scenarioName }: {
  source: RouteSource | null; context: { network_id: string }; closures: ClosureOverride | undefined; scenarioName?: string
}): RouteScenarioDraft | null {
  if (!source || !closures?.closed_lanes.length) return null
  return {
    networkId: context.network_id,
    baseScenarioId: source.kind === "scenario" ? source.scenario_id : null,
    baseScenarioName: source.kind === "scenario" ? scenarioName ?? null : null,
    closedLanes: [...closures.closed_lanes].sort(),
    closureResponses: { ...closures.closure_responses },
  }
}

import type { SignalPlan } from "@/api/native-scenario"

// Mirrors simulation/scenario_config.py: DEFAULT_MAXIMUM_RED_SECONDS, fixed_red_seconds and the 30–600 s bounds.
export const DEFAULT_MAXIMUM_RED_SECONDS = 120
export const MAXIMUM_RED_BOUNDS = { min: 30, max: 600 }

/** How long each approach waits for green under the plan's own fixed-time cycle (cycle minus its green). */
export function fixedTimeRed(plan: Pick<SignalPlan, "phase_order" | "green_seconds" | "yellow_seconds" | "all_red_seconds">) {
  const cycle = plan.phase_order.reduce((total, service) =>
    total + plan.green_seconds + plan.all_red_seconds + (service === "pedestrian" ? 0 : plan.yellow_seconds), 0)
  return cycle - plan.green_seconds
}

/** The cap the engine uses when no maximum red is saved: 120 s, or the plan's own red if longer. */
export function automaticMaximumRed(plan: Parameters<typeof fixedTimeRed>[0]) {
  return Math.max(DEFAULT_MAXIMUM_RED_SECONDS, fixedTimeRed(plan))
}

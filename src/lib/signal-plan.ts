import type { SignalPlan } from "@/api/native-scenario"

// Mirrors simulation/scenario_config.py: DEFAULT_MAXIMUM_RED_SECONDS, phase_key, fixed_red_seconds, walk_red_seconds and the 30–600 s bounds.
export const DEFAULT_MAXIMUM_RED_SECONDS = 120
export const MAXIMUM_RED_BOUNDS = { min: 30, max: 600 }

type TimedPlan = Pick<SignalPlan, "phase_order" | "green_seconds" | "yellow_seconds" | "all_red_seconds"> & { phase_greens?: number[] }

/** The engine's name for a phase_order item: an approach, "pedestrian", or a group joined by "+" in plan order. */
export function phaseKey(item: string | string[]) {
  return typeof item === "string" ? item : item.join("+")
}

function cycleParts(plan: TimedPlan) {
  const keys = plan.phase_order.map(phaseKey)
  const greens = keys.map((_, index) => plan.phase_greens?.[index] ?? plan.green_seconds)
  const cycle = keys.reduce((total, key, index) => total + greens[index] + plan.all_red_seconds + (key === "pedestrian" ? 0 : plan.yellow_seconds), 0)
  return { keys, greens, cycle }
}

/** The longest a vehicle phase waits for green under the plan's own fixed-time cycle (cycle minus its green). The walk phase's red is `walkRed`. */
export function fixedTimeRed(plan: TimedPlan) {
  const { keys, greens, cycle } = cycleParts(plan)
  const vehicleGreens = greens.filter((_, index) => keys[index] !== "pedestrian")
  return cycle - (vehicleGreens.length ? Math.min(...vehicleGreens) : plan.green_seconds)
}

/** How long the walk phase waits under the plan's own cycle: cycle minus the walk green. */
export function walkRed(plan: TimedPlan) {
  const { keys, greens, cycle } = cycleParts(plan)
  const walk = keys.indexOf("pedestrian")
  return cycle - (walk >= 0 ? greens[walk] : plan.green_seconds)
}

/** The cap the engine uses when no maximum red is saved: 120 s, or the plan's own red if longer. */
export function automaticMaximumRed(plan: TimedPlan) {
  return Math.max(DEFAULT_MAXIMUM_RED_SECONDS, fixedTimeRed(plan))
}

type PhaseEdit = { phase_order: (string | string[])[]; phase_greens?: number[] }

const members = (item: string | string[]) => (typeof item === "string" ? [item] : item)

/** Merge a vehicle phase with the next one so they share a green; null when either is the walk phase or there is no next phase. */
export function groupWithNext(plan: PhaseEdit, index: number): PhaseEdit | null {
  const [first, second] = [plan.phase_order[index], plan.phase_order[index + 1]]
  if (first === undefined || second === undefined || phaseKey(first) === "pedestrian" || phaseKey(second) === "pedestrian") return null
  const phase_order = [...plan.phase_order.slice(0, index), [...members(first), ...members(second)], ...plan.phase_order.slice(index + 2)]
  return plan.phase_greens ? { phase_order, phase_greens: plan.phase_greens.filter((_, position) => position !== index + 1) } : { phase_order }
}

/** Split a group back into single approaches; each keeps the group's green. Null when the item is not a group. */
export function splitGroup(plan: PhaseEdit, index: number): PhaseEdit | null {
  const item = plan.phase_order[index]
  if (typeof item === "string" || item === undefined) return null
  const phase_order = [...plan.phase_order.slice(0, index), ...item, ...plan.phase_order.slice(index + 1)]
  if (!plan.phase_greens) return { phase_order }
  const green = plan.phase_greens[index]
  return { phase_order, phase_greens: [...plan.phase_greens.slice(0, index), ...item.map(() => green), ...plan.phase_greens.slice(index + 1)] }
}

/** Move a phase earlier (-1) or later (+1), carrying its green with it. */
export function movePhase(plan: PhaseEdit, index: number, direction: -1 | 1): PhaseEdit {
  const swap = <T,>(items: T[]) => {
    const next = [...items]
    ;[next[index], next[index + direction]] = [next[index + direction], next[index]]
    return next
  }
  return plan.phase_greens ? { phase_order: swap(plan.phase_order), phase_greens: swap(plan.phase_greens) } : { phase_order: swap(plan.phase_order) }
}

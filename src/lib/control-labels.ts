export const NO_SIGNAL_LABEL = "No signal (first come, first served)"

const RL_ALGORITHMS = ["ql", "dql", "ppo"]

const algorithmOf = (mode: string) => mode.split(":")[0].toLowerCase()

/** True for a trained-policy mode such as `ql`, `dql:3` or `ppo:12`. */
export function isRlControl(mode: string | null | undefined): boolean {
  return RL_ALGORITHMS.includes(algorithmOf(String(mode ?? "")))
}

/** One name per run control mode, shared by the dashboard, reports and comparisons. */
export function controlLabel(mode: string | null | undefined): string {
  const value = String(mode || "unknown")
  if (value === "no-signal") return NO_SIGNAL_LABEL
  if (value === "fixed-time") return "Fixed-time"
  if (value === "playback") return "Playback"
  if (isRlControl(value)) return `SmartFlow RL (${algorithmOf(value).toUpperCase()})`
  return value.replaceAll("-", " ")
}

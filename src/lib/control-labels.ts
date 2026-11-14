export const NO_SIGNAL_LABEL = "No signal (negotiated, provisional)"

const RL_ALGORITHMS = ["ql", "dql", "ppo"]

const algorithmOf = (mode: string) => mode.split(":")[0].toLowerCase()

/** True for a trained-policy mode such as `ql`, `dql:3` or `ppo:12`. */
export function isRlControl(mode: string | null | undefined): boolean {
  return RL_ALGORITHMS.includes(algorithmOf(String(mode ?? "")))
}

const busyWith = (workload: string) => workload === "training/evaluation" ? "An RL training or evaluation job is running"
  : workload === "live simulation" ? "A live simulation is running"
    : workload === "recording" ? "A recording is being generated" : `SmartFlow is busy with ${workload}`

/** Why a new live run cannot start while another workload holds the server's one compute slot. */
export function blockedStartMessage(workload: string) {
  return `${busyWith(workload)}. The server runs one workload at a time, so a new simulation can start when it finishes or is stopped. Replaying a recording still works.`
}

/** Why training or evaluation cannot start while another workload holds the server's one compute slot. */
export function blockedTrainingMessage(workload: string) {
  return `${busyWith(workload)}. The server runs one workload at a time, so training or evaluation can start when it finishes or is stopped.`
}

/** One name per run control mode, shared by the dashboard, reports and comparisons. */
export function controlLabel(mode: string | null | undefined): string {
  const value = String(mode || "unknown")
  if (value === "no-signal") return NO_SIGNAL_LABEL
  if (value === "fixed-time") return "Traditional signal (fixed-time)"
  if (value === "playback") return "Playback"
  if (isRlControl(value)) return `SmartFlow RL (${algorithmOf(value).toUpperCase()})`
  return value.replaceAll("-", " ")
}

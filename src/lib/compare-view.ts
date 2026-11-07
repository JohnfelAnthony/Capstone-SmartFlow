export type KpiTone = "better" | "worse" | "neutral"

const NEUTRAL_TOLERANCE = 1e-4

/** Difference from the baseline (left) to the compared run (right), and whether that change helps for this metric. */
export function kpiChange(left: number | null, right: number | null, lowerIsBetter: boolean | null): { delta: number | null; tone: KpiTone } {
  if (left === null || right === null) return { delta: null, tone: "neutral" }
  const delta = right - left
  if (lowerIsBetter === null || Math.abs(delta) <= NEUTRAL_TOLERANCE) return { delta, tone: "neutral" }
  return { delta, tone: delta < 0 === lowerIsBetter ? "better" : "worse" }
}

export function frameWindow(time: number, windowSeconds = 60): { start: number; end: number } {
  const start = Math.floor(Math.max(0, time) / windowSeconds) * windowSeconds
  return { start, end: start + windowSeconds }
}

/** Index of the last frame at or before `time`, or -1 when `time` is before the first frame. */
export function frameAtTime(times: number[], time: number): number {
  let low = 0
  let high = times.length - 1
  let found = -1
  while (low <= high) {
    const middle = (low + high) >> 1
    if (times[middle] <= time) { found = middle; low = middle + 1 } else high = middle - 1
  }
  return found
}

export function advancePlayback(time: number, elapsedMs: number, speed: 1 | 2 | 4, duration: number): { time: number; finished: boolean } {
  const next = time + (elapsedMs / 1000) * speed
  return next >= duration ? { time: duration, finished: true } : { time: next, finished: false }
}

export function studyQueue(queues: Record<string, number> | undefined): number {
  return Object.values(queues ?? {}).reduce((total, value) => total + value, 0)
}

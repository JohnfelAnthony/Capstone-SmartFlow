import type { LaneEvent, NativeScenarioConfig, NativeScenarioOptions } from "@/api/native-scenario"

/** One closed lane: closed from `start` seconds (0 = from the start) until `end` seconds (null = to the end of the run). */
export type ClosureRule = { start: number; end: number | null }
export type LaneOption = NativeScenarioOptions["lanes"][number]

/** Closures a scenario already holds as closed_lanes and timed events. `locked` lanes have a pattern this form cannot show (several intervals); they are kept untouched. */
export function readClosures(config: NativeScenarioConfig) {
  const events = [...(config.events ?? [])].map((event, index) => ({ event, index })).sort((a, b) => a.event.time - b.event.time || a.index - b.index).map(item => item.event)
  const lanes = new Set<string>([...(config.closed_lanes ?? []), ...events.filter(event => event.closed !== undefined).map(event => event.lane_id)])
  const rules: Record<string, ClosureRule> = {}
  const locked: string[] = []
  for (const lane of [...lanes].sort()) {
    const own = events.filter(event => event.lane_id === lane && event.closed !== undefined)
    let closed = (config.closed_lanes ?? []).includes(lane)
    const intervals: ClosureRule[] = closed ? [{ start: 0, end: null }] : []
    let clean = !own.some(event => event.speed_factor !== undefined)
    for (const event of own) {
      if (event.closed === closed) clean = false
      else if (event.closed) intervals.push({ start: event.time, end: null })
      else intervals[intervals.length - 1].end = event.time
      closed = Boolean(event.closed)
    }
    if (clean && intervals.length === 1) rules[lane] = intervals[0]
    else locked.push(lane)
  }
  return { rules, locked }
}

/** The settings with their closures replaced by `rules`; speed events and `locked` lanes' own settings stay as they were. */
export function writeClosures(config: NativeScenarioConfig, rules: Record<string, ClosureRule>, locked: string[]): NativeScenarioConfig {
  const keep = new Set(locked)
  const events: LaneEvent[] = (config.events ?? []).filter(event => event.closed === undefined || keep.has(event.lane_id))
  const closedLanes = (config.closed_lanes ?? []).filter(lane => keep.has(lane))
  for (const [lane, rule] of Object.entries(rules)) {
    if (rule.start <= 0) closedLanes.push(lane)
    else events.push({ time: rule.start, lane_id: lane, closed: true })
    if (rule.end !== null) events.push({ time: rule.end, lane_id: lane, closed: false })
  }
  return { ...config, closed_lanes: [...new Set(closedLanes)].sort(), events: events.map((event, index) => ({ event, index })).sort((a, b) => a.event.time - b.event.time || a.index - b.index).map(item => item.event) }
}

export function describeRule(rule: ClosureRule) {
  if (rule.start <= 0) return rule.end === null ? "whole run" : `until ${rule.end} s`
  return rule.end === null ? `from ${rule.start} s` : `${rule.start}–${rule.end} s`
}

export function ruleProblem(rule: ClosureRule) {
  if (!Number.isFinite(rule.start) || rule.start < 0) return "The start time cannot be negative."
  if (rule.end !== null && (!Number.isFinite(rule.end) || rule.end <= rule.start)) return "The end time must be after the start time."
  return null
}

/** "Dalisay Gante Road · north, 0–214 m out · northbound — whole run" for each closed lane, in lane order. */
export function closureLines(config: NativeScenarioConfig, lanes: LaneOption[]) {
  const { rules, locked } = readClosures(config)
  const nameOf = (id: string) => { const lane = lanes.find(item => item.id === id); return lane ? `${lane.road_name} · ${lane.where} · ${lane.direction}` : id }
  return [...Object.entries(rules).map(([lane, rule]) => `${nameOf(lane)} — ${describeRule(rule)}`), ...locked.map(lane => `${nameOf(lane)} — several timed changes`)]
}

/** The first problem with any closure's times, for the form to refuse before saving. */
export function closureProblem(config: NativeScenarioConfig) {
  return Object.values(readClosures(config).rules).map(ruleProblem).find(Boolean) ?? null
}

export type RoadGroup = { roadId: string; title: string; lanes: LaneOption[] }

/** The two directions of each road piece together, named by street and where the piece lies. */
export function groupRoads(lanes: LaneOption[]): RoadGroup[] {
  const groups = new Map<string, RoadGroup>()
  for (const lane of lanes) {
    const roadId = lane.road_id ?? lane.id
    const group = groups.get(roadId) ?? { roadId, title: [lane.road_name, lane.where].filter(Boolean).join(" · "), lanes: [] }
    group.lanes.push(lane)
    groups.set(roadId, group)
  }
  return [...groups.values()].sort((a, b) => a.roadId.localeCompare(b.roadId, undefined, { numeric: true }))
}

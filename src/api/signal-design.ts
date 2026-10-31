import { apiRequest } from "@/api/client"
import type { SignalPlan } from "@/api/native-scenario"

export type SignalDesignResult = {
  cycle_seconds: number
  webster_cycle_seconds: number
  phase_order: (string | string[])[]
  phase_greens: number[]
  flow_ratios: number[]
  total_flow_ratio: number
  lost_time_seconds: number
  warnings: string[]
  assumptions: Record<string, unknown>
}

/** A provisional Webster plan from approach counts (vehicles per hour by class). The result still needs field review. */
export function designSignalPlan(body: {
  network_id?: string
  junction?: string
  phase_order: (string | string[])[]
  approach_counts: Record<string, Record<string, number>>
  base_plan?: Partial<SignalPlan>
}) {
  return apiRequest<{ network_id: string; junction: string; plan: SignalPlan; result: SignalDesignResult }>("/api/signal-design", { method: "POST", body })
}

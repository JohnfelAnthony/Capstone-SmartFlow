import { expect, it } from "vitest"
import { workerSummary } from "@/lib/control-labels"

it("never calls the RL worker Idle while its status is unknown or another workload holds the slot", () => {
  const base = { loaded: true, statusFailed: false, activeJobId: null, blockingWorkload: null }
  expect(workerSummary({ ...base, loaded: false }).value).toBe("—")
  expect(workerSummary({ ...base, statusFailed: true })).toEqual({ value: "Unavailable", detail: "Status could not be loaded" })
  expect(workerSummary({ ...base, blockingWorkload: "live simulation" })).toEqual({ value: "Blocked", detail: "Busy with live simulation" })
  expect(workerSummary({ ...base, activeJobId: 4 })).toEqual({ value: "Active", detail: "Job #4" })
  expect(workerSummary(base)).toEqual({ value: "Idle", detail: "Ready for a job" })
})

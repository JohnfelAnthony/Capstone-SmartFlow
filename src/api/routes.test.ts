import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { SESSION_EXPIRED_EVENT, sessionRestored } from "./client"
import { getRouteContext, previewRoute } from "./routes"

const context = { source: { kind: "network" as const, network_id: "site-a" }, vehicle_type: "car" as const }
const preview = { ...context, expected_network_sha256: "a".repeat(64), entry_id: "west", destination_id: "north" }

beforeEach(() => { vi.stubGlobal("window", new EventTarget()); sessionRestored() })
afterEach(() => vi.unstubAllGlobals())

it("posts both endpoint shapes with session cookies and passes through cancellation", async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response("{}")))
  vi.stubGlobal("fetch", fetch)
  const controller = new AbortController()
  await getRouteContext(context, controller.signal)
  await previewRoute(preview, controller.signal)
  const override = { closed_lanes: [], closure_responses: {} }
  await previewRoute({ ...preview, closure_override: override }, controller.signal)
  expect(fetch).toHaveBeenNthCalledWith(1, expect.stringMatching(/\/api\/routes\/context$/), expect.objectContaining({
    method: "POST", credentials: "include", body: JSON.stringify(context), signal: controller.signal,
  }))
  expect(fetch).toHaveBeenNthCalledWith(2, expect.stringMatching(/\/api\/routes\/preview$/), expect.objectContaining({
    method: "POST", credentials: "include", body: JSON.stringify(preview), signal: controller.signal,
  }))
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ ...preview, closure_override: override })
})

it("uses existing session handling so later requests do not retry a 401 over the network", async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response('{"detail":"Authentication required."}', { status: 401 })))
  vi.stubGlobal("fetch", fetch)
  const expired = vi.fn()
  window.addEventListener(SESSION_EXPIRED_EVENT, expired)
  await expect(previewRoute(preview)).rejects.toMatchObject({ status: 401 })
  await expect(getRouteContext(context)).rejects.toMatchObject({ status: 401 })
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(expired).toHaveBeenCalledTimes(1)
})

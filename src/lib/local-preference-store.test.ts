import { afterEach, describe, expect, it, vi } from "vitest"

class FakeStorage {
  [key: string]: unknown
  setItem(key: string, value: string) { this[key] = value }
  getItem(key: string) { return typeof this[key] === "string" ? this[key] : null }
  removeItem(key: string) { delete this[key] }
}

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.resetModules() })

describe("desktop preference persistence", () => {
  it("loads shared preferences after changing origins and persists changes", async () => {
    vi.stubEnv("VITE_SMARTFLOW_DESKTOP", "1")
    const saved: Record<string, string> = { "smartflow-theme": "light", "smartflow-view-7": "2d" }
    const storage = new FakeStorage()
    storage.setItem("smartflow-theme", "dark")
    vi.stubGlobal("window", { localStorage: storage })
    vi.stubGlobal("fetch", vi.fn(async (_url: string, request?: RequestInit) => {
      if (request?.method === "POST") {
        const body = JSON.parse(String(request.body)) as { key: string; value: string | null }
        if (body.value === null) delete saved[body.key]
        else saved[body.key] = body.value
      }
      return { ok: true, json: async () => ({ ...saved }) }
    }))
    const store = await import("./local-preference-store")
    await store.initializePreferences()
    expect(storage.getItem("smartflow-theme")).toBe("light")
    expect(storage.getItem("smartflow-view-7")).toBe("2d")
    await store.writePreference("smartflow-theme", "dark")
    await store.writePreference("smartflow-view-7", null)
    expect(saved).toEqual({ "smartflow-theme": "dark" })
    const nextOriginStorage = new FakeStorage()
    vi.stubGlobal("window", { localStorage: nextOriginStorage })
    vi.resetModules()
    await (await import("./local-preference-store")).initializePreferences()
    expect(nextOriginStorage.getItem("smartflow-theme")).toBe("dark")
  })

  it("does not overwrite desktop preferences after a failed load", async () => {
    vi.stubEnv("VITE_SMARTFLOW_DESKTOP", "1")
    vi.stubGlobal("window", { localStorage: new FakeStorage() })
    const fetchMock = vi.fn(async () => ({ ok: false }))
    vi.stubGlobal("fetch", fetchMock)
    vi.spyOn(console, "error").mockImplementation(() => {})
    const store = await import("./local-preference-store")
    await store.initializePreferences()
    await expect(store.writePreference("smartflow-theme", "dark")).rejects.toThrow("unavailable")
    expect(fetchMock).toHaveBeenCalledTimes(1)
    vi.restoreAllMocks()
  })
})

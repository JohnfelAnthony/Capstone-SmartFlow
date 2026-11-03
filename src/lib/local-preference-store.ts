const desktop = import.meta.env.VITE_SMARTFLOW_DESKTOP === "1"
const allowed = /^(smartflow-theme|smartflow-random-count|smartflow-random-palette|smartflow-view-[0-9]{1,12})$/
let desktopReady = false
let pending: Promise<void> = Promise.resolve()

export async function initializePreferences() {
  if (!desktop) return
  try {
    const response = await fetch("/api/desktop/preferences", { credentials: "include" })
    if (!response.ok) throw new Error("Unable to load desktop preferences")
    const values: Record<string, string> = await response.json()
    for (const key of Object.keys(window.localStorage)) {
      if (allowed.test(key)) window.localStorage.removeItem(key)
    }
    for (const [key, value] of Object.entries(values)) {
      if (allowed.test(key) && typeof value === "string") window.localStorage.setItem(key, value)
    }
    desktopReady = true
  } catch (error) {
    console.error("Desktop preferences were not loaded; existing preferences will not be overwritten.", error)
  }
}

export function writePreference(key: string, value: string | null): Promise<void> {
  if (!allowed.test(key)) return Promise.reject(new Error("Unsupported preference"))
  if (value === null) window.localStorage.removeItem(key)
  else window.localStorage.setItem(key, value)
  if (!desktop) return Promise.resolve()
  if (!desktopReady) return Promise.reject(new Error("Desktop preferences are unavailable"))
  const update = async () => {
    const response = await fetch("/api/desktop/preferences", {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value }),
    })
    if (!response.ok) throw new Error("Unable to save desktop preferences")
  }
  const result = pending.then(update)
  pending = result.catch(() => {})
  return result
}

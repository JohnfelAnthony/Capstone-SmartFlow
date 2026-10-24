export type ThemeMode = "dark" | "light"

// Kept to clear palettes saved by the removed Randomize button.
const RANDOM_THEME_VARIABLES = [
  "--background",
  "--foreground",
  "--card",
  "--card-foreground",
  "--popover",
  "--popover-foreground",
  "--primary",
  "--primary-foreground",
  "--secondary",
  "--secondary-foreground",
  "--muted",
  "--muted-foreground",
  "--accent",
  "--accent-foreground",
  "--border",
  "--input",
  "--ring",
  "--chart-1",
  "--chart-2",
  "--chart-3",
  "--chart-4",
  "--chart-5",
  "--sidebar",
  "--sidebar-foreground",
  "--sidebar-primary",
  "--sidebar-primary-foreground",
  "--sidebar-accent",
  "--sidebar-accent-foreground",
  "--sidebar-border",
  "--sidebar-ring",
  "--random-dashboard",
  "--random-dashboard-card",
  "--random-dashboard-input",
  "--random-dashboard-hover",
  "--random-dashboard-muted",
  "--random-dashboard-secondary",
  "--random-dashboard-primary",
  "--random-sim-viewport",
  "--random-sim-grid",
]

export function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "dark"
  }

  const savedTheme = window.localStorage.getItem("smartflow-theme")
  if (savedTheme === "light" || savedTheme === "dark") {
    return savedTheme
  }

  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"
}

export function applyTheme(theme: ThemeMode) {
  const root = document.documentElement

  root.classList.toggle("light", theme === "light")
  root.classList.toggle("dark", theme === "dark")
  root.style.colorScheme = theme
}

export function clearRandomPalette() {
  const root = document.documentElement

  root.classList.remove("random-theme")
  for (const variableName of RANDOM_THEME_VARIABLES) {
    root.style.removeProperty(variableName)
  }

  window.localStorage.removeItem("smartflow-random-palette")
}

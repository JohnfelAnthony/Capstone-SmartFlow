export type ThemeMode = "dark" | "light"
export type RandomPalette = {
  background: string
  foreground: string
  card: string
  cardForeground: string
  popover: string
  primary: string
  primaryForeground: string
  secondary: string
  muted: string
  mutedForeground: string
  accent: string
  border: string
  input: string
  sidebar: string
  sidebarForeground: string
  dashboard: string
  dashboardCard: string
  dashboardInput: string
  dashboardHover: string
  dashboardMuted: string
  dashboardSecondary: string
  dashboardPrimary: string
  simViewport: string
  simGrid: string
}

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

const VIVID_PRIMARY_COLORS = [
  "#ff0000",
  "#0000ff",
  "#ff7a00",
  "#00ff00",
  "#ffff00",
  "#00ffff",
  "#ff00ff",
  "#8a2be2",
  "#ff1493",
  "#00e676",
  "#2979ff",
  "#ff1744",
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

export function generateRandomPalette(): RandomPalette {
  const randomFrom = <T,>(items: T[]) => items[Math.floor(Math.random() * items.length)]
  const color = () =>
    `hsl(${Math.floor(Math.random() * 360)} ${45 + Math.floor(Math.random() * 56)}% ${8 + Math.floor(Math.random() * 82)}%)`
  const vividColor = () => randomFrom(VIVID_PRIMARY_COLORS)
  const translucent = () =>
    `hsl(${Math.floor(Math.random() * 360)} ${45 + Math.floor(Math.random() * 56)}% ${20 + Math.floor(Math.random() * 70)}% / ${0.18 + Math.random() * 0.62})`

  return {
    background: color(),
    foreground: color(),
    card: color(),
    cardForeground: color(),
    popover: color(),
    primary: vividColor(),
    primaryForeground: color(),
    secondary: vividColor(),
    muted: color(),
    mutedForeground: color(),
    accent: vividColor(),
    border: translucent(),
    input: translucent(),
    sidebar: color(),
    sidebarForeground: color(),
    dashboard: color(),
    dashboardCard: color(),
    dashboardInput: color(),
    dashboardHover: color(),
    dashboardMuted: color(),
    dashboardSecondary: vividColor(),
    dashboardPrimary: vividColor(),
    simViewport: color(),
    simGrid: translucent(),
  }
}

export function applyRandomPalette(palette: RandomPalette) {
  const root = document.documentElement
  const variableMap: Record<string, string> = {
    "--background": palette.background,
    "--foreground": palette.foreground,
    "--card": palette.card,
    "--card-foreground": palette.cardForeground,
    "--popover": palette.popover,
    "--popover-foreground": palette.cardForeground,
    "--primary": palette.primary,
    "--primary-foreground": palette.primaryForeground,
    "--secondary": palette.secondary,
    "--secondary-foreground": palette.foreground,
    "--muted": palette.muted,
    "--muted-foreground": palette.mutedForeground,
    "--accent": palette.accent,
    "--accent-foreground": palette.foreground,
    "--border": palette.border,
    "--input": palette.input,
    "--ring": palette.primary,
    "--chart-1": palette.primary,
    "--chart-2": palette.dashboardSecondary,
    "--chart-3": palette.accent,
    "--chart-4": palette.dashboardMuted,
    "--chart-5": palette.simGrid,
    "--sidebar": palette.sidebar,
    "--sidebar-foreground": palette.sidebarForeground,
    "--sidebar-primary": palette.primary,
    "--sidebar-primary-foreground": palette.primaryForeground,
    "--sidebar-accent": palette.secondary,
    "--sidebar-accent-foreground": palette.foreground,
    "--sidebar-border": palette.border,
    "--sidebar-ring": palette.primary,
    "--random-dashboard": palette.dashboard,
    "--random-dashboard-card": palette.dashboardCard,
    "--random-dashboard-input": palette.dashboardInput,
    "--random-dashboard-hover": palette.dashboardHover,
    "--random-dashboard-muted": palette.dashboardMuted,
    "--random-dashboard-secondary": palette.dashboardSecondary,
    "--random-dashboard-primary": palette.dashboardPrimary,
    "--random-sim-viewport": palette.simViewport,
    "--random-sim-grid": palette.simGrid,
  }

  for (const [name, value] of Object.entries(variableMap)) {
    root.style.setProperty(name, value)
  }

  root.classList.add("random-theme")
}


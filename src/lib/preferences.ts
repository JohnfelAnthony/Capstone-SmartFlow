import type { VisualizationMode } from "@/simulation/visualization-mode"

export function defaultVisualization(userId: number): VisualizationMode {
  try {
    return window.localStorage.getItem(`smartflow-view-${userId}`) === "2d" ? "2d" : "3d"
  } catch {
    return "3d"
  }
}

export function saveDefaultVisualization(userId: number, mode: VisualizationMode) {
  window.localStorage.setItem(`smartflow-view-${userId}`, mode)
}

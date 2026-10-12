import type { SceneBounds } from "./scene-geometry"

/** Fit the supplied ground rectangle directly, without a larger enclosing sphere. */
export function perspectiveBoundsFit(bounds: SceneBounds, verticalFovDegrees: number, aspect: number, pitchDegrees = 58, azimuthDegrees = 0) {
  const pitch = pitchDegrees * Math.PI / 180, azimuth = azimuthDegrees * Math.PI / 180
  const verticalTangent = Math.tan(verticalFovDegrees * Math.PI / 360)
  const horizontalTangent = verticalTangent * Math.max(0.1, aspect)
  const halfWidth = Math.max(1, bounds.max_x - bounds.min_x) / 2
  const halfDepth = Math.max(1, bounds.max_y - bounds.min_y) / 2
  const sine = Math.sin(azimuth), cosine = Math.cos(azimuth)
  let distance = 8
  for (const x of [-halfWidth, halfWidth]) for (const z of [-halfDepth, halfDepth]) {
    const lateral = cosine * x - sine * z
    const longitudinal = sine * x + cosine * z
    const height = -Math.sin(pitch) * longitudinal
    const towardCamera = Math.cos(pitch) * longitudinal
    distance = Math.max(distance, Math.abs(lateral) / horizontalTangent + towardCamera, Math.abs(height) / verticalTangent + towardCamera)
  }
  return {
    distance,
    offset: {
      x: Math.sin(azimuth) * Math.cos(pitch) * distance,
      y: Math.sin(pitch) * distance,
      z: Math.cos(azimuth) * Math.cos(pitch) * distance,
    },
  }
}

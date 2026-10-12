import { describe, expect, it } from "vitest"
import { PerspectiveCamera, Vector3 } from "three"
import { perspectiveBoundsFit } from "../camera-fit"
import { boundsForJunction, normalizeSceneGeometry } from "../scene-geometry"
import { bentNetwork } from "./geometry-fixture"

describe("junction rectangle camera framing", () => {
  it.each([0.65, 1.25, 1.8])("fits every supplied ground corner at aspect %s without extra sphere padding", (aspect) => {
    const bounds = boundsForJunction(normalizeSceneGeometry(bentNetwork), "J1")
    const centerX = (bounds.min_x + bounds.max_x) / 2, centerZ = -(bounds.min_y + bounds.max_y) / 2
    const fit = perspectiveBoundsFit(bounds, 44, aspect)
    const camera = new PerspectiveCamera(44, aspect, 0.1, 10000)
    camera.position.set(centerX + fit.offset.x, fit.offset.y, centerZ + fit.offset.z)
    camera.lookAt(centerX, 0, centerZ)
    camera.updateMatrixWorld(true)
    let largestProjectedExtent = 0
    for (const x of [bounds.min_x, bounds.max_x]) for (const y of [bounds.min_y, bounds.max_y]) {
      const projected = new Vector3(x, 0, -y).project(camera)
      expect(Math.abs(projected.x)).toBeLessThanOrEqual(1 + 1e-10)
      expect(Math.abs(projected.y)).toBeLessThanOrEqual(1 + 1e-10)
      largestProjectedExtent = Math.max(largestProjectedExtent, Math.abs(projected.x), Math.abs(projected.y))
    }
    expect(largestProjectedExtent).toBeCloseTo(1, 6)
  })

  it("brings a balanced immediate-approach rectangle closer than the former diagonal sphere", () => {
    const bounds = { min_x: -48, max_x: 48, min_y: -48, max_y: 48 }
    const fit = perspectiveBoundsFit(bounds, 44, 1.25)
    const oldDistance = Math.hypot(96, 96) / 2 / Math.sin(44 * Math.PI / 360)
    expect(fit.distance).toBeLessThan(oldDistance * 0.75)
    expect(bounds).toEqual({ min_x: -48, max_x: 48, min_y: -48, max_y: 48 })
  })
})

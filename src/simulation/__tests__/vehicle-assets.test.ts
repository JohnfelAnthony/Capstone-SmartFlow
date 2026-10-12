import { afterEach, describe, expect, it, vi } from "vitest"
import { InstancedMesh, Matrix4, Vector3 } from "three"
import type { RenderVehicle } from "../frame-types"
import { getFallbackVehicleAssetLibrary, loadVehicleAssetLibrary, VEHICLE_ASSET_REGISTRY, VEHICLE_CLASSES, VEHICLE_PROFILES, vehicleClass, vehicleHeadingRadians, VehicleFleetInstances, type VehicleAssetLibrary } from "../vehicle-assets"

const libraries: VehicleAssetLibrary[] = []
afterEach(() => { libraries.forEach((library) => library.dispose()); libraries.length = 0; vi.unstubAllGlobals() })
const assets = () => { const library = getFallbackVehicleAssetLibrary(); libraries.push(library); return library }
const vehicle = (id: string, type = "car", angle = 90): RenderVehicle => ({
  id, visual_type: type, emergency: type === "emergency", x: 12, y: 34, angle,
  speed: 0, lane_id: "lane", lane_position: 12, length: VEHICLE_PROFILES[vehicleClass(type)].length,
  width: VEHICLE_PROFILES[vehicleClass(type)].width, stopped: true,
})

describe("canonical six-class vehicle assets", () => {
  it("maps all engine classes explicitly, with authored classes where the inspected kit has none", () => {
    expect(VEHICLE_CLASSES).toEqual(["car", "motorcycle", "tricycle", "bus", "truck", "emergency"])
    expect(vehicleClass("emergency")).toBe("emergency")
    expect(vehicleClass("car", true)).toBe("emergency")
    expect(vehicleClass("unknown")).toBe("car")
    expect(VEHICLE_ASSET_REGISTRY.car.url).toContain("sedan.glb")
    expect(VEHICLE_ASSET_REGISTRY.tricycle.url).toBeNull()
    expect(VEHICLE_ASSET_REGISTRY.motorcycle.url).toBeNull()
    expect(VEHICLE_ASSET_REGISTRY.bus.url).toBeNull()
  })

  it.each(VEHICLE_CLASSES)("centers and grounds %s to an exact unit footprint before engine scaling", (type) => {
    const template = assets().template(type)
    expect(template.bounds.min.x).toBeCloseTo(-0.5, 6)
    expect(template.bounds.max.x).toBeCloseTo(0.5, 6)
    expect(template.bounds.min.z).toBeCloseTo(-0.5, 6)
    expect(template.bounds.max.z).toBeCloseTo(0.5, 6)
    expect(template.bounds.min.y).toBeCloseTo(0, 6)
    expect(template.bounds.max.y).toBeCloseTo(VEHICLE_PROFILES[type].height, 6)
  })

  it.each([[0, 0, -1], [90, 1, 0], [180, 0, 1], [270, -1, 0]])("points forward correctly at native heading %s", (angle, x, z) => {
    const direction = new Vector3(1, 0, 0).applyMatrix4(new Matrix4().makeRotationY(vehicleHeadingRadians(angle)))
    expect(direction.x).toBeCloseTo(x)
    expect(direction.z).toBeCloseTo(z)
  })

  it("uses authoritative position/dimensions and preserves entity IDs in instanced picking", () => {
    const library = assets(), fleet = new VehicleFleetInstances(library)
    const tricycle = { ...vehicle("green-passenger", "tricycle", 0), length: 3.2, width: 1.45 }
    fleet.update([tricycle])
    const batch = fleet.group.children.find((mesh) => mesh.name === "fleet-tricycle")!
    const matrix = new Matrix4()
    ;(batch as InstancedMesh).getMatrixAt(0, matrix)
    const center = new Vector3(0, 0, 0).applyMatrix4(matrix)
    expect(center.x).toBeCloseTo(12)
    expect(center.z).toBeCloseTo(-34)
    expect(fleet.vehicleIdForHit(batch, 0)).toBe("green-passenger")
    expect(fleet.vehicleIdForHit(batch, 1)).toBeNull()
    const front = new Vector3(0.5, 0, 0).applyMatrix4(matrix)
    expect(front.z).toBeCloseTo(-34 - 1.6)
    const side = new Vector3(0, 0, 0.5).applyMatrix4(matrix)
    expect(Math.abs(side.x - center.x)).toBeCloseTo(1.45 / 2)
    fleet.update([])
    expect(fleet.vehicleIdForHit(batch, 0)).toBeNull()
    fleet.dispose()
  })

  it("displays the entire 300-vehicle mixed fleet with draw calls per shared material", () => {
    const fleet = new VehicleFleetInstances(assets(), 300)
    fleet.update(Array.from({ length: 300 }, (_, index) => vehicle(String(index), VEHICLE_CLASSES[index % 6])))
    expect(fleet.displayedCount).toBe(300)
    expect(fleet.omittedCount).toBe(0)
    for (const type of VEHICLE_CLASSES) expect(fleet.batchCounts[type].entities).toBe(50)
    expect(fleet.drawCallCount).toBeLessThan(40)
    fleet.dispose()
  })

  it("disposes instance resources separately and shared GPU resources exactly once", () => {
    const library = assets(), template = library.template("tricycle"), fleet = new VehicleFleetInstances(library)
    const geometryDispose = vi.spyOn(template.parts[0].geometry, "dispose")
    const materialDispose = vi.spyOn(template.parts[0].material, "dispose")
    fleet.dispose()
    fleet.dispose()
    expect(geometryDispose).not.toHaveBeenCalled()
    expect(materialDispose).not.toHaveBeenCalled()
    library.dispose()
    library.dispose()
    expect(geometryDispose).toHaveBeenCalledTimes(1)
    expect(materialDispose).toHaveBeenCalledTimes(1)
    const replacement = assets()
    expect(replacement.template("tricycle").parts.length).toBeGreaterThan(1)
  })

  it("keeps distinct classes usable on failed asset requests without repeated downloads across libraries", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 })
    vi.stubGlobal("fetch", fetch)
    const notice = vi.fn()
    const first = await loadVehicleAssetLibrary(notice)
    const second = await loadVehicleAssetLibrary()
    libraries.push(first, second)
    expect(fetch).toHaveBeenCalledTimes(5)
    expect(notice).toHaveBeenCalledTimes(5)
    expect(first.issues.every((issue) => issue.message.includes("distinct procedural appearance"))).toBe(true)
    for (const type of VEHICLE_CLASSES) expect(first.template(type).parts.length).toBeGreaterThan(0)
    expect(first.template("tricycle").source).toBe("authored")
    expect(first.template("emergency").source).toBe("procedural-fallback")
  })
})

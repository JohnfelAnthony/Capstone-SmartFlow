import {
  Box3,
  BoxGeometry,
  CylinderGeometry,
  DynamicDrawUsage,
  Group,
  InstancedMesh,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  Object3D,
  SphereGeometry,
  Vector3,
  type BufferGeometry,
  type Material,
  type Texture,
} from "three"
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js"
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js"
import type { RenderVehicle } from "./frame-types"
import { headingToThreeYaw, normalizeVehicleClass, vehicleDimensions } from "./scene-geometry"

export const VEHICLE_CLASSES = ["car", "motorcycle", "tricycle", "bus", "truck"] as const
export type VehicleClass = typeof VEHICLE_CLASSES[number]
export type RoadPropType = "barrier" | "cone"

export const VEHICLE_PROFILES: Record<VehicleClass, { length: number; width: number; height: number; label: string }> = {
  car: { length: 4.5, width: 1.8, height: 1.5, label: "Car" },
  motorcycle: { length: 2, width: 0.8, height: 1.4, label: "Motorcycle" },
  tricycle: { length: 3, width: 1.4, height: 1.8, label: "Tagum tricycle" },
  bus: { length: 10, width: 2.5, height: 3.1, label: "Bus" },
  truck: { length: 8, width: 2.5, height: 2.8, label: "Truck" },
}

export const VEHICLE_ASSET_REGISTRY: Record<VehicleClass, { url: string | null; sourceForward: "+X" | "+Z" }> = {
  car: { url: "/assets/simulation/kenney-car-kit/sedan.glb", sourceForward: "+Z" },
  motorcycle: { url: null, sourceForward: "+X" },
  tricycle: { url: null, sourceForward: "+X" },
  bus: { url: null, sourceForward: "+X" },
  truck: { url: "/assets/simulation/kenney-car-kit/truck.glb", sourceForward: "+Z" },
}

const PROP_REGISTRY: Record<RoadPropType, string> = {
  barrier: "/assets/simulation/kenney-city-kit-roads/construction-barrier.glb",
  cone: "/assets/simulation/kenney-city-kit-roads/construction-cone.glb",
}

export type VehicleAssetIssue = { asset: VehicleClass | RoadPropType; message: string }
export type VehicleAssetPart = { geometry: BufferGeometry; material: Material }
export type VehicleTemplate = {
  parts: VehicleAssetPart[]
  bounds: Box3
  height: number
  source: "bundled-glb" | "authored" | "procedural-fallback"
}

const colors = {
  car: 0xc88269,
  bus: 0xe2c787,
  truck: 0x7d97aa,
  green: 0x69b83f,
  glass: 0x25323e,
  tire: 0x22272b,
  metal: 0x7b848b,
  trim: 0xf3f2e9,
  red: 0xce534d,
  blue: 0x467cab,
}

export function vehicleClass(type: string | undefined): VehicleClass {
  return normalizeVehicleClass(type)
}

/** Native angles: north=0, east=90. +X meshes rotate toward world -Z for north. */
export function vehicleHeadingRadians(angle: number) {
  return headingToThreeYaw(angle)
}

function material(color: number) {
  return new MeshStandardMaterial({ color, roughness: 0.78, metalness: 0.02 })
}

function addBox(group: Group, surface: Material, x: number, y: number, z: number, length: number, height: number, width: number) {
  const mesh = new Mesh(new BoxGeometry(length, height, width), surface)
  mesh.position.set(x, y, z)
  group.add(mesh)
  return mesh
}

function addWheel(group: Group, surface: Material, x: number, z: number, radius: number, width: number) {
  const wheel = new Mesh(new CylinderGeometry(radius, radius, width, 10), surface)
  wheel.rotation.x = Math.PI / 2
  wheel.position.set(x, radius, z)
  wheel.name = "wheel"
  group.add(wheel)
}

function proceduralVehicle(type: VehicleClass) {
  const group = new Group()
  group.name = `smartflow-${type}`
  const tires = material(colors.tire)
  const glass = material(colors.glass)
  const trim = material(colors.trim)
  const metal = material(colors.metal)
  const body = material(type === "tricycle" ? colors.green : type === "bus" ? colors.bus : type === "truck" ? colors.truck : colors.car)

  if (type === "tricycle") {
    // One centered front wheel, two rear wheels; a passenger cabin rather than a recolored car.
    addWheel(group, tires, 1.08, 0, 0.25, 0.2)
    addWheel(group, tires, -0.91, -0.57, 0.25, 0.2)
    addWheel(group, tires, -0.91, 0.57, 0.25, 0.2)
    addBox(group, body, -0.35, 0.63, 0, 1.75, 0.67, 1.27)
    addBox(group, body, 0.68, 0.61, 0, 0.58, 0.3, 0.52)
    addBox(group, tires, 0.48, 0.92, 0, 0.44, 0.12, 0.5)
    addBox(group, metal, 1.02, 0.56, 0, 0.08, 0.59, 0.16).rotation.z = -0.15
    addBox(group, metal, 0.8, 1.03, 0, 0.1, 0.08, 0.67)
    addBox(group, glass, -0.18, 1.2, -0.62, 1.15, 0.45, 0.025)
    addBox(group, glass, -0.18, 1.2, 0.62, 1.15, 0.45, 0.025)
    addBox(group, glass, 0.48, 1.21, 0, 0.04, 0.47, 1.04)
    addBox(group, body, -0.39, 1.63, 0, 1.88, 0.16, 1.36).name = "covered-passenger-roof"
    for (const x of [-1.12, 0.4]) for (const z of [-0.57, 0.57]) {
      addBox(group, trim, x, 1.28, z, 0.06, 0.68, 0.06)
    }
    addBox(group, trim, -0.39, 0.48, 0, 1.9, 0.09, 1.34)
    addBox(group, trim, 1.11, 0.91, 0, 0.08, 0.16, 0.26)
    return group
  }

  if (type === "motorcycle") {
    addWheel(group, tires, -0.66, 0, 0.29, 0.17)
    addWheel(group, tires, 0.74, 0, 0.29, 0.17)
    addBox(group, body, 0.06, 0.61, 0, 0.85, 0.24, 0.34)
    addBox(group, tires, -0.27, 0.81, 0, 0.62, 0.13, 0.34)
    addBox(group, metal, 0.65, 0.66, 0, 0.07, 0.65, 0.08).rotation.z = -0.22
    addBox(group, metal, 0.56, 1, 0, 0.09, 0.07, 0.64)
    addBox(group, metal, -0.05, 0.41, 0, 1.07, 0.09, 0.22)
    addBox(group, glass, -0.15, 1.11, 0, 0.25, 0.4, 0.32).rotation.z = -0.17
    const helmet = new Mesh(new SphereGeometry(0.16, 8, 6), trim)
    helmet.position.set(-0.08, 1.43, 0)
    group.add(helmet)
    return group
  }

  const profile = VEHICLE_PROFILES[type]
  const length = profile.length
  const width = profile.width
  const isBus = type === "bus"
  const isTruck = type === "truck"
  const radius = isBus || isTruck ? 0.43 : 0.32
  const bodyHeight = isBus ? 1.95 : isTruck ? 1.6 : 0.65
  addBox(group, body, 0, radius + bodyHeight / 2, 0, length * 0.94, bodyHeight, width * 0.9)
  if (isBus) {
    addBox(group, trim, 0, 2.44, 0, length * 0.95, 0.14, width * 0.92)
    for (let x = -length * 0.35; x < length * 0.4; x += 1.1) for (const z of [-width * 0.457, width * 0.457]) {
      addBox(group, glass, x, 1.94, z, 0.85, 0.68, 0.035)
    }
    addBox(group, glass, length * 0.472, 1.76, 0, 0.05, 1.05, width * 0.72)
  } else if (isTruck) {
    addBox(group, trim, -length * 0.12, 1.59, 0, length * 0.65, 1.6, width * 0.93)
    addBox(group, body, length * 0.33, 1.45, 0, length * 0.25, 1.8, width * 0.9)
    addBox(group, glass, length * 0.457, 1.77, 0, 0.035, 0.72, width * 0.7)
  } else {
    addBox(group, glass, -length * 0.03, 1.3, 0, length * 0.49, 0.63, width * 0.72)
    addBox(group, body, -length * 0.035, 1.64, 0, length * 0.51, 0.13, width * 0.79)
  }
  for (const x of [-length * 0.32, length * 0.32]) for (const z of [-width * 0.43, width * 0.43]) {
    addWheel(group, tires, x, z, radius, width * 0.14)
  }
  addBox(group, trim, length * 0.475, radius + 0.4, 0, 0.03, 0.14, width * 0.63)
  return group
}

function proceduralProp(type: RoadPropType) {
  const group = new Group()
  const orange = material(0xe59742)
  const trim = material(colors.trim)
  if (type === "cone") {
    const cone = new Mesh(new CylinderGeometry(0.03, 0.23, 0.7, 8), orange)
    cone.position.y = 0.41
    group.add(cone)
    addBox(group, trim, 0, 0.05, 0, 0.55, 0.1, 0.55)
  } else {
    addBox(group, trim, 0, 0.66, 0, 2.3, 0.32, 0.15)
    for (const x of [-0.9, 0.9]) {
      addBox(group, orange, x, 0.35, 0, 0.12, 0.7, 0.15)
      addBox(group, orange, x, 0.04, 0, 0.42, 0.08, 0.55)
    }
    for (const x of [-0.8, 0, 0.8]) addBox(group, orange, x, 0.66, 0.078, 0.4, 0.28, 0.015)
  }
  return group
}

/** Bake normalization once, then merge every repeated part sharing a material. */
function normalizedTemplate(group: Object3D, height: number, source: VehicleTemplate["source"], rotateSource = false): VehicleTemplate {
  group.updateMatrixWorld(true)
  const orientation = new Matrix4().makeRotationY(rotateSource ? Math.PI / 2 : 0)
  const sourceBounds = new Box3()
  const grouped = new Map<Material, BufferGeometry[]>()
  const sourceGeometries = new Set<BufferGeometry>()
  group.traverse((object) => {
    if (!(object instanceof Mesh)) return
    sourceGeometries.add(object.geometry)
    if (Array.isArray(object.material)) throw new Error("Expected a single material per curated mesh")
    const geometry = object.geometry.clone().applyMatrix4(new Matrix4().multiplyMatrices(orientation, object.matrixWorld))
    geometry.computeBoundingBox()
    sourceBounds.union(geometry.boundingBox!)
    const values = grouped.get(object.material) ?? []
    values.push(geometry)
    grouped.set(object.material, values)
  })
  const size = sourceBounds.getSize(new Vector3())
  if (size.x <= 0 || size.y <= 0 || size.z <= 0) throw new Error("Asset has an empty footprint")
  const center = sourceBounds.getCenter(new Vector3())
  const normalize = new Matrix4().makeScale(1 / size.x, height / size.y, 1 / size.z)
    .multiply(new Matrix4().makeTranslation(-center.x, -sourceBounds.min.y, -center.z))
  const parts: VehicleAssetPart[] = []
  const bounds = new Box3()
  for (const [surface, geometries] of grouped) {
    const geometry = geometries.length === 1 ? geometries[0] : mergeGeometries(geometries, false)
    if (!geometry) throw new Error("Could not batch asset geometry")
    if (geometries.length > 1) geometries.forEach((value) => value.dispose())
    geometry.applyMatrix4(normalize)
    geometry.computeBoundingBox()
    geometry.computeBoundingSphere()
    bounds.union(geometry.boundingBox!)
    parts.push({ geometry, material: surface })
    if (surface instanceof MeshStandardMaterial) {
      surface.transparent = false
      surface.opacity = 1
      surface.roughness = 0.78
      surface.metalness = 0.02
    }
  }
  sourceGeometries.forEach((geometry) => geometry.dispose())
  return { parts, bounds, height, source }
}

function materialTextures(surface: Material): Texture[] {
  if (!(surface instanceof MeshStandardMaterial)) return []
  return [surface.map, surface.normalMap, surface.roughnessMap, surface.metalnessMap, surface.emissiveMap, surface.aoMap, surface.alphaMap].filter((value): value is Texture => value !== null)
}

export class VehicleAssetLibrary {
  private readonly templates = new Map<VehicleClass, VehicleTemplate>()
  private readonly props = new Map<RoadPropType, VehicleTemplate>()
  private readonly geometries = new Set<BufferGeometry>()
  private readonly materials = new Set<Material>()
  private readonly textures = new Set<Texture>()
  private disposed = false
  readonly issues: VehicleAssetIssue[] = []

  constructor() {
    for (const type of VEHICLE_CLASSES) {
      this.replaceVehicle(type, normalizedTemplate(proceduralVehicle(type), VEHICLE_PROFILES[type].height, VEHICLE_ASSET_REGISTRY[type].url ? "procedural-fallback" : "authored"))
    }
    for (const type of ["barrier", "cone"] as const) this.replaceProp(type, normalizedTemplate(proceduralProp(type), type === "barrier" ? 1.1 : 0.75, "procedural-fallback"))
  }

  template(type: VehicleClass) {
    if (this.disposed) throw new Error("Vehicle assets have been disposed")
    return this.templates.get(type)!
  }

  private track(template: VehicleTemplate) {
    for (const part of template.parts) {
      this.geometries.add(part.geometry)
      this.materials.add(part.material)
      materialTextures(part.material).forEach((texture) => this.textures.add(texture))
    }
  }

  replaceVehicle(type: VehicleClass, template: VehicleTemplate) {
    this.track(template)
    this.templates.set(type, template)
  }

  replaceProp(type: RoadPropType, template: VehicleTemplate) {
    this.track(template)
    this.props.set(type, template)
  }

  /** Static groups borrow library resources. Do not dispose their geometries separately. */
  createRoadProp(type: RoadPropType, length = type === "barrier" ? 2.4 : 0.55, width = type === "barrier" ? 0.6 : 0.55) {
    if (this.disposed) throw new Error("Vehicle assets have been disposed")
    const group = new Group()
    group.name = `road-prop-${type}`
    for (const part of this.props.get(type)!.parts) group.add(new Mesh(part.geometry, part.material))
    group.scale.set(length, 1, width)
    return group
  }

  dispose() {
    if (this.disposed) return
    this.disposed = true
    this.geometries.forEach((geometry) => geometry.dispose())
    this.materials.forEach((surface) => surface.dispose())
    this.textures.forEach((texture) => {
      const image = texture.image
      texture.dispose()
      if (typeof ImageBitmap !== "undefined" && image instanceof ImageBitmap) image.close()
    })
    this.templates.clear()
    this.props.clear()
    this.geometries.clear()
    this.materials.clear()
    this.textures.clear()
  }
}

/** Binary-only cache survives view switches; each library owns separate disposable GPU objects. */
const assetBytes = new Map<string, Promise<ArrayBuffer>>()

function loadBytes(url: string) {
  let bytes = assetBytes.get(url)
  if (!bytes) {
    bytes = fetch(url, { signal: AbortSignal.timeout(15000) }).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return response.arrayBuffer()
    })
    assetBytes.set(url, bytes)
  }
  return bytes
}

export function getFallbackVehicleAssetLibrary() {
  return new VehicleAssetLibrary()
}

export async function loadVehicleAssetLibrary(onIssue?: (issue: VehicleAssetIssue) => void) {
  const library = getFallbackVehicleAssetLibrary()
  const loader = new GLTFLoader()
  const jobs: Array<{ asset: VehicleClass | RoadPropType; url: string; height: number; vehicle: boolean }> = []
  for (const type of VEHICLE_CLASSES) {
    const url = VEHICLE_ASSET_REGISTRY[type].url
    if (url) jobs.push({ asset: type, url, height: VEHICLE_PROFILES[type].height, vehicle: true })
  }
  for (const type of ["barrier", "cone"] as const) jobs.push({ asset: type, url: PROP_REGISTRY[type], height: type === "barrier" ? 1.1 : 0.75, vehicle: false })
  await Promise.all(jobs.map(async ({ asset, url, height, vehicle }) => {
    try {
      const gltf = await loader.parseAsync(await loadBytes(url), "")
      const template = normalizedTemplate(gltf.scene, height, "bundled-glb", vehicle)
      if (vehicle) library.replaceVehicle(asset as VehicleClass, template)
      else library.replaceProp(asset as RoadPropType, template)
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown load error"
      const issue = { asset, message: `${vehicle ? VEHICLE_PROFILES[asset as VehicleClass].label : asset} asset unavailable; using its distinct procedural appearance. ${detail}` }
      library.issues.push(issue)
      onIssue?.(issue)
    }
  }))
  return library
}

type FleetBatch = { meshes: InstancedMesh[]; ids: string[]; count: number }

/** One instanced draw per class/material. Updates transform buffers, never entity React state. */
export class VehicleFleetInstances {
  readonly group = new Group()
  readonly capacity: number
  private readonly batches = new Map<VehicleClass, FleetBatch>()
  private readonly matrix = new Matrix4()
  private readonly transform = new Object3D()
  private readonly meshClasses = new Map<Object3D, VehicleClass>()
  private disposed = false
  displayedCount = 0
  omittedCount = 0

  constructor(library: VehicleAssetLibrary, capacity = 300, shadows = false) {
    this.capacity = Math.max(1, Math.floor(capacity))
    this.group.name = "instanced-native-fleet"
    for (const type of VEHICLE_CLASSES) {
      const batch: FleetBatch = { meshes: [], ids: [], count: 0 }
      for (const part of library.template(type).parts) {
        const mesh = new InstancedMesh(part.geometry, part.material, this.capacity)
        mesh.name = `fleet-${type}`
        mesh.count = 0
        mesh.castShadow = shadows
        mesh.instanceMatrix.setUsage(DynamicDrawUsage)
        // Bounds span a moving network; stale aggregate bounds must not hide or prevent picking.
        mesh.frustumCulled = false
        this.group.add(mesh)
        this.meshClasses.set(mesh, type)
        batch.meshes.push(mesh)
      }
      this.batches.set(type, batch)
    }
  }

  update(vehicles: readonly RenderVehicle[]) {
    if (this.disposed) return
    this.displayedCount = 0
    this.omittedCount = 0
    for (const batch of this.batches.values()) {
      batch.count = 0
      batch.ids.length = 0
    }
    for (const vehicle of vehicles) {
      const type = vehicleClass(vehicle.visual_type)
      const batch = this.batches.get(type)!
      if (this.displayedCount >= this.capacity) {
        this.omittedCount += 1
        continue
      }
      const dimensions = vehicleDimensions(vehicle)
      this.transform.position.set(vehicle.x, 0.04, -vehicle.y)
      this.transform.rotation.set(0, vehicleHeadingRadians(vehicle.angle), 0)
      this.transform.scale.set(dimensions.length, 1, dimensions.width)
      this.transform.updateMatrix()
      this.matrix.copy(this.transform.matrix)
      batch.ids.push(vehicle.id)
      for (const mesh of batch.meshes) mesh.setMatrixAt(batch.count, this.matrix)
      batch.count += 1
      this.displayedCount += 1
    }
    for (const batch of this.batches.values()) for (const mesh of batch.meshes) {
      mesh.count = batch.count
      mesh.instanceMatrix.needsUpdate = true
      // Raycasting checks this bound even when frustum culling is disabled.
      mesh.boundingSphere = null
    }
  }

  vehicleIdForHit(mesh: Object3D, instanceId: number | undefined): string | null {
    const type = this.meshClasses.get(mesh)
    return type && instanceId !== undefined ? this.batches.get(type)!.ids[instanceId] ?? null : null
  }

  get batchCounts() {
    return Object.fromEntries([...this.batches].map(([type, batch]) => [type, { entities: batch.count, parts: batch.meshes.length }])) as Record<VehicleClass, { entities: number; parts: number }>
  }

  get drawCallCount() {
    return [...this.batches.values()].reduce((count, batch) => count + (batch.count ? batch.meshes.length : 0), 0)
  }

  dispose() {
    if (this.disposed) return
    this.disposed = true
    for (const batch of this.batches.values()) for (const mesh of batch.meshes) mesh.dispose()
    this.group.clear()
    this.batches.clear()
    this.meshClasses.clear()
  }
}

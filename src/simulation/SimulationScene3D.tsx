import * as React from "react"
import {
  AmbientLight, BoxGeometry, BufferGeometry, CanvasTexture, CircleGeometry, Color, CylinderGeometry,
  DirectionalLight, DoubleSide, DynamicDrawUsage, Group, InstancedMesh, Line,
  LineDashedMaterial, LineLoop, LineBasicMaterial, Mesh, MeshBasicMaterial,
  MeshStandardMaterial, Object3D, PCFSoftShadowMap, PerspectiveCamera, Raycaster,
  Scene, Shape, ShapeGeometry, SphereGeometry, Sprite, SpriteMaterial, SRGBColorSpace, Vector2, Vector3,
  WebGLRenderer, type Material,
} from "three"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js"
import type { VisualPoint } from "@/api/visual-network"
import type { RenderFrame, RenderVehicle } from "@/simulation/frame-types"
import { boundsForJunction, headingToThreeYaw, lanePolygon, SCENE_PALETTE, selectionKey, signalAppearance, type SceneBounds, type SceneGeometry, type Selection } from "@/simulation/scene-geometry"
import type { PresentationState } from "@/simulation/presentation-state"
import { junctionTagText } from "@/simulation/scene-summary"
import { interpolateVehicle, interpolationDuration, isPresentationJump } from "@/simulation/entity-interpolation"
import { getFallbackVehicleAssetLibrary, loadVehicleAssetLibrary, VehicleFleetInstances, VEHICLE_CLASSES } from "@/simulation/vehicle-assets"
import { perspectiveBoundsFit } from "@/simulation/camera-fit"

export type ScenePerformanceSample = { fps: number; p95FrameMs: number; drawCalls: number; geometries: number; textures: number; frameLoops: number; displayedVehicles: number; displayedPedestrians: number }
type VehicleView = { previous: RenderVehicle; target: RenderVehicle; current: RenderVehicle }
type SceneProps = {
  frame: RenderFrame | null
  geometry: SceneGeometry
  presentation: PresentationState
  runKey: string
  onSelect: (selection: Selection | null) => void
  onUnavailable?: (message: string) => void
  onPerformanceSample?: (sample: ScenePerformanceSample) => void
}
let activeFrameLoops = 0

function polygonGeometry(points: readonly VisualPoint[], elevation: number) {
  const shape = new Shape()
  if (points.length) {
    shape.moveTo(points[0].x, points[0].y)
    points.slice(1).forEach((point) => shape.lineTo(point.x, point.y))
    shape.closePath()
  }
  return new ShapeGeometry(shape).rotateX(-Math.PI / 2).translate(0, elevation, 0)
}

function ribbon(points: readonly VisualPoint[], width: number, elevation = 0) {
  return polygonGeometry(lanePolygon(points, width), elevation)
}

function midpoint(points: readonly VisualPoint[]) {
  if (points.length < 2) return { x: points[0]?.x ?? 0, y: points[0]?.y ?? 0, heading: 0 }
  const index = Math.max(1, Math.floor(points.length / 2))
  const a = points[index - 1], b = points[index]
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, heading: Math.atan2(b.y - a.y, b.x - a.x) }
}

function distanceToSegment(point: VisualPoint, a: VisualPoint, b: VisualPoint) {
  const dx = b.x - a.x, dy = b.y - a.y
  const amount = Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / (dx * dx + dy * dy || 1)))
  return Math.hypot(point.x - a.x - amount * dx, point.y - a.y - amount * dy)
}

function pointInPolygon(point: VisualPoint, polygon: readonly VisualPoint[]) {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i], b = polygon[j]
    if ((a.y > point.y) !== (b.y > point.y) && point.x < (b.x - a.x) * (point.y - a.y) / (b.y - a.y) + a.x) inside = !inside
  }
  return inside
}

function stableHash(value: string) {
  let hash = 2166136261
  for (const character of value) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619)
  return hash >>> 0
}

// Per junction corner: an L of set-back buildings plus a street-tree row along each road edge (metres from centre).
const CORNER_BUILDINGS = [[26, 26], [42, 26], [26, 42]] as const
const CORNER_TREES = [[32, 14], [48, 14], [14, 32], [14, 48]] as const

/** Regular illustrative city blocks: stable, and kept outside buffered engine road/path geometry. */
function contextPlacements(geometry: SceneGeometry, pedestrianPaths: readonly { shape: VisualPoint[] }[] = []) {
  const candidates = geometry.junctions.flatMap((junction) => [-1, 1].flatMap((sx) => [-1, 1].flatMap((sy) => [
    ...CORNER_BUILDINGS.map(([dx, dy]) => ({ x: junction.center.x + sx * dx, y: junction.center.y + sy * dy, building: true })),
    ...CORNER_TREES.map(([dx, dy]) => ({ x: junction.center.x + sx * dx, y: junction.center.y + sy * dy, building: false })),
  ])))
  const accepted: typeof candidates = []
  return candidates.filter((candidate) => {
    const radius = candidate.building ? 8 : 2.5
    if (accepted.some((other) => Math.hypot(other.x - candidate.x, other.y - candidate.y) < (candidate.building && other.building ? 15 : 6))) return false
    if (!isClearOfNetwork(candidate, radius)) return false
    accepted.push(candidate)
    return true
  })

  function isClearOfNetwork(candidate: VisualPoint, radius: number) {
    if (geometry.junctions.some((junction) => pointInPolygon(candidate, junction.polygon) || junction.polygon.some((point, index) => distanceToSegment(candidate, point, junction.polygon[(index + 1) % junction.polygon.length]) < radius + 5))) return false
    if (geometry.lanes.some((lane) => lane.centerline.slice(1).some((point, index) => distanceToSegment(candidate, lane.centerline[index], point) < radius + lane.width / 2 + 5))) return false
    return !pedestrianPaths.some((path) => path.shape.slice(1).some((point, index) => distanceToSegment(candidate, path.shape[index], point) < radius + 5))
  }
}

export function SimulationScene3D(props: SceneProps) {
  const hostRef = React.useRef<HTMLDivElement | null>(null)
  const propsRef = React.useRef(props)
  const [assetNotice, setAssetNotice] = React.useState("")
  React.useEffect(() => { propsRef.current = props }, [props])

  React.useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const geometry = props.geometry
    let active = true
    let renderer: WebGLRenderer
    try { renderer = new WebGLRenderer({ antialias: true, powerPreference: "low-power" }) }
    catch {
      propsRef.current.onUnavailable?.("WebGL could not initialize. The current simulation remains available in the 2D view.")
      return
    }
    renderer.outputColorSpace = SRGBColorSpace
    renderer.domElement.className = "sf-three-canvas"
    renderer.domElement.setAttribute("aria-label", "Architectural traffic model. Drag to orbit, right-drag to pan, scroll to zoom. Use Inspect object for keyboard selection.")
    renderer.domElement.tabIndex = 0
    host.appendChild(renderer.domElement)
    const scene = new Scene()
    scene.background = new Color(SCENE_PALETTE.ground)
    const extent = Math.max(geometry.bounds.max_x - geometry.bounds.min_x, geometry.bounds.max_y - geometry.bounds.min_y)
    const camera = new PerspectiveCamera(44, 1, 0.1, Math.max(1000, extent * 5))
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = !window.matchMedia("(prefers-reduced-motion: reduce)").matches
    controls.minDistance = 8
    controls.maxDistance = Math.max(200, extent * 3)
    controls.maxPolarAngle = Math.PI * 0.47
    controls.screenSpacePanning = false
    scene.add(new AmbientLight(0xffffff, 2))
    const sun = new DirectionalLight(0xffffff, 2.2)
    sun.position.set(70, 150, 90)
    sun.shadow.mapSize.set(1024, 1024)
    sun.shadow.camera.left = -80
    sun.shadow.camera.right = 80
    sun.shadow.camera.top = 80
    sun.shadow.camera.bottom = -80
    sun.shadow.camera.near = 5
    sun.shadow.camera.far = 400
    sun.shadow.normalBias = 0.035
    scene.add(sun, sun.target)

    const geometries = new Set<BufferGeometry>()
    const materials = new Set<Material>()
    const staticPickables: Object3D[] = []
    const addMaterial = <T extends Material>(surface: T) => { materials.add(surface); return surface }
    const addGeometry = <T extends BufferGeometry>(value: T) => { geometries.add(value); return value }
    const surface = (color: string | number) => addMaterial(new MeshStandardMaterial({ color, roughness: 1, metalness: 0, side: DoubleSide }))
    const roadSurface = surface(SCENE_PALETTE.pavement)
    const curbSurface = surface(SCENE_PALETTE.curb)
    const markingsSurface = surface(SCENE_PALETTE.markings)
    const poleSurface = surface(0x30383d)
    const mesh = (shape: BufferGeometry, appearance: Material, parent: Object3D = scene) => {
      const result = new Mesh(addGeometry(shape), appearance)
      result.receiveShadow = true
      parent.add(result)
      return result
    }
    const merge = (parts: BufferGeometry[], appearance: Material, parent: Object3D = scene) => {
      if (!parts.length) return
      const combined = mergeGeometries(parts)
      parts.forEach((part) => part.dispose())
      if (combined) mesh(combined, appearance, parent)
    }
    const laneSurfaces = new Map<string, MeshStandardMaterial>()
    const markingParts: BufferGeometry[] = []
    const curbs: BufferGeometry[] = []
    const arrowParts: BufferGeometry[] = []
    const connectors = new Group(), arrows = new Group(), signalGroup = new Group()
    const context = new Group(), pedestrianPaths = new Group(), restrictions = new Group()
    scene.add(connectors, arrows, signalGroup, context, pedestrianPaths, restrictions)
    // Junction tags match the 2D map tags; clicks still land on the junction surface underneath.
    const junctionTags = new Map<string, Sprite>(), tagTextures: CanvasTexture[] = []
    for (const junction of geometry.junctions) {
      const text = junctionTagText(junction.label), tagCanvas = document.createElement("canvas"), drawing = tagCanvas.getContext("2d")
      if (!drawing) continue
      drawing.font = "600 40px system-ui"
      tagCanvas.width = Math.ceil(drawing.measureText(text).width) + 48
      tagCanvas.height = 72
      drawing.font = "600 40px system-ui"
      drawing.fillStyle = "#1F7A5A"; drawing.beginPath(); drawing.roundRect(0, 0, tagCanvas.width, tagCanvas.height, 18); drawing.fill()
      drawing.fillStyle = "#FFFFFF"; drawing.textAlign = "center"; drawing.textBaseline = "middle"; drawing.fillText(text, tagCanvas.width / 2, tagCanvas.height / 2)
      const texture = new CanvasTexture(tagCanvas)
      texture.colorSpace = SRGBColorSpace
      tagTextures.push(texture)
      const tag = new Sprite(addMaterial(new SpriteMaterial({ map: texture, depthTest: false, transparent: true })))
      tag.scale.set(tagCanvas.width / tagCanvas.height * 3.5, 3.5, 1)
      tag.position.set(junction.center.x, 12, -junction.center.y)
      tag.renderOrder = 10
      scene.add(tag)
      junctionTags.set(junction.id, tag)
    }
    for (const lane of geometry.lanes) {
      if (lane.kind === "connector") {
        mesh(ribbon(lane.centerline, 0.09, 0.07), markingsSurface, connectors)
        continue
      }
      if (lane.kind !== "road") continue
      const laneSurface = surface(SCENE_PALETTE.pavement)
      laneSurfaces.set(lane.id, laneSurface)
      const laneMesh = mesh(polygonGeometry(lane.polygon, 0.025), laneSurface)
      laneMesh.userData.selection = { kind: "lane", id: lane.id }
      staticPickables.push(laneMesh)
      curbs.push(ribbon(lane.centerline, lane.width + 0.26, 0.018))
      const edge = lane.centerline.map((point, index) => {
        const before = lane.centerline[Math.max(0, index - 1)], after = lane.centerline[Math.min(lane.centerline.length - 1, index + 1)]
        const angle = Math.atan2(after.y - before.y, after.x - before.x)
        return { x: point.x - Math.sin(angle) * (lane.width / 2 - 0.13), y: point.y + Math.cos(angle) * (lane.width / 2 - 0.13) }
      })
      markingParts.push(ribbon(edge, 0.09, 0.035))
      const middle = midpoint(lane.centerline)
      const direction = { x: Math.cos(middle.heading), y: Math.sin(middle.heading) }, normal = { x: -Math.sin(middle.heading), y: Math.cos(middle.heading) }
      arrowParts.push(polygonGeometry([
        { x: middle.x + direction.x * 1.4, y: middle.y + direction.y * 1.4 },
        { x: middle.x - direction.x * 0.7 + normal.x * 0.6, y: middle.y - direction.y * 0.7 + normal.y * 0.6 },
        { x: middle.x - direction.x * 0.7 - normal.x * 0.6, y: middle.y - direction.y * 0.7 - normal.y * 0.6 },
      ], 0.055))
    }
    merge(curbs, curbSurface)
    for (const junction of geometry.junctions) {
      const pavement = mesh(polygonGeometry(junction.polygon, 0.04), roadSurface)
      pavement.userData.selection = { kind: "junction", id: junction.id }
      staticPickables.push(pavement)
    }
    const signalLamps: Array<{ signal: SceneGeometry["signalGroups"][number]; lamps: Record<"red" | "yellow" | "green", number> }> = []
    const poleParts: BufferGeometry[] = []
    const lampGeometry = addGeometry(new SphereGeometry(0.16, 8, 6))
    const lampSurface = addMaterial(new MeshBasicMaterial({ color: 0xffffff }))
    const lampInstances = new InstancedMesh(lampGeometry, lampSurface, Math.max(1, geometry.signalGroups.length * 3))
    lampInstances.count = geometry.signalGroups.length * 3
    const lampTransform = new Object3D(), lampColor = new Color(SCENE_PALETTE.off)
    const lampJunctions: Array<string | null> = []
    let lampIndex = 0
    signalGroup.add(lampInstances)
    staticPickables.push(lampInstances)
    for (const signal of geometry.signalGroups) {
      markingParts.push(ribbon(signal.stop_line, 0.25, 0.06))
      const angle = signal.heading * Math.PI / 180
      const x = signal.anchor.x - Math.sin(angle) * (signal.width / 2 + 0.55), z = -signal.anchor.y - Math.cos(angle) * (signal.width / 2 + 0.55)
      poleParts.push(new CylinderGeometry(0.08, 0.08, 2.9, 6).translate(x, 1.45, z))
      poleParts.push(new BoxGeometry(0.5, 1.18, 0.4).translate(x, 3.12, z))
      const lamps = {} as Record<"red" | "yellow" | "green", number>
      for (const [color, height] of [["red", 3.48], ["yellow", 3.12], ["green", 2.76]] as const) {
        lampTransform.position.set(x + 0.08, height, z + 0.17)
        lampTransform.updateMatrix()
        lampInstances.setMatrixAt(lampIndex, lampTransform.matrix)
        lampInstances.setColorAt(lampIndex, lampColor)
        lampJunctions.push(signal.junctionId)
        lamps[color] = lampIndex++
      }
      signalLamps.push({ signal, lamps })
    }
    merge(poleParts, poleSurface, signalGroup)
    merge(markingParts, markingsSurface)
    merge(arrowParts, markingsSurface, arrows)
    const floor = mesh(new BoxGeometry(Math.max(200, extent + 160), 0.08, Math.max(200, extent + 160)), surface(SCENE_PALETTE.ground))
    floor.position.set((geometry.bounds.min_x + geometry.bounds.max_x) / 2, -0.06, -(geometry.bounds.min_y + geometry.bounds.max_y) / 2)

    const contextBuildingGeometry = addGeometry(new BoxGeometry(1, 1, 1))
    const contextTrunkGeometry = addGeometry(new CylinderGeometry(0.32, 0.42, 2.3, 6))
    const contextCrownGeometry = addGeometry(new SphereGeometry(2.3, 8, 6))
    const contextBuildingSurface = surface(SCENE_PALETTE.building), contextTrunkSurface = surface(0x8a7d68), contextCrownSurface = surface(SCENE_PALETTE.vegetation)
    let contextMeshes: InstancedMesh[] = []
    const dummy = new Object3D()
    const configureInstances = (shape: BufferGeometry, appearance: Material, count: number, parent: Object3D = scene) => {
      const result = new InstancedMesh(shape, appearance, Math.max(1, count))
      result.count = count
      result.frustumCulled = false
      result.instanceMatrix.setUsage(DynamicDrawUsage)
      parent.add(result)
      return result
    }
    let currentQuality = ""
    const rebuildContext = (paths: readonly { shape: VisualPoint[] }[]) => {
      contextMeshes.forEach((value) => value.dispose())
      context.clear()
      const placements = contextPlacements(geometry, paths)
      const buildings = placements.filter((item) => item.building), trees = placements.filter((item) => !item.building)
      const buildingMesh = configureInstances(contextBuildingGeometry, contextBuildingSurface, buildings.length, context)
      const trunks = configureInstances(contextTrunkGeometry, contextTrunkSurface, trees.length, context), crowns = configureInstances(contextCrownGeometry, contextCrownSurface, trees.length, context)
      buildings.forEach((point, index) => {
        const height = 6 + stableHash(`${point.x}:${point.y}`) % 7
        dummy.position.set(point.x, height / 2, -point.y)
        dummy.rotation.set(0, 0, 0)
        dummy.scale.set(12, height, 12)
        dummy.updateMatrix()
        buildingMesh.setMatrixAt(index, dummy.matrix)
      })
      trees.forEach((point, index) => {
        dummy.position.set(point.x, 1.15, -point.y)
        dummy.rotation.set(0, 0, 0)
        dummy.scale.set(1, 1, 1)
        dummy.updateMatrix()
        trunks.setMatrixAt(index, dummy.matrix)
        dummy.position.y = 3.2
        dummy.scale.set(1, 0.75, 1)
        dummy.updateMatrix()
        crowns.setMatrixAt(index, dummy.matrix)
      })
      contextMeshes = [buildingMesh, trunks, crowns]
      contextMeshes.forEach((value) => { value.instanceMatrix.needsUpdate = true; value.castShadow = currentQuality === "enhanced" })
    }

    let library = getFallbackVehicleAssetLibrary(), fleet = new VehicleFleetInstances(library, 300)
    scene.add(fleet.group)
    const shadowGeometry = addGeometry(new CircleGeometry(0.5, 12).rotateX(-Math.PI / 2))
    const shadowMaterial = addMaterial(new MeshBasicMaterial({ color: 0x263130, transparent: true, opacity: 0.14, depthWrite: false }))
    const blobShadows = configureInstances(shadowGeometry, shadowMaterial, 300)
    const personParts = [new CylinderGeometry(0.21, 0.23, 0.7, 7).translate(0, 0.95, 0), new BoxGeometry(0.12, 0.58, 0.13).translate(-0.1, 0.31, 0), new BoxGeometry(0.12, 0.58, 0.13).translate(0.1, 0.31, 0)]
    const personGeometry = mergeGeometries(personParts)!
    personParts.forEach((value) => value.dispose())
    const people = configureInstances(addGeometry(personGeometry), surface(SCENE_PALETTE.pedestrian), 128)
    const heads = configureInstances(addGeometry(new SphereGeometry(0.16, 8, 6).translate(0, 1.44, 0)), surface(0xd9bda4), 128)
    let pedestrianIds: string[] = []
    const selectionMaterial = addMaterial(new LineBasicMaterial({ color: SCENE_PALETTE.selected, depthTest: false }))
    let selectionGeometry = addGeometry(new BufferGeometry())
    const selectionOutline = new LineLoop(selectionGeometry, selectionMaterial)
    selectionOutline.renderOrder = 10
    scene.add(selectionOutline)
    let selectedKey = ""
    const pathsMaterial = addMaterial(new LineDashedMaterial({ color: SCENE_PALETTE.markings, dashSize: 0.7, gapSize: 0.6, linewidth: 1 }))
    let pathGeometries: BufferGeometry[] = [], pathSignature = "", restrictionSignature = "", focusSignature = ""
    let lastFrame: RenderFrame | null = null
    let lastRun = propsRef.current.runKey, revision = propsRef.current.presentation.revision
    let updatedAt = performance.now(), duration = 1
    const vehicles = new Map<string, VehicleView>(), drawnVehicles: RenderVehicle[] = []

    const setCameraBounds = (bounds: SceneBounds) => {
      const x = (bounds.min_x + bounds.max_x) / 2, z = -(bounds.min_y + bounds.max_y) / 2
      const { offset } = perspectiveBoundsFit(bounds, camera.fov, camera.aspect)
      camera.position.set(x + offset.x, offset.y, z + offset.z)
      controls.target.set(x, 0, z)
      sun.position.set(x + 70, 150, z + 90)
      sun.target.position.set(x, 0, z)
      controls.update()
    }
    const applyQuality = () => {
      const quality = propsRef.current.presentation.quality
      if (quality === currentQuality) return
      currentQuality = quality
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, quality === "enhanced" ? 1.5 : 1.25))
      renderer.shadowMap.enabled = quality === "enhanced"
      renderer.shadowMap.type = PCFSoftShadowMap
      sun.castShadow = quality === "enhanced"
      fleet.group.children.forEach((value) => { if (value instanceof Mesh) value.castShadow = quality === "enhanced" })
      people.castShadow = heads.castShadow = quality === "enhanced"
      contextMeshes.forEach((value) => { value.castShadow = quality === "enhanced" })
      blobShadows.visible = quality === "laptop"
      renderer.setSize(Math.max(1, host.clientWidth), Math.max(1, host.clientHeight), false)
    }
    const resize = () => {
      renderer.setSize(Math.max(1, host.clientWidth), Math.max(1, host.clientHeight), false)
      camera.aspect = Math.max(1, host.clientWidth) / Math.max(1, host.clientHeight)
      camera.updateProjectionMatrix()
      if (!focusSignature) setCameraBounds(boundsForJunction(geometry, propsRef.current.presentation.junctionId))
    }
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    applyQuality()
    resize()
    rebuildContext(propsRef.current.frame?.visual.pedestrian_paths ?? [])

    const updatePaths = (frame: RenderFrame | null) => {
      const paths = frame?.visual.pedestrian_paths ?? [], signature = JSON.stringify(paths)
      if (signature === pathSignature) return
      pathSignature = signature
      pathGeometries.forEach((value) => value.dispose())
      pathGeometries = []
      pedestrianPaths.clear()
      for (const path of paths) {
        const shape = new BufferGeometry().setFromPoints(path.shape.map((point) => new Vector3(point.x, 0.085, -point.y)))
        pathGeometries.push(shape)
        const line = new Line(shape, pathsMaterial)
        line.computeLineDistances()
        pedestrianPaths.add(line)
      }
      rebuildContext(paths)
    }
    const updateRestrictions = (frame: RenderFrame | null) => {
      const closed = frame?.visual.closed_lanes ?? [], slow = frame?.visual.slow_lanes ?? {}, signature = JSON.stringify([closed, slow])
      if (signature === restrictionSignature) return
      restrictionSignature = signature
      restrictions.clear()
      for (const lane of geometry.lanes) {
        if (lane.kind !== "road") continue
        const closedLane = closed.includes(lane.id), slowdown = slow[lane.id] < 1
        if (!closedLane && !slowdown) continue
        const position = closedLane ? lane.centerline[0] : midpoint(lane.centerline)
        if (!position) continue
        const prop = library.createRoadProp(closedLane ? "barrier" : "cone", closedLane ? lane.width * 0.92 : 0.6, 0.6)
        prop.position.set(position.x, 0.05, -position.y)
        prop.rotation.y = midpoint(lane.centerline).heading + Math.PI / 2
        prop.userData.selection = { kind: "lane", id: lane.id }
        prop.traverse((value) => { value.userData.selection = prop.userData.selection })
        restrictions.add(prop)
      }
    }
    loadVehicleAssetLibrary().then((loaded) => {
      if (!active) { loaded.dispose(); return }
      scene.remove(fleet.group)
      fleet.dispose()
      library.dispose()
      library = loaded
      fleet = new VehicleFleetInstances(library, 300, currentQuality === "enhanced")
      scene.add(fleet.group)
      restrictionSignature = ""
      setAssetNotice(loaded.issues.map((issue) => issue.message).join(" "))
      host.dataset.vehicleAssetSources = JSON.stringify(Object.fromEntries(VEHICLE_CLASSES.map((type) => [type, loaded.template(type).source])))
    })

    const raycaster = new Raycaster(), pointer = new Vector2()
    let pointerStart = { x: 0, y: 0 }
    const pointerDown = (event: PointerEvent) => { pointerStart = { x: event.clientX, y: event.clientY } }
    const pick = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 5 || event.button !== 0) return
      const box = renderer.domElement.getBoundingClientRect()
      pointer.set((event.clientX - box.left) / box.width * 2 - 1, -((event.clientY - box.top) / box.height) * 2 + 1)
      raycaster.setFromCamera(pointer, camera)
      const hits = raycaster.intersectObjects([...fleet.group.children, people, heads, ...restrictions.children, ...staticPickables], true)
      for (const hit of hits) {
        const id = fleet.vehicleIdForHit(hit.object, hit.instanceId)
        if (id) { propsRef.current.onSelect({ kind: "vehicle", id }); return }
        if (hit.object === people || hit.object === heads) {
          const person = hit.instanceId === undefined ? null : pedestrianIds[hit.instanceId]
          if (person) { propsRef.current.onSelect({ kind: "pedestrian", id: person }); return }
        }
        if (hit.object === lampInstances && hit.instanceId !== undefined) {
          const junction = lampJunctions[hit.instanceId]
          if (junction) { propsRef.current.onSelect({ kind: "junction", id: junction }); return }
        }
        if (hit.object.userData.selection) { propsRef.current.onSelect(hit.object.userData.selection); return }
      }
      propsRef.current.onSelect(null)
    }
    const contextLost = (event: Event) => {
      event.preventDefault()
      propsRef.current.onUnavailable?.("The WebGL context was lost. Switched to 2D with the same authoritative simulation state.")
    }
    renderer.domElement.addEventListener("pointerdown", pointerDown)
    renderer.domElement.addEventListener("pointerup", pick)
    renderer.domElement.addEventListener("webglcontextlost", contextLost)

    const updateSelection = (presentation: PresentationState) => {
      const selection = presentation.selection, key = selectionKey(selection)
      selectionOutline.visible = Boolean(selection)
      if (!selection) return
      if (key !== selectedKey) {
        selectedKey = key
        let points: VisualPoint[]
        if (selection.kind === "lane") points = geometry.laneById.get(selection.id)?.polygon ?? []
        else if (selection.kind === "junction") points = geometry.junctionById.get(selection.id)?.polygon ?? []
        else if (selection.kind === "vehicle") points = [{ x: -0.5, y: -0.5 }, { x: 0.5, y: -0.5 }, { x: 0.5, y: 0.5 }, { x: -0.5, y: 0.5 }]
        else points = Array.from({ length: 16 }, (_, index) => ({ x: Math.cos(index / 16 * Math.PI * 2) * 0.6, y: Math.sin(index / 16 * Math.PI * 2) * 0.6 }))
        selectionGeometry.dispose()
        geometries.delete(selectionGeometry)
        selectionGeometry = addGeometry(new BufferGeometry().setFromPoints(points.map((point) => new Vector3(point.x, 0.15, -point.y))))
        selectionOutline.geometry = selectionGeometry
        selectionGeometry.computeBoundingSphere()
      }
      selectionOutline.position.set(0, 0, 0)
      selectionOutline.rotation.set(0, 0, 0)
      selectionOutline.scale.set(1, 1, 1)
      if (selection.kind === "vehicle") {
        const current = vehicles.get(selection.id)?.current
        if (!current) { selectionOutline.visible = false; return }
        selectionOutline.position.set(current.x, 0, -current.y)
        selectionOutline.rotation.y = headingToThreeYaw(current.angle)
        selectionOutline.scale.set(current.length + 0.7, 1, current.width + 0.7)
      } else if (selection.kind === "pedestrian") {
        const current = propsRef.current.frame?.pedestrians.find((person) => person.id === selection.id)
        selectionOutline.visible = Boolean(current)
        if (current) selectionOutline.position.set(current.x, 0, -current.y)
      }
    }

    let animationId = 0, sampleStarted = performance.now(), previousRenderedAt = sampleStarted, renderedFrames = 0
    let frameIntervals: number[] = []
    const frameHistory: Array<{ time: number; interval: number }> = []
    activeFrameLoops += 1
    const animate = () => {
      if (!active) return
      const { frame: next, presentation, runKey } = propsRef.current, now = performance.now()
      applyQuality()
      const jumped = revision !== presentation.revision
      if (next !== lastFrame || jumped) {
        const snap = !next || jumped || isPresentationJump(lastFrame, next, lastRun, runKey)
        const ids = new Set(next?.vehicles.map((vehicle) => vehicle.id) ?? [])
        for (const id of vehicles.keys()) if (!ids.has(id)) vehicles.delete(id)
        if (next) for (const vehicle of next.vehicles) {
          const existing = vehicles.get(vehicle.id), previous = snap || !existing ? vehicle : existing.current
          vehicles.set(vehicle.id, { previous, target: vehicle, current: previous })
        }
        duration = next && !snap ? interpolationDuration(lastFrame, next) : 1
        updatedAt = now
        lastFrame = next
        lastRun = runKey
        revision = presentation.revision
        updatePaths(next)
        pedestrianIds = (next?.pedestrians ?? []).slice(0, 128).map((person) => person.id)
        for (const [index, person] of (next?.pedestrians ?? []).slice(0, 128).entries()) {
          dummy.position.set(person.x, 0.05, -person.y)
          dummy.rotation.set(0, 0, 0)
          dummy.scale.set(1, 1, 1)
          dummy.updateMatrix()
          people.setMatrixAt(index, dummy.matrix)
          heads.setMatrixAt(index, dummy.matrix)
        }
        people.count = heads.count = pedestrianIds.length
        people.instanceMatrix.needsUpdate = heads.instanceMatrix.needsUpdate = true
        people.boundingSphere = heads.boundingSphere = null
      }
      drawnVehicles.length = 0
      for (const vehicle of vehicles.values()) {
        vehicle.current = interpolateVehicle(vehicle.previous, vehicle.target, now - updatedAt, duration)
        drawnVehicles.push(vehicle.current)
      }
      fleet.update(drawnVehicles)
      blobShadows.count = Math.min(drawnVehicles.length, 300)
      for (let index = 0; index < blobShadows.count; index++) {
        const vehicle = drawnVehicles[index]
        dummy.position.set(vehicle.x, 0.052, -vehicle.y)
        dummy.rotation.set(0, headingToThreeYaw(vehicle.angle), 0)
        dummy.scale.set(vehicle.length * 0.95, 1, vehicle.width * 0.95)
        dummy.updateMatrix()
        blobShadows.setMatrixAt(index, dummy.matrix)
      }
      blobShadows.instanceMatrix.needsUpdate = true
      const currentFocus = `${presentation.focus}:${presentation.junctionId}:${presentation.focus === "follow" ? selectionKey(presentation.selection) : ""}:${presentation.revision}`
      if (currentFocus !== focusSignature) {
        focusSignature = currentFocus
        if (presentation.focus === "network") setCameraBounds(geometry.bounds)
        else if (presentation.focus === "junction") setCameraBounds(boundsForJunction(geometry, presentation.junctionId))
        else if (presentation.selection?.kind === "vehicle") {
          const vehicle = vehicles.get(presentation.selection.id)?.current
          if (vehicle) setCameraBounds({ min_x: vehicle.x - 18, max_x: vehicle.x + 18, min_y: vehicle.y - 18, max_y: vehicle.y + 18 })
        }
      }
      if (presentation.focus === "follow" && presentation.selection?.kind === "vehicle") {
        const vehicle = vehicles.get(presentation.selection.id)?.current
        if (vehicle) {
          const dx = vehicle.x - controls.target.x, dz = -vehicle.y - controls.target.z
          controls.target.set(vehicle.x, 0, -vehicle.y)
          camera.position.x += dx
          camera.position.z += dz
        }
      }
      connectors.visible = presentation.overlays.connectors
      arrows.visible = presentation.overlays.arrows
      const taggedJunction = presentation.selection?.kind === "junction" ? presentation.selection.id : presentation.junctionId
      for (const [id, tag] of junctionTags) { tag.visible = presentation.overlays.labels; tag.material.opacity = id === taggedJunction ? 1 : .55 }
      context.visible = presentation.overlays.context
      signalGroup.visible = presentation.overlays.signals
      updateRestrictions(next)
      for (const [id, appearance] of laneSurfaces) {
        const metric = next?.lane_metrics?.[id], closed = next?.visual.closed_lanes.includes(id), slow = (next?.visual.slow_lanes[id] ?? 1) < 1
        const count = metric?.queue ?? 0
        const queueColor = count >= 10 ? 0xa67161 : count >= 5 ? 0xa49164 : count >= 1 ? 0x667a79 : SCENE_PALETTE.pavement
        appearance.color.set(closed ? SCENE_PALETTE.closed : slow ? SCENE_PALETTE.slow : presentation.overlays.heatmap && metric ? queueColor : SCENE_PALETTE.pavement)
      }
      for (const { signal, lamps } of signalLamps) {
        const state = signalAppearance(signal, next)
        for (const color of ["red", "yellow", "green"] as const) {
          const lit = state.lit && state.color === color
          lampColor.set(lit ? SCENE_PALETTE[color] : SCENE_PALETTE.off)
          lampInstances.setColorAt(lamps[color], lampColor)
        }
      }
      if (lampInstances.instanceColor) lampInstances.instanceColor.needsUpdate = true
      updateSelection(presentation)
      controls.update()
      renderer.render(scene, camera)
      const interval = now - previousRenderedAt
      frameIntervals.push(interval)
      frameHistory.push({ time: now, interval })
      while (frameHistory[0]?.time < now - 60000) frameHistory.shift()
      previousRenderedAt = now
      renderedFrames += 1
      if (now - sampleStarted >= 2000) {
        const ordered = [...frameIntervals].sort((a, b) => a - b)
        const sample: ScenePerformanceSample = {
          fps: Math.round(renderedFrames * 1000 / (now - sampleStarted) * 10) / 10,
          p95FrameMs: Math.round((ordered[Math.min(ordered.length - 1, Math.floor(ordered.length * 0.95))] ?? 0) * 10) / 10,
          drawCalls: renderer.info.render.calls, geometries: renderer.info.memory.geometries,
          textures: renderer.info.memory.textures, frameLoops: activeFrameLoops,
          displayedVehicles: fleet.displayedCount, displayedPedestrians: people.count,
        }
        host.dataset.performance = JSON.stringify(sample)
        host.dataset.frameIntervals = JSON.stringify(frameIntervals.map((interval) => Math.round(interval * 100) / 100))
        host.dataset.frameIntervals60Seconds = JSON.stringify(frameHistory.map((entry) => Math.round(entry.interval * 100) / 100))
        host.dataset.vehicleBatchCounts = JSON.stringify(fleet.batchCounts)
        propsRef.current.onPerformanceSample?.(sample)
        sampleStarted = now
        renderedFrames = 0
        frameIntervals = []
      }
      animationId = requestAnimationFrame(animate)
    }
    animate()
    return () => {
      active = false
      activeFrameLoops -= 1
      cancelAnimationFrame(animationId)
      observer.disconnect()
      renderer.domElement.removeEventListener("pointerdown", pointerDown)
      renderer.domElement.removeEventListener("pointerup", pick)
      renderer.domElement.removeEventListener("webglcontextlost", contextLost)
      controls.dispose()
      fleet.dispose()
      contextMeshes.forEach((value) => value.dispose())
      people.dispose()
      heads.dispose()
      blobShadows.dispose()
      lampInstances.dispose()
      restrictions.clear()
      library.dispose()
      pathGeometries.forEach((value) => value.dispose())
      geometries.forEach((value) => value.dispose())
      materials.forEach((value) => value.dispose())
      tagTextures.forEach((value) => value.dispose())
      sun.shadow.map?.dispose()
      renderer.dispose()
      renderer.domElement.remove()
      delete host.dataset.performance
      delete host.dataset.frameIntervals
      delete host.dataset.frameIntervals60Seconds
    }
  }, [props.geometry])

  return <div className="sf-three-shell">
    <div ref={hostRef} className="sf-three-host" data-renderer="native-three" />
    {assetNotice ? <p className="sf-scene-asset-notice" role="status">{assetNotice}</p> : null}
  </div>
}

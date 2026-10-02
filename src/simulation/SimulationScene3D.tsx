import * as React from "react"
import {
  AmbientLight, BoxGeometry, BufferGeometry, Color, CylinderGeometry,
  DirectionalLight, Float32BufferAttribute, Group, Mesh, MeshStandardMaterial,
  PerspectiveCamera, Scene, SphereGeometry, SRGBColorSpace, WebGLRenderer,
} from "three"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js"
import { FocusIcon, RotateCcwIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { getVisualNetwork, type VisualNetwork, type VisualPoint } from "@/api/visual-network"
import type { RenderFrame, RenderVehicle } from "@/simulation/frame-types"

function ribbon(points: VisualPoint[], width: number, elevation = 0) {
  const vertices: number[] = []
  const sides = points.map((point, index) => {
    const before = points[Math.max(0, index - 1)]
    const after = points[Math.min(points.length - 1, index + 1)]
    const heading = Math.atan2(after.y - before.y, after.x - before.x)
    const dx = Math.sin(heading) * width / 2
    const dy = -Math.cos(heading) * width / 2
    return [[point.x + dx, elevation, -point.y - dy], [point.x - dx, elevation, -point.y + dy]]
  })
  for (let index = 1; index < sides.length; index++) {
    const [a, b] = sides[index - 1]
    const [c, d] = sides[index]
    vertices.push(...a, ...b, ...c, ...b, ...d, ...c)
  }
  const geometry = new BufferGeometry()
  geometry.setAttribute("position", new Float32BufferAttribute(vertices, 3))
  geometry.computeVertexNormals()
  return geometry
}

type CarView = { group: Group; previous: RenderVehicle; target: RenderVehicle; updatedAt: number }

export function SimulationScene3D({ frame, intersectionId, onUnavailable, onPerformanceSample }: {
  frame: RenderFrame | null
  intersectionId?: string | null
  onUnavailable?: (message: string) => void
  onPerformanceSample?: (sample: { fps: number; p95FrameMs: number; drawCalls: number }) => void
}) {
  const hostRef = React.useRef<HTMLDivElement | null>(null)
  const frameRef = React.useRef(frame)
  const performanceSampleRef = React.useRef(onPerformanceSample)
  const resetViewRef = React.useRef<() => void>(() => undefined)
  const followRef = React.useRef(false)
  const [following, setFollowing] = React.useState(false)
  const [network, setNetwork] = React.useState<VisualNetwork | null>(null)
  const [error, setError] = React.useState("")
  React.useEffect(() => { frameRef.current = frame }, [frame])
  React.useEffect(() => { performanceSampleRef.current = onPerformanceSample }, [onPerformanceSample])
  React.useEffect(() => {
    let active = true
    getVisualNetwork(intersectionId).then((result) => {
      if (active) { setNetwork(result); setError("") }
    }).catch(() => { if (active) setError("Road network could not be loaded.") })
    return () => { active = false }
  }, [intersectionId])

  React.useEffect(() => {
    const host = hostRef.current
    if (!host || !network) return
    let renderer: WebGLRenderer
    try {
      renderer = new WebGLRenderer({ antialias: true, powerPreference: "low-power" })
    } catch {
      onUnavailable?.("3D is unavailable in this browser. Use the 2D view.")
      return
    }
    renderer.outputColorSpace = SRGBColorSpace
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
    renderer.domElement.className = "sf-three-canvas"
    renderer.domElement.setAttribute("aria-label", "Live Tagum road network. Drag to orbit, right-drag to pan, scroll to zoom.")
    host.appendChild(renderer.domElement)
    const scene = new Scene()
    scene.background = new Color(0xe8ecef)
    const { min_x, max_x, min_y, max_y } = network.bounds
    const centerX = (min_x + max_x) / 2
    const centerZ = -(min_y + max_y) / 2
    const extent = Math.max(max_x - min_x, max_y - min_y)
    const camera = new PerspectiveCamera(42, 1, 0.1, Math.max(3000, extent * 10))
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.minDistance = 8
    controls.maxDistance = extent * 3
    controls.maxPolarAngle = Math.PI * 0.48
    controls.screenSpacePanning = false
    const resetView = () => {
      const verticalFov = camera.fov * Math.PI / 180
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect)
      const radius = Math.hypot(max_x - min_x, max_y - min_y) / 2
      const distance = radius / Math.sin(Math.min(verticalFov, horizontalFov) / 2) * 1.05
      camera.position.set(centerX + distance * 0.2, distance * 0.8, centerZ + distance * 0.56)
      controls.target.set(centerX, 0, centerZ)
      controls.update()
    }
    resetViewRef.current = resetView
    resetView()
    scene.add(new AmbientLight(0xffffff, 2))
    const sun = new DirectionalLight(0xffffff, 2)
    sun.position.set(-100, 250, 150)
    scene.add(sun)
    const roadMaterial = new MeshStandardMaterial({ color: 0x414852, roughness: 1, side: 2 })
    const markingMaterial = new MeshStandardMaterial({ color: 0xf4f0dc, roughness: 1, side: 2 })
    const poleMaterial = new MeshStandardMaterial({ color: 0x30363b })
    const bodyMaterial = new MeshStandardMaterial({ color: 0xf4b73d, roughness: 0.65 })
    const emergencyMaterial = new MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.65 })
    const emergencyRed = new MeshStandardMaterial({ color: 0xef4444, emissive: 0xef4444, emissiveIntensity: 0.5 })
    const emergencyBlue = new MeshStandardMaterial({ color: 0x2563eb, emissive: 0x2563eb, emissiveIntensity: 0.5 })
    const pedestrianMaterial = new MeshStandardMaterial({ color: 0xf97316, roughness: 0.8 })
    const glassMaterial = new MeshStandardMaterial({ color: 0x314c60, roughness: 0.45 })
    const tireMaterial = new MeshStandardMaterial({ color: 0x202327 })
    const geometries: BufferGeometry[] = []
    const materials = [roadMaterial, markingMaterial, poleMaterial, bodyMaterial, emergencyMaterial, emergencyRed, emergencyBlue, pedestrianMaterial, glassMaterial, tireMaterial]
    const laneMaterials = new Map<string, MeshStandardMaterial>()
    const markingGeometries: BufferGeometry[] = []
    const addMesh = (geometry: BufferGeometry, material: MeshStandardMaterial, parent: Group | Scene = scene) => {
      geometries.push(geometry)
      const mesh = new Mesh(geometry, material)
      parent.add(mesh)
      return mesh
    }
    for (const road of [...network.roads, ...network.internal_lanes]) {
      for (const lane of road.lanes) {
        const laneMaterial = roadMaterial.clone()
        materials.push(laneMaterial)
        laneMaterials.set(lane.id, laneMaterial)
        addMesh(ribbon(lane.shape, lane.width, 0.01), laneMaterial)
        // Fine edge markings follow the actual polyline rather than a rectangular grid.
        const edge = lane.shape.map((point, index) => {
          const a = lane.shape[Math.max(0, index - 1)]
          const b = lane.shape[Math.min(lane.shape.length - 1, index + 1)]
          const heading = Math.atan2(b.y - a.y, b.x - a.x)
          return { x: point.x + Math.sin(heading) * (lane.width / 2 - 0.12), y: point.y - Math.cos(heading) * (lane.width / 2 - 0.12) }
        })
        markingGeometries.push(ribbon(edge, 0.1, 0.025))
      }
    }
    for (const crossing of network.crossings) {
      for (const lane of crossing.lanes) markingGeometries.push(ribbon(lane.shape, lane.width, 0.035))
    }
    for (const junction of network.signals) {
      const vertices: number[] = []
      for (let index = 0; index < junction.shape.length; index++) {
        const a = junction.shape[index]
        const b = junction.shape[(index + 1) % junction.shape.length]
        vertices.push(junction.x, 0, -junction.y, a.x, 0, -a.y, b.x, 0, -b.y)
      }
      const pavement = new BufferGeometry()
      pavement.setAttribute("position", new Float32BufferAttribute(vertices, 3))
      pavement.computeVertexNormals()
      addMesh(pavement, roadMaterial)
    }
    const lamps = new Map<string, MeshStandardMaterial>()
    for (const signal of network.signal_groups) {
      markingGeometries.push(ribbon(signal.stop_line, 0.3, 0.04))
      const heading = signal.heading * Math.PI / 180
      const x = signal.anchor.x + Math.sin(heading) * 2.2
      const z = -signal.anchor.y + Math.cos(heading) * 2.2
      const pole = addMesh(new CylinderGeometry(0.12, 0.12, 3.5, 6), poleMaterial)
      pole.position.set(x, 1.75, z)
      const housing = addMesh(new BoxGeometry(0.55, 1.3, 0.45), poleMaterial)
      housing.position.set(x, 3.6, z)
      const material = new MeshStandardMaterial({ color: 0xe84b4b, emissive: 0xe84b4b, emissiveIntensity: 0.6 })
      materials.push(material)
      const lamp = addMesh(new SphereGeometry(0.24, 8, 6), material)
      lamp.position.set(x, 3.6, z)
      lamps.set(signal.signal_id, material)
    }
    if (markingGeometries.length) {
      const combinedMarkings = mergeGeometries(markingGeometries)
      if (combinedMarkings) addMesh(combinedMarkings, markingMaterial)
      markingGeometries.forEach((geometry) => geometry.dispose())
    }
    const carBody = new BoxGeometry(4.5, 0.7, 1.8)
    const carCabin = new BoxGeometry(2.15, 0.65, 1.6)
    const wheelParts = [-3.5, -1.0].flatMap((x) => [-0.88, 0.88].map((z) =>
      new BoxGeometry(0.7, 0.6, 0.22).translate(x, 0.35, z)))
    const carWheels = mergeGeometries(wheelParts)
    wheelParts.forEach((geometry) => geometry.dispose())
    if (!carWheels) throw new Error("Unable to build shared vehicle wheels")
    geometries.push(carBody, carCabin, carWheels)
    const createCar = (vehicle: RenderVehicle) => {
      const group = new Group()
      const isEmergency = vehicle.emergency || vehicle.visual_type === "emergency"
      const body = new Mesh(carBody, isEmergency ? emergencyMaterial : bodyMaterial)
      body.position.set(-2.25, 0.65, 0)
      const cabin = new Mesh(carCabin, glassMaterial)
      cabin.position.set(-2.5, 1.25, 0)
      group.add(body, cabin)
      if (isEmergency) {
        const red = new Mesh(new BoxGeometry(0.55, 0.18, 0.48), emergencyRed)
        const blue = new Mesh(new BoxGeometry(0.55, 0.18, 0.48), emergencyBlue)
        geometries.push(red.geometry, blue.geometry)
        red.position.set(-2, 1.65, -0.35)
        blue.position.set(-2, 1.65, 0.35)
        group.add(red, blue)
      }
      group.add(new Mesh(carWheels, tireMaterial))
      scene.add(group)
      group.scale.set(Math.max(vehicle.length, 1) / 4.5, 1, Math.max(vehicle.width, 0.5) / 1.8)
      return group
    }
    const cars = new Map<string, CarView>()
    const pedestrians = new Map<string, Mesh>()
    const pedestrianGeometry = new CylinderGeometry(0.25, 0.25, 1.5, 8)
    geometries.push(pedestrianGeometry)
    let lastFrame: RenderFrame | null = null
    const resize = () => {
      const width = Math.max(1, host.clientWidth), height = Math.max(1, host.clientHeight)
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    resize()
    resetView()
    let animationId = 0
    let wasFollowing = false
    let sampleStartedAt = performance.now()
    let previousRenderAt = sampleStartedAt
    let renderedFrames = 0
    let frameIntervals: number[] = []
    const animate = () => {
      const nextFrame = frameRef.current
      const now = performance.now()
      if (nextFrame && nextFrame !== lastFrame) {
        const closedLanes = new Set(nextFrame.visual.closed_lanes)
        for (const [laneId, material] of laneMaterials) {
          const restricted = nextFrame.visual.slow_lanes[laneId] < 1
          material.color.setHex(closedLanes.has(laneId) ? 0xb91c1c : restricted ? 0xb87916 : 0x414852)
        }
        const activeIds = new Set(nextFrame.vehicles.map((vehicle) => vehicle.id))
        for (const [id, car] of cars) if (!activeIds.has(id)) { scene.remove(car.group); cars.delete(id) }
        for (const vehicle of nextFrame.vehicles) {
          const car = cars.get(vehicle.id)
          if (car) {
            car.previous = { ...vehicle, x: car.group.position.x, y: -car.group.position.z, angle: 90 - car.group.rotation.y * 180 / Math.PI }
            car.target = vehicle
            car.updatedAt = now
          } else {
            cars.set(vehicle.id, { group: createCar(vehicle), previous: vehicle, target: vehicle, updatedAt: now })
          }
        }
        const pedestrianIds = new Set(nextFrame.pedestrians.map((pedestrian) => pedestrian.id))
        for (const [id, mesh] of pedestrians) if (!pedestrianIds.has(id)) { scene.remove(mesh); pedestrians.delete(id) }
        for (const pedestrian of nextFrame.pedestrians) {
          let mesh = pedestrians.get(pedestrian.id)
          if (!mesh) {
            mesh = new Mesh(pedestrianGeometry, pedestrianMaterial)
            scene.add(mesh)
            pedestrians.set(pedestrian.id, mesh)
          }
          mesh.position.set(pedestrian.x, 0.8, -pedestrian.y)
        }
        for (const [id, material] of lamps) {
          const state = nextFrame.traffic_lights[id]?.state ?? "r"
          const color = state.includes("G") || state.includes("g") ? 0x20c780 : state.includes("y") ? 0xffc444 : 0xe84b4b
          material.color.setHex(color)
          material.emissive.setHex(color)
        }
        lastFrame = nextFrame
      }
      for (const car of cars.values()) {
        const amount = Math.min(1, (now - car.updatedAt) / 100)
        car.group.position.set(car.previous.x + (car.target.x - car.previous.x) * amount, 0.05, -(car.previous.y + (car.target.y - car.previous.y) * amount))
        const angleDelta = ((car.target.angle - car.previous.angle + 540) % 360) - 180
        car.group.rotation.y = (90 - car.previous.angle - angleDelta * amount) * Math.PI / 180
      }
      if (followRef.current && cars.size) {
        const car = cars.values().next().value!
        const dx = car.group.position.x - controls.target.x
        const dz = car.group.position.z - controls.target.z
        controls.target.set(car.group.position.x, 0, car.group.position.z)
        camera.position.x += dx
        camera.position.z += dz
        if (!wasFollowing) camera.position.set(car.group.position.x + 20, 36, car.group.position.z + 30)
      }
      wasFollowing = followRef.current
      controls.update()
      renderer.render(scene, camera)
      renderedFrames += 1
      frameIntervals.push(now - previousRenderAt)
      previousRenderAt = now
      if (now - sampleStartedAt >= 2000 && performanceSampleRef.current) {
        const ordered = frameIntervals.sort((a, b) => a - b)
        performanceSampleRef.current({
          fps: Math.round(renderedFrames * 1000 / (now - sampleStartedAt)),
          p95FrameMs: Math.round(ordered[Math.min(ordered.length - 1, Math.floor(ordered.length * .95))] * 10) / 10,
          drawCalls: renderer.info.render.calls,
        })
        sampleStartedAt = now
        renderedFrames = 0
        frameIntervals = []
      }
      animationId = requestAnimationFrame(animate)
    }
    animate()
    return () => {
      cancelAnimationFrame(animationId)
      observer.disconnect()
      controls.dispose()
      for (const geometry of geometries) geometry.dispose()
      for (const material of materials) material.dispose()
      renderer.dispose()
      renderer.domElement.remove()
      resetViewRef.current = () => undefined
    }
  }, [network, onUnavailable])

  return (
    <div className="sf-three-shell">
      <div ref={hostRef} className="sf-three-host" />
      <div className="sf-three-foundation-label">
        <strong>{error || (network ? "Tagum · 5 connected junctions" : "Loading road network…")}</strong>
        <span>Drag to orbit · right-drag to pan · scroll to zoom</span>
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>
      </div>
      <div className="absolute right-3 top-3 flex gap-2">
        <Button variant="secondary" size="sm" aria-pressed={following} onClick={() => { followRef.current = !following; setFollowing(!following) }}><FocusIcon data-icon="inline-start" />{following ? "Following car" : "Follow car"}</Button>
        <Button variant="secondary" size="icon-sm" aria-label="Reset 3D camera" onClick={() => { followRef.current = false; setFollowing(false); resetViewRef.current() }}><RotateCcwIcon /></Button>
      </div>
    </div>
  )
}

import * as React from "react"
import {
  AmbientLight, BoxGeometry, BufferGeometry, Color, CylinderGeometry,
  DirectionalLight, Float32BufferAttribute, Group, Mesh, MeshStandardMaterial,
  PerspectiveCamera, Scene, SphereGeometry, SRGBColorSpace, WebGLRenderer,
} from "three"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"
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

export function SimulationScene3D({ frame, intersectionId, onUnavailable }: {
  frame: RenderFrame | null
  intersectionId?: string | null
  onUnavailable?: (message: string) => void
}) {
  const hostRef = React.useRef<HTMLDivElement | null>(null)
  const frameRef = React.useRef(frame)
  const resetViewRef = React.useRef<() => void>(() => undefined)
  const followRef = React.useRef(false)
  const [following, setFollowing] = React.useState(false)
  const [network, setNetwork] = React.useState<VisualNetwork | null>(null)
  const [error, setError] = React.useState("")
  React.useEffect(() => { frameRef.current = frame }, [frame])
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
    const glassMaterial = new MeshStandardMaterial({ color: 0x314c60, roughness: 0.45 })
    const tireMaterial = new MeshStandardMaterial({ color: 0x202327 })
    const geometries: BufferGeometry[] = []
    const materials = [roadMaterial, markingMaterial, poleMaterial, bodyMaterial, glassMaterial, tireMaterial]
    const addMesh = (geometry: BufferGeometry, material: MeshStandardMaterial, parent: Group | Scene = scene) => {
      geometries.push(geometry)
      const mesh = new Mesh(geometry, material)
      parent.add(mesh)
      return mesh
    }
    for (const road of network.roads) {
      for (const lane of road.lanes) {
        addMesh(ribbon(lane.shape, lane.width), roadMaterial)
        // Fine edge markings follow the actual polyline rather than a rectangular grid.
        const edge = lane.shape.map((point, index) => {
          const a = lane.shape[Math.max(0, index - 1)]
          const b = lane.shape[Math.min(lane.shape.length - 1, index + 1)]
          const heading = Math.atan2(b.y - a.y, b.x - a.x)
          return { x: point.x + Math.sin(heading) * (lane.width / 2 - 0.12), y: point.y - Math.cos(heading) * (lane.width / 2 - 0.12) }
        })
        addMesh(ribbon(edge, 0.1, 0.025), markingMaterial)
      }
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
      addMesh(ribbon(signal.stop_line, 0.3, 0.04), markingMaterial)
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
    const carBody = new BoxGeometry(4.5, 0.7, 1.8)
    const carCabin = new BoxGeometry(2.15, 0.65, 1.6)
    const carWheel = new BoxGeometry(0.7, 0.6, 0.22)
    geometries.push(carBody, carCabin, carWheel)
    const createCar = () => {
      const group = new Group()
      const body = new Mesh(carBody, bodyMaterial)
      body.position.y = 0.65
      const cabin = new Mesh(carCabin, glassMaterial)
      cabin.position.set(-0.25, 1.25, 0)
      group.add(body, cabin)
      for (const x of [-1.4, 1.4]) for (const z of [-0.88, 0.88]) {
        const wheel = new Mesh(carWheel, tireMaterial)
        wheel.position.set(x, 0.35, z)
        group.add(wheel)
      }
      scene.add(group)
      return group
    }
    const cars = new Map<string, CarView>()
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
    const animate = () => {
      const nextFrame = frameRef.current
      const now = performance.now()
      if (nextFrame && nextFrame !== lastFrame) {
        const activeIds = new Set(nextFrame.vehicles.map((vehicle) => vehicle.id))
        for (const [id, car] of cars) if (!activeIds.has(id)) { scene.remove(car.group); cars.delete(id) }
        for (const vehicle of nextFrame.vehicles) {
          const car = cars.get(vehicle.id)
          if (car) {
            car.previous = { ...vehicle, x: car.group.position.x, y: -car.group.position.z, angle: 90 - car.group.rotation.y * 180 / Math.PI }
            car.target = vehicle
            car.updatedAt = now
          } else {
            cars.set(vehicle.id, { group: createCar(), previous: vehicle, target: vehicle, updatedAt: now })
          }
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

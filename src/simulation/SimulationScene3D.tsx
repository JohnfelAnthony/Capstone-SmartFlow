import * as React from "react"
import {
  AmbientLight,
  Color,
  DirectionalLight,
  Fog,
  GridHelper,
  Group,
  HemisphereLight,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  PlaneGeometry,
  Scene,
  SRGBColorSpace,
  WebGLRenderer,
} from "three"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"
import { RotateCcwIcon } from "lucide-react"
import { SmartFlowAssetKit } from "@/simulation/three-assets"

const cameraHome = {
  position: [42, 46, 42] as const,
  target: [0, 0, 0] as const,
}

export function SimulationScene3D({
  onUnavailable,
}: {
  onUnavailable?: (message: string) => void
}) {
  const hostRef = React.useRef<HTMLDivElement | null>(null)
  const resetViewRef = React.useRef<() => void>(() => undefined)

  React.useEffect(() => {
    const host = hostRef.current
    if (!host) return

    let renderer: WebGLRenderer
    try {
      renderer = new WebGLRenderer({
        antialias: true,
        alpha: false,
        powerPreference: "high-performance",
      })
    } catch {
      onUnavailable?.("3D rendering is unavailable in this browser. Returned to the 2D view.")
      return
    }

    renderer.outputColorSpace = SRGBColorSpace
    renderer.shadowMap.enabled = true
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
    renderer.domElement.className = "sf-three-canvas"
    renderer.domElement.setAttribute("aria-label", "3D simulation renderer")
    host.appendChild(renderer.domElement)

    const scene = new Scene()
    scene.background = new Color(0x9ccf8d)
    scene.fog = new Fog(0x9ccf8d, 85, 190)

    const camera = new PerspectiveCamera(36, 1, 0.1, 500)
    camera.position.set(...cameraHome.position)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.minDistance = 18
    controls.maxDistance = 110
    controls.minPolarAngle = Math.PI * 0.16
    controls.maxPolarAngle = Math.PI * 0.46
    controls.screenSpacePanning = false
    controls.target.set(...cameraHome.target)

    const worldRoot = new Group()
    worldRoot.name = "smartflow-world"
    scene.add(worldRoot)
    const assetKit = new SmartFlowAssetKit()

    const ground = new Mesh(
      new PlaneGeometry(180, 180),
      new MeshStandardMaterial({ color: 0x78ad6e, roughness: 0.96 })
    )
    ground.name = "foundation-ground"
    ground.rotation.x = -Math.PI / 2
    ground.position.y = -0.03
    ground.receiveShadow = true
    worldRoot.add(ground)

    const grid = new GridHelper(140, 28, 0x427a49, 0x6da36e)
    grid.name = "foundation-grid"
    grid.position.y = 0.01
    worldRoot.add(grid)

    const assetShowcase = assetKit.createAssetShowcase()
    assetShowcase.position.set(0, 0.04, 0)
    worldRoot.add(assetShowcase)

    scene.add(new AmbientLight(0xffffff, 0.42))
    scene.add(new HemisphereLight(0xdff4ff, 0x315c32, 1.15))

    const sun = new DirectionalLight(0xfff5db, 1.7)
    sun.position.set(48, 72, 36)
    sun.castShadow = true
    sun.shadow.mapSize.set(1024, 1024)
    sun.shadow.camera.left = -70
    sun.shadow.camera.right = 70
    sun.shadow.camera.top = 70
    sun.shadow.camera.bottom = -70
    scene.add(sun)

    const resetView = () => {
      camera.position.set(...cameraHome.position)
      controls.target.set(...cameraHome.target)
      controls.update()
    }
    resetViewRef.current = resetView
    resetView()

    const resizeRenderer = () => {
      const width = Math.max(host.clientWidth, 320)
      const height = Math.max(host.clientHeight, 280)
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }

    const resizeObserver = new ResizeObserver(resizeRenderer)
    resizeObserver.observe(host)
    resizeRenderer()

    let animationFrameId = 0
    const render = () => {
      controls.update()
      renderer.render(scene, camera)
      animationFrameId = window.requestAnimationFrame(render)
    }
    render()

    return () => {
      window.cancelAnimationFrame(animationFrameId)
      resizeObserver.disconnect()
      controls.dispose()
      assetKit.dispose()
      ground.geometry.dispose()
      ;(ground.material as MeshStandardMaterial).dispose()
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement.remove()
      resetViewRef.current = () => undefined
    }
  }, [onUnavailable])

  return (
    <div className="sf-three-shell">
      <div ref={hostRef} className="sf-three-host" />
      <div className="sf-three-foundation-label">
        <span>3D renderer</span>
        <strong>Scene foundation ready</strong>
      </div>
      <button
        className="sf-three-reset"
        type="button"
        aria-label="Reset 3D camera"
        title="Reset 3D camera"
        onClick={() => resetViewRef.current()}
      >
        <RotateCcwIcon />
      </button>
    </div>
  )
}

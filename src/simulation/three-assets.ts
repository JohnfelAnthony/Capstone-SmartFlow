import {
  BoxGeometry,
  CylinderGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  SphereGeometry,
  type BufferGeometry,
  type Material,
  type MeshStandardMaterialParameters,
  type Object3D,
} from "three"

export type VehicleAssetType = "car" | "bus" | "truck" | "ambulance" | "motorcycle"
export type PedestrianAssetPose = "standing" | "walking"
export type SignalAssetType = "vehicle" | "pedestrian"

type VehicleStyle = {
  bodyColor: number
  accentColor?: number
  cabinColor: number
  width: number
  height: number
  length: number
  cabinLength: number
  cabinOffsetZ: number
  wheelRadius: number
  wheelWidth: number
}

type BuildingOptions = {
  width?: number
  depth?: number
  floors?: number
  accentColor?: number
}

const palette = {
  smartGreen: 0x32a852,
  deepGreen: 0x1f6b39,
  asphalt: 0x182132,
  tire: 0x10141d,
  glass: 0x1f4b66,
  white: 0xf8faf7,
  warmWhite: 0xeee7d9,
  concrete: 0xaca79d,
  yellow: 0xf7bd24,
  red: 0xef4444,
  blue: 0x2563eb,
  amber: 0xf59e0b,
  signalHousing: 0x202734,
  signalPole: 0x151a24,
  skin: 0xe2b388,
  denim: 0x1f3d56,
  shirt: 0x2f8f55,
}

const vehicleStyles: Record<VehicleAssetType, VehicleStyle> = {
  car: {
    bodyColor: palette.smartGreen,
    accentColor: palette.deepGreen,
    cabinColor: palette.glass,
    width: 1.35,
    height: 0.48,
    length: 2.75,
    cabinLength: 1.05,
    cabinOffsetZ: -0.1,
    wheelRadius: 0.19,
    wheelWidth: 0.12,
  },
  bus: {
    bodyColor: palette.white,
    accentColor: palette.smartGreen,
    cabinColor: palette.glass,
    width: 1.55,
    height: 0.82,
    length: 4.45,
    cabinLength: 2.2,
    cabinOffsetZ: -0.2,
    wheelRadius: 0.22,
    wheelWidth: 0.13,
  },
  truck: {
    bodyColor: palette.white,
    accentColor: 0x24486d,
    cabinColor: palette.glass,
    width: 1.5,
    height: 0.78,
    length: 3.75,
    cabinLength: 1,
    cabinOffsetZ: 1.05,
    wheelRadius: 0.22,
    wheelWidth: 0.14,
  },
  ambulance: {
    bodyColor: palette.white,
    accentColor: palette.red,
    cabinColor: palette.glass,
    width: 1.48,
    height: 0.82,
    length: 3.45,
    cabinLength: 1.05,
    cabinOffsetZ: 0.9,
    wheelRadius: 0.2,
    wheelWidth: 0.13,
  },
  motorcycle: {
    bodyColor: palette.deepGreen,
    accentColor: palette.asphalt,
    cabinColor: palette.glass,
    width: 0.58,
    height: 0.48,
    length: 1.75,
    cabinLength: 0.52,
    cabinOffsetZ: -0.05,
    wheelRadius: 0.24,
    wheelWidth: 0.08,
  },
}

function setShadow(object: Object3D, receive = false) {
  object.traverse((child) => {
    if (!(child instanceof Mesh)) return
    child.castShadow = true
    child.receiveShadow = receive
  })
}

export class SmartFlowAssetKit {
  private readonly materials = new Map<string, MeshStandardMaterial>()
  private readonly geometries = new Map<string, BufferGeometry>()

  material(name: string, color: number, options: MeshStandardMaterialParameters = {}) {
    const key = `${name}:${color}:${JSON.stringify(options)}`
    const existing = this.materials.get(key)
    if (existing) return existing
    const material = new MeshStandardMaterial({ color, roughness: 0.62, metalness: 0.04, ...options })
    this.materials.set(key, material)
    return material
  }

  box(name: string, width: number, height: number, depth: number) {
    const key = `${name}:${width}:${height}:${depth}`
    const existing = this.geometries.get(key)
    if (existing) return existing
    const geometry = new BoxGeometry(width, height, depth)
    this.geometries.set(key, geometry)
    return geometry
  }

  cylinder(name: string, radius: number, depth: number, segments = 12) {
    const key = `${name}:${radius}:${depth}:${segments}`
    const existing = this.geometries.get(key)
    if (existing) return existing
    const geometry = new CylinderGeometry(radius, radius, depth, segments)
    this.geometries.set(key, geometry)
    return geometry
  }

  sphere(name: string, radius: number, segments = 12) {
    const key = `${name}:${radius}:${segments}`
    const existing = this.geometries.get(key)
    if (existing) return existing
    const geometry = new SphereGeometry(radius, segments, segments)
    this.geometries.set(key, geometry)
    return geometry
  }

  createVehicle(type: VehicleAssetType) {
    if (type === "motorcycle") return this.createMotorcycle()
    const style = vehicleStyles[type]
    const group = new Group()
    group.name = `asset-vehicle-${type}`

    const body = new Mesh(
      this.box(`${type}-body`, style.width, style.height, style.length),
      this.material(`${type}-body`, style.bodyColor)
    )
    body.position.y = style.height / 2 + 0.18
    group.add(body)

    const cabin = new Mesh(
      this.box(`${type}-cabin`, style.width * 0.72, style.height * 0.55, style.cabinLength),
      this.material(`${type}-cabin`, style.cabinColor, { transparent: true, opacity: 0.86, roughness: 0.2 })
    )
    cabin.position.set(0, style.height + 0.25, style.cabinOffsetZ)
    group.add(cabin)

    if (style.accentColor) {
      const stripe = new Mesh(
        this.box(`${type}-stripe`, style.width + 0.02, 0.08, style.length * 0.78),
        this.material(`${type}-stripe`, style.accentColor)
      )
      stripe.position.set(0, style.height * 0.62, 0)
      group.add(stripe)
    }

    if (type === "bus") this.addBusWindows(group, style)
    if (type === "ambulance") this.addEmergencyDetails(group, style)

    this.addWheels(group, style)
    setShadow(group)
    return group
  }

  createPedestrian(pose: PedestrianAssetPose = "standing") {
    const group = new Group()
    group.name = `asset-pedestrian-${pose}`
    const torso = new Mesh(this.box("pedestrian-torso", 0.28, 0.54, 0.18), this.material("pedestrian-shirt", palette.shirt))
    torso.position.y = 0.62
    group.add(torso)

    const head = new Mesh(this.sphere("pedestrian-head", 0.13, 12), this.material("pedestrian-skin", palette.skin))
    head.position.y = 1.0
    group.add(head)

    const hair = new Mesh(this.box("pedestrian-hair", 0.22, 0.1, 0.16), this.material("pedestrian-hair", palette.tire))
    hair.position.y = 1.11
    group.add(hair)

    const legMaterial = this.material("pedestrian-denim", palette.denim)
    const leftLeg = new Mesh(this.box("pedestrian-leg", 0.08, 0.4, 0.08), legMaterial)
    const rightLeg = new Mesh(this.box("pedestrian-leg", 0.08, 0.4, 0.08), legMaterial)
    leftLeg.position.set(-0.07, 0.25, pose === "walking" ? -0.08 : 0)
    rightLeg.position.set(0.07, 0.25, pose === "walking" ? 0.08 : 0)
    leftLeg.rotation.x = pose === "walking" ? -0.25 : 0
    rightLeg.rotation.x = pose === "walking" ? 0.25 : 0
    group.add(leftLeg, rightLeg)

    const shoe = this.material("pedestrian-shoe", palette.tire)
    for (const x of [-0.07, 0.07]) {
      const foot = new Mesh(this.box("pedestrian-foot", 0.1, 0.05, 0.18), shoe)
      foot.position.set(x, 0.03, pose === "walking" && x < 0 ? -0.16 : 0.08)
      group.add(foot)
    }

    setShadow(group)
    return group
  }

  createTrafficSignal(type: SignalAssetType = "vehicle") {
    const group = new Group()
    group.name = `asset-signal-${type}`
    this.addSignalPole(group)
    const housingHeight = type === "vehicle" ? 0.86 : 0.68
    const housing = new Mesh(
      this.box(`${type}-signal-housing`, 0.36, housingHeight, 0.22),
      this.material("signal-housing", palette.signalHousing)
    )
    housing.position.set(0, 1.72, 0.32)
    group.add(housing)

    if (type === "vehicle") {
      const lamps = [
        { y: 1.96, color: palette.red, name: "red" },
        { y: 1.72, color: palette.amber, name: "amber" },
        { y: 1.48, color: palette.smartGreen, name: "green" },
      ]
      lamps.forEach((lamp) => {
        const mesh = new Mesh(
          this.sphere(`signal-lamp-${lamp.name}`, 0.075, 12),
          this.material(`signal-lamp-${lamp.name}`, lamp.color, { emissive: lamp.color, emissiveIntensity: 0.42 })
        )
        mesh.position.set(0, lamp.y, 0.45)
        group.add(mesh)
      })
    } else {
      const stop = new Mesh(
        this.box("ped-signal-stop", 0.12, 0.18, 0.04),
        this.material("ped-signal-red", palette.red, { emissive: palette.red, emissiveIntensity: 0.35 })
      )
      const walk = new Mesh(
        this.box("ped-signal-walk", 0.14, 0.22, 0.04),
        this.material("ped-signal-green", palette.smartGreen, { emissive: palette.smartGreen, emissiveIntensity: 0.35 })
      )
      stop.position.set(0, 1.82, 0.45)
      walk.position.set(0, 1.58, 0.45)
      group.add(stop, walk)
    }

    setShadow(group)
    return group
  }

  createStreetlight() {
    const group = new Group()
    group.name = "asset-streetlight"
    const pole = new Mesh(this.cylinder("streetlight-pole", 0.045, 2.2, 10), this.material("streetlight-metal", palette.signalPole))
    pole.position.y = 1.1
    group.add(pole)

    const arm = new Mesh(this.box("streetlight-arm", 0.72, 0.06, 0.08), this.material("streetlight-metal", palette.signalPole))
    arm.position.set(0.32, 2.16, 0)
    group.add(arm)

    const lamp = new Mesh(
      this.box("streetlight-lamp", 0.45, 0.08, 0.28),
      this.material("streetlight-lamp", 0xf7f3d4, { emissive: 0xf1d36d, emissiveIntensity: 0.28 })
    )
    lamp.position.set(0.68, 2.08, 0)
    group.add(lamp)

    setShadow(group)
    return group
  }

  createRoadBarrier() {
    const group = new Group()
    group.name = "asset-road-barrier"
    const base = new Mesh(this.box("barrier-base", 1.9, 0.48, 0.34), this.material("barrier-concrete", palette.concrete))
    base.position.y = 0.24
    group.add(base)

    const stripe = new Mesh(this.box("barrier-stripe", 1.94, 0.12, 0.035), this.material("barrier-yellow", palette.yellow))
    stripe.position.set(0, 0.34, 0.19)
    group.add(stripe)

    setShadow(group, true)
    return group
  }

  createBuilding(options: BuildingOptions = {}) {
    const width = options.width ?? 3.6
    const depth = options.depth ?? 2.4
    const floors = options.floors ?? 2
    const height = floors * 0.86
    const accentColor = options.accentColor ?? palette.smartGreen
    const group = new Group()
    group.name = "asset-building"

    const body = new Mesh(this.box("building-body", width, height, depth), this.material("building-body", palette.warmWhite))
    body.position.y = height / 2
    group.add(body)

    const roof = new Mesh(this.box("building-roof", width + 0.18, 0.16, depth + 0.18), this.material("building-roof", palette.asphalt))
    roof.position.y = height + 0.08
    group.add(roof)

    const trim = new Mesh(this.box("building-trim", width + 0.08, 0.12, depth + 0.08), this.material("building-trim", accentColor))
    trim.position.y = height * 0.55
    group.add(trim)

    const windowMaterial = this.material("building-window", palette.glass, { transparent: true, opacity: 0.88, roughness: 0.18 })
    for (let floor = 0; floor < Math.max(1, floors); floor += 1) {
      const y = 0.44 + floor * 0.74
      for (const x of [-width * 0.28, 0, width * 0.28]) {
        const window = new Mesh(this.box("building-window", 0.38, 0.28, 0.04), windowMaterial)
        window.position.set(x, y, depth / 2 + 0.03)
        group.add(window)
      }
    }

    setShadow(group, true)
    return group
  }

  createAssetShowcase() {
    const group = new Group()
    group.name = "smartflow-asset-showcase"
    const placements: Array<[Object3D, number, number, number]> = [
      [this.createVehicle("car"), -7.8, 0, -2.4],
      [this.createVehicle("bus"), -4.4, 0, -2.4],
      [this.createVehicle("truck"), -0.4, 0, -2.4],
      [this.createVehicle("ambulance"), 3.4, 0, -2.4],
      [this.createVehicle("motorcycle"), 6.6, 0, -2.4],
      [this.createPedestrian("standing"), -7.4, 0, 1.1],
      [this.createPedestrian("walking"), -6.4, 0, 1.1],
      [this.createTrafficSignal("vehicle"), -3.7, 0, 1.0],
      [this.createTrafficSignal("pedestrian"), -2.6, 0, 1.0],
      [this.createRoadBarrier(), -0.6, 0, 1.2],
      [this.createStreetlight(), 1.6, 0, 1.0],
      [this.createBuilding({ width: 2.9, depth: 2.2, floors: 2 }), 4.4, 0, 1.4],
      [this.createBuilding({ width: 3.4, depth: 2.1, floors: 2, accentColor: palette.blue }), 7.8, 0, 1.4],
    ]

    placements.forEach(([object, x, y, z]) => {
      object.position.set(x, y, z)
      group.add(object)
    })
    return group
  }

  dispose() {
    this.geometries.forEach((geometry) => geometry.dispose())
    this.materials.forEach((material: Material) => material.dispose())
    this.geometries.clear()
    this.materials.clear()
  }

  private addWheels(group: Group, style: VehicleStyle) {
    const wheelMaterial = this.material("vehicle-wheel", palette.tire)
    const zOffset = style.length * 0.34
    const xOffset = style.width * 0.52
    for (const x of [-xOffset, xOffset]) {
      for (const z of [-zOffset, zOffset]) {
        const wheel = new Mesh(this.cylinder("vehicle-wheel", style.wheelRadius, style.wheelWidth, 14), wheelMaterial)
        wheel.rotation.z = Math.PI / 2
        wheel.position.set(x, style.wheelRadius + 0.03, z)
        group.add(wheel)
      }
    }
  }

  private addBusWindows(group: Group, style: VehicleStyle) {
    const windowMaterial = this.material("bus-window", palette.glass, { transparent: true, opacity: 0.86, roughness: 0.18 })
    for (const z of [-1.35, -0.65, 0.05, 0.75, 1.45]) {
      const window = new Mesh(this.box("bus-side-window", 0.04, 0.36, 0.42), windowMaterial)
      window.position.set(style.width / 2 + 0.03, 0.78, z)
      group.add(window)
    }
  }

  private addEmergencyDetails(group: Group, style: VehicleStyle) {
    const stripe = new Mesh(this.box("ambulance-red-stripe", style.width + 0.03, 0.09, style.length * 0.72), this.material("ambulance-red", palette.red))
    stripe.position.set(0, 0.58, 0)
    group.add(stripe)

    const redLight = new Mesh(this.box("ambulance-light", 0.2, 0.08, 0.14), this.material("ambulance-light-red", palette.red, { emissive: palette.red, emissiveIntensity: 0.45 }))
    const blueLight = new Mesh(this.box("ambulance-light", 0.2, 0.08, 0.14), this.material("ambulance-light-blue", palette.blue, { emissive: palette.blue, emissiveIntensity: 0.45 }))
    redLight.position.set(-0.18, style.height + 0.58, 0.05)
    blueLight.position.set(0.18, style.height + 0.58, 0.05)
    group.add(redLight, blueLight)
  }

  private createMotorcycle() {
    const group = new Group()
    group.name = "asset-vehicle-motorcycle"
    const style = vehicleStyles.motorcycle
    const frameMaterial = this.material("motorcycle-frame", style.bodyColor)
    const darkMaterial = this.material("motorcycle-dark", palette.tire)

    const body = new Mesh(this.box("motorcycle-body", 0.38, 0.26, 0.92), frameMaterial)
    body.position.y = 0.52
    group.add(body)

    const seat = new Mesh(this.box("motorcycle-seat", 0.34, 0.1, 0.52), darkMaterial)
    seat.position.set(0, 0.72, -0.1)
    group.add(seat)

    const fork = new Mesh(this.box("motorcycle-fork", 0.08, 0.52, 0.08), darkMaterial)
    fork.position.set(0, 0.48, 0.62)
    fork.rotation.x = -0.35
    group.add(fork)

    for (const z of [-0.62, 0.72]) {
      const wheel = new Mesh(this.cylinder("motorcycle-wheel", style.wheelRadius, style.wheelWidth, 16), darkMaterial)
      wheel.rotation.z = Math.PI / 2
      wheel.position.set(0, style.wheelRadius, z)
      group.add(wheel)
    }

    setShadow(group)
    return group
  }

  private addSignalPole(group: Group) {
    const poleMaterial = this.material("signal-pole", palette.signalPole)
    const base = new Mesh(this.box("signal-base", 0.48, 0.16, 0.48), poleMaterial)
    base.position.y = 0.08
    group.add(base)

    const pole = new Mesh(this.cylinder("signal-pole", 0.045, 1.46, 10), poleMaterial)
    pole.position.y = 0.88
    group.add(pole)
  }
}

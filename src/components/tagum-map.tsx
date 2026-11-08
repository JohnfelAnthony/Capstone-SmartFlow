import * as React from "react"
import L from "leaflet"
import "leaflet/dist/leaflet.css"

import { Button } from "@/components/ui/button"
import { STUDY_SITES } from "@/lib/study-sites"

const TAGUM_VIEW = { center: [7.45, 125.803] as L.LatLngTuple, zoom: 14 }
const SITE_ZOOM = 18
const BASEMAPS = {
  default: {
    label: "Map", url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' },
  },
  satellite: {
    label: "Satellite", url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    // Imagery past zoom 18 is patchy outside big cities, so scale up the last native level instead of showing blanks.
    options: { maxZoom: 19, maxNativeZoom: 18, attribution: "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community" },
  },
}
type Basemap = keyof typeof BASEMAPS
// One zoom-15 tile over Tagum, used as the preview picture on the layer button.
const PREVIEW_TILE = { z: "15", x: "27834", y: "15703" }
const previewUrl = (key: Basemap) => BASEMAPS[key].url.replace(/\{(z|x|y)\}/g, (_, part: "z" | "x" | "y") => PREVIEW_TILE[part])

/** OpenStreetMap of Tagum City; each study site is a marker that zooms in when clicked. */
export function TagumMap() {
  const host = React.useRef<HTMLDivElement | null>(null)
  const map = React.useRef<L.Map | null>(null)
  const [basemap, setBasemap] = React.useState<Basemap>("default")
  const other: Basemap = basemap === "default" ? "satellite" : "default"
  React.useEffect(() => {
    if (!host.current) return
    const instance = L.map(host.current).setView(TAGUM_VIEW.center, TAGUM_VIEW.zoom)
    for (const site of Object.values(STUDY_SITES)) {
      L.circleMarker([site.lat, site.lon], { radius: 11, color: "#ffffff", weight: 3, fillColor: "#16a34a", fillOpacity: 1 })
        .bindTooltip(site.label, { permanent: true, direction: "top", offset: [0, -12] })
        .on("click", () => instance.flyTo([site.lat, site.lon], SITE_ZOOM))
        .addTo(instance)
    }
    map.current = instance
    return () => { instance.remove(); map.current = null }
  }, [])
  React.useEffect(() => {
    if (!map.current) return
    const layer = L.tileLayer(BASEMAPS[basemap].url, BASEMAPS[basemap].options).addTo(map.current)
    return () => { layer.remove() }
  }, [basemap])
  return <div className="relative">
    <div ref={host} role="region" aria-label="Map of Tagum City with the two study sites" className="h-[min(72vh,680px)] w-full rounded-xl border" />
    <div className="absolute top-3 right-3 z-[1000] flex items-start gap-2">
      {Object.values(STUDY_SITES).map((site) =>
        <Button key={site.label} size="sm" variant="secondary" onClick={() => map.current?.flyTo([site.lat, site.lon], SITE_ZOOM)}>{site.label}</Button>)}
      <button type="button" onClick={() => setBasemap(other)} aria-label={`Show the ${BASEMAPS[other].label.toLowerCase()} view`}
        className="relative size-16 overflow-hidden rounded-lg border-2 border-white bg-muted bg-cover bg-center shadow-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
        style={{ backgroundImage: `url(${previewUrl(other)})` }}>
        <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent pb-1 pt-3 text-center text-xs font-medium text-white">{BASEMAPS[other].label}</span>
      </button>
    </div>
  </div>
}

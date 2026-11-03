import * as React from "react"
import L from "leaflet"
import "leaflet/dist/leaflet.css"

import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { STUDY_SITES } from "@/lib/study-sites"

const TAGUM_VIEW = { center: [7.45, 125.803] as L.LatLngTuple, zoom: 14 }
const SITE_ZOOM = 18
const BASEMAPS = {
  default: {
    label: "Default", url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' },
  },
  satellite: {
    label: "Satellite", url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    // Imagery past zoom 18 is patchy outside big cities, so scale up the last native level instead of showing blanks.
    options: { maxZoom: 19, maxNativeZoom: 18, attribution: "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community" },
  },
}
type Basemap = keyof typeof BASEMAPS

/** OpenStreetMap of Tagum City; each study site is a marker that zooms in when clicked. */
export function TagumMap() {
  const host = React.useRef<HTMLDivElement | null>(null)
  const map = React.useRef<L.Map | null>(null)
  const [basemap, setBasemap] = React.useState<Basemap>("default")
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
    <div className="absolute top-3 right-3 z-[1000] flex flex-wrap justify-end gap-2">
      <ToggleGroup value={[basemap]} onValueChange={(values) => values[0] && setBasemap(values[0] as Basemap)} variant="outline" size="sm" className="rounded-lg bg-background" aria-label="Map style">
        {(Object.keys(BASEMAPS) as Basemap[]).map((key) => <ToggleGroupItem key={key} value={key} className="aria-pressed:bg-primary aria-pressed:text-primary-foreground">{BASEMAPS[key].label}</ToggleGroupItem>)}
      </ToggleGroup>
      {Object.values(STUDY_SITES).map((site) =>
        <Button key={site.label} size="sm" variant="secondary" onClick={() => map.current?.flyTo([site.lat, site.lon], SITE_ZOOM)}>{site.label}</Button>)}
      <Button size="sm" variant="secondary" onClick={() => map.current?.flyTo(TAGUM_VIEW.center, TAGUM_VIEW.zoom)}>All of Tagum</Button>
    </div>
  </div>
}

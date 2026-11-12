import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"
import type { PeakCountsSummary } from "@/api/native-scenario"
import { PeakTrafficCard } from "@/components/peak-traffic"
import { PEAK_SCHEMA, savedPeakSha, trafficSource } from "@/lib/peak-traffic"

const siteB: PeakCountsSummary = {
  label: "Demand based on video counts with assumed routes", traffic_label: "Peak traffic",
  video: { file: "IMG_2516.MOV", seconds: 968, take_id: "t", source_sha256: "s" }, method: "automatic_detector", reviewed: false,
  count_direction: "arriving", counted_vehicles: 650, assumed_vehicles: 50, vehicles_per_hour: 2603.3, entering: { "5": 217, "10": 434, "15": 651 },
  by_type: { car: 404, motorcycle: 152, tricycle: 34, bus: 10, truck: 100 },
  roads: [{ approach: "south", name: "Dao Street", arriving: 50, leaving: 210, arriving_assumed: true, leaving_assumed: true },
    { approach: "west", name: "Davao-Agusan National Highway", arriving: 401, leaving: 150, arriving_assumed: false, leaving_assumed: true }],
  pedestrians: null, notes: ["Vehicle types are automatic detector guesses that nobody has reviewed; the detector has no tricycle class."], dataset_sha256: "abc",
}

describe("peak-traffic video counts", () => {
  it("tells peak, preset and earlier imported demand apart", () => {
    expect(trafficSource({ demand_windows: [{}], demand_source: { kind: "field_counts", datasets: [{ schema: PEAK_SCHEMA, sha256: "abc" }] } })).toBe("peak")
    expect(trafficSource({ demand_windows: [{}], demand_source: { kind: "field_counts", datasets: [{ schema: "field_observer_counts" }] } })).toBe("imported")
    expect(trafficSource({ demand_windows: [], demand_source: { kind: "synthetic" } })).toBe("preset")
    expect(savedPeakSha({ demand_source: { kind: "field_counts", datasets: [{ schema: PEAK_SCHEMA, sha256: "abc" }] } })).toBe("abc")
  })

  it("shows the run-length numbers, counted against assumed roads, the warnings and no counted pedestrians", () => {
    const html = renderToStaticMarkup(createElement(PeakTrafficCard, { summary: siteB }))
    expect(html).toContain("Video counts, assumed routes")
    expect(html).toContain("Automatic detector count, not reviewed of IMG_2516.MOV · 16 min 8 s · 650 vehicles counted, 50 assumed")
    for (const chip of ["5 min ≈ 217", "10 min ≈ 434", "15 min ≈ 651"]) expect(html).toContain(chip)
    expect(html).toContain("<strong>401</strong>")
    expect(html).toContain("≈ 50")
    expect(html).toContain("Pedestrians: not counted at this site.")
    expect(html).toContain("detector guesses")
    expect(html).not.toContain("changed after this scenario was saved")
    const stale = renderToStaticMarkup(createElement(PeakTrafficCard, { summary: siteB, stale: true, onRefresh: () => undefined }))
    expect(stale).toContain("changed after this scenario was saved")
    expect(stale).toMatch(/<button[^>]*>Use the current count<\/button>/)
    expect(stale).not.toContain("Choose Peak traffic again")
  })
})

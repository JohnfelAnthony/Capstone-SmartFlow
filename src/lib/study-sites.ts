// The two study sites by network id. Photos are the team's enhanced images (the Citi Hardware corner is Site B).
export const STUDY_SITES: Record<string, { label: string; photo: string; lat: number; lon: number }> = {
  tagum_site_a: { label: "Site A", photo: "/assets/junctions/tagum_site_a.jpg", lat: 7.46174, lon: 125.80262 },
  tagum_site_b: { label: "Site B", photo: "/assets/junctions/tagum_site_b.jpg", lat: 7.43826, lon: 125.80256 },
}

export const sitePhoto = (networkId: string | null | undefined) => (networkId ? STUDY_SITES[networkId]?.photo : undefined)

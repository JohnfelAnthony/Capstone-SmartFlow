export type VehicleMixPreset = { label: string; mix: Record<string, number> }

function proportions(mix: Record<string, number>) {
  const total = Object.values(mix).reduce((sum, weight) => sum + weight, 0)
  return Object.fromEntries(Object.entries(mix).filter(([, weight]) => weight > 0).map(([type, weight]) => [type, weight / total]))
}

/** Preset key whose normalised proportions equal the mix's within 1e-6, or null for a custom mix. */
export function matchingMixPreset(mix: Record<string, number> | undefined, presets: Record<string, VehicleMixPreset>): string | null {
  if (!mix || !Object.keys(mix).length) return null
  const shares = proportions(mix)
  for (const [key, preset] of Object.entries(presets)) {
    const target = proportions(preset.mix)
    const types = new Set([...Object.keys(shares), ...Object.keys(target)])
    if ([...types].every((type) => Math.abs((shares[type] ?? 0) - (target[type] ?? 0)) < 1e-6)) return key
  }
  return null
}

export function mixShares(mix: Record<string, number>): Array<{ type: string; percent: number }> {
  return Object.entries(proportions(mix)).map(([type, share]) => ({ type, percent: share * 100 })).sort((a, b) => b.percent - a.percent)
}

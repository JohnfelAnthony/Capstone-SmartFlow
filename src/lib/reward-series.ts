export type RewardPoint = { algorithm: string; episode: number; reward: number }

/** One row per episode, one column per algorithm, so each algorithm draws its own line. */
export function rewardSeries(points: RewardPoint[]): { data: Array<Record<string, number>>; algorithms: string[] } {
  const algorithms: string[] = []
  const rows = new Map<number, Record<string, number>>()
  for (const { algorithm, episode, reward } of points) {
    if (!algorithms.includes(algorithm)) algorithms.push(algorithm)
    const row = rows.get(episode) ?? { episode }
    row[algorithm] = reward
    rows.set(episode, row)
  }
  return { data: [...rows.values()].sort((a, b) => a.episode - b.episode), algorithms }
}

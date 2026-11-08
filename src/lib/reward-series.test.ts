import { describe, expect, it } from "vitest"
import { rewardSeries } from "./reward-series"

describe("rewardSeries", () => {
  it("makes one column per algorithm, ordered by episode", () => {
    const series = rewardSeries([
      { algorithm: "QL", episode: 1, reward: -5 },
      { algorithm: "PPO", episode: 1, reward: -3 },
      { algorithm: "QL", episode: 2, reward: -4 },
    ])
    expect(series.algorithms).toEqual(["QL", "PPO"])
    expect(series.data).toEqual([{ episode: 1, QL: -5, PPO: -3 }, { episode: 2, QL: -4 }])
  })
  it("is empty without points", () => {
    expect(rewardSeries([])).toEqual({ data: [], algorithms: [] })
  })
})

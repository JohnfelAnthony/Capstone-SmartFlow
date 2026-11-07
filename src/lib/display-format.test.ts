import { describe, expect, it } from "vitest"
import { EMPTY_VALUE, formatServerDate, parseServerTimestamp } from "./display-format"

describe("parseServerTimestamp", () => {
  it("reads SQLite times without a zone as UTC", () => {
    expect(parseServerTimestamp("2026-11-06 10:04:00")?.toISOString()).toBe("2026-11-06T10:04:00.000Z")
  })
  it("keeps an explicit zone", () => {
    expect(parseServerTimestamp("2026-06-03T02:45:00+00:00")?.toISOString()).toBe("2026-06-03T02:45:00.000Z")
  })
  it("returns null for missing or invalid values", () => {
    expect(parseServerTimestamp("not a date")).toBeNull()
    expect(parseServerTimestamp(null)).toBeNull()
  })
})

describe("formatServerDate", () => {
  const now = new Date("2026-11-08T00:00:00Z")
  it("omits the year in the current year and shows it otherwise", () => {
    expect(formatServerDate("2026-06-03T02:45:00+00:00", now)).not.toMatch(/2026/)
    expect(formatServerDate("2025-06-03T02:45:00+00:00", now)).toMatch(/2025/)
  })
  it("says Never when there is no date", () => {
    expect(formatServerDate(null)).toBe("Never")
  })
  it("uses the long dash for empty values", () => {
    expect(EMPTY_VALUE).toBe("—")
  })
})

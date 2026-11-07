export const EMPTY_VALUE = "—"

const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i

// SQLite stores UTC as "YYYY-MM-DD HH:MM:SS" without a zone.
export function parseServerTimestamp(value: string | null | undefined): Date | null {
  if (!value) return null
  const iso = value.replace(" ", "T")
  const date = new Date(HAS_ZONE.test(iso) ? iso : `${iso}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatServerDate(value: string | null | undefined, now = new Date()): string {
  if (!value) return "Never"
  const date = parseServerTimestamp(value)
  if (!date) return value
  const options: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }
  if (date.getFullYear() !== now.getFullYear()) options.year = "numeric"
  return new Intl.DateTimeFormat("en", options).format(date)
}

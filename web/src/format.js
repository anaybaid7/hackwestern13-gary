// Small helpers for turning the state into words.

/** "2026-11-21T15:25:00Z" -> "10:25 AM", in the reader's own timezone. */
export function clock(ts) {
  const when = new Date(ts)
  if (Number.isNaN(when.getTime())) return ''
  return when.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

/** A local calendar day as a key: "2026-11-21". */
export function dayKey(value) {
  const when = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(when.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`
}

/** "2026-11-21" -> "Sat 21 Nov". */
export function dayName(day) {
  const [year, month, date] = String(day).split('-').map(Number)
  if (!year || !month || !date) return String(day)
  return new Date(year, month - 1, date).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
}

export function isToday(ts, now) {
  return dayKey(ts) !== '' && dayKey(ts) === dayKey(now)
}

/** 1 -> "1st", 2 -> "2nd", 5 -> "5th". */
export function ordinal(n) {
  const tens = n % 100
  if (tens >= 11 && tens <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

export function plural(n, one, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`
}

/** "https://london.ca/parks-london" -> "london.ca". */
export function host(url) {
  try {
    return new URL(url).host.replace(/^www\./, '')
  } catch {
    return String(url)
  }
}

/** ["a bench", "a dog", "a kite"] -> "a bench, a dog and a kite". */
export function list(items) {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

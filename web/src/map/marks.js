// What both maps (flat and 3D) put on a place: the same pins, the same
// words for screen readers, the same trail order. Kept in one spot so the two
// can never say different things about the same state.

export const INK = '#14202b'
export const CREAM = '#fff4da'
export const LIME = '#c8f56b'
export const CORAL = '#ff5a47'

export function stillPlease() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}

export function escape(text) {
  return String(text).replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`)
}

/** "Swift Clover Goat" -> "Swift Clover": the label under an explorer's dot. */
export function shortName(name) {
  return String(name).replace(/ Goat$/, '')
}

export function pinHtml(tile, here) {
  const mark = tile.cleared ? '' : here ? '!' : '?'
  const name = tile.cleared || here ? `<span class="tile-name">${escape(tile.place)}</span>` : '' // shown on hover or tap
  return `<span class="pin" aria-hidden="true">${mark}</span>${name}`
}

/** The class list of a place's pin. */
export function pinClass(tile, { here, fresh, picked }) {
  return `tile ${tile.cleared ? 'cleared' : 'fog'}${fresh ? ' fresh' : ''}${here ? ' here' : ''}${picked ? ' picked' : ''}`
}

/** What a screen reader hears for a place's pin. */
export function pinLabel(tile, here) {
  return tile.cleared ? `${tile.place}, uncovered` : here ? 'Fog. Your quest is here' : 'Fog'
}

/** Cleared places in the order they were uncovered: the route of your week so far. -> [[lat, lng]] */
export function trailOf(map, spots) {
  return map
    .filter((tile) => tile.cleared)
    .map((tile, n) => ({ at: spots.get(tile.place), when: Date.parse(tile.cleared_at ?? '') || 0, n }))
    .sort((a, b) => a.when - b.when || a.n - b.n)
    .map((stop) => stop.at)
}

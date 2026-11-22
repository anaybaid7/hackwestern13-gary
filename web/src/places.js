// Where each place is on the real map, as [latitude, longitude]. This only
// decides where to draw. Which places exist and which are cleared still
// comes from the backend.
//
// A quest's own lat/lng (the scout looks them up) comes first. Then these
// hand-placed spots for places the scout and the seed quests use. Anything
// else gets a made-up spot near downtown, for drawing only.
export const LONDON = [42.9849, -81.2453] // downtown London, Ontario

const KNOWN = {
  'hack western': [43.0096, -81.2737], // Western University
  'western university': [43.0096, -81.2737],
  'gibbons park': [42.9995, -81.2585],
  'harris park': [42.9862, -81.2563],
  'ivey park': [42.984, -81.252],
  'victoria park': [42.9876, -81.2464],
  'springbank park': [42.9655, -81.3005],
  'kains woods': [42.975, -81.358],
  'thames valley parkway': [42.9845, -81.258],
  'fanshawe': [43.04, -81.18],
  'medway valley': [43.018, -81.282],
  'westminster ponds': [42.947, -81.24],
  'meadowlily woods': [42.969, -81.19],
  'covent garden market': [42.9832, -81.2485],
  'museum london': [42.9846, -81.254],
  'storybook gardens': [42.963, -81.31],
  'sifton bog': [42.975, -81.32],
  'warbler woods': [42.97, -81.348],
  'kilally meadows': [43.024, -81.223],
}

/** The backend's way of telling two spellings of one place apart (rules.place_key). */
export function placeKey(place) {
  return String(place ?? '').toLowerCase().split(/\s+/).filter(Boolean).join(' ')
}

function known(key) {
  for (const [name, spot] of Object.entries(KNOWN)) if (key.includes(name)) return spot
  return null
}

function hash(text) {
  let h = 2166136261
  for (const ch of text) h = Math.imul(h ^ ch.codePointAt(0), 16777619)
  return h >>> 0
}

const CLOSE = 0.0012 // degrees, about 130 m: pins nearer than this are nudged apart
const SPREAD = 0.03 // degrees, about 3 km: how far from downtown an unknown place may land

/** {place: [lat, lng]} for the map tiles that carry real coordinates (from the scout). */
export function realSpots(tiles) {
  const out = {}
  for (const tile of tiles) if (typeof tile.lat === 'number' && typeof tile.lng === 'number') out[tile.place] = [tile.lat, tile.lng]
  return out
}

/**
 * Where a quest really is: its own coordinates, else a hand-placed known spot,
 * else null. Never the made-up spot layout() gives an unknown place, so
 * "you are here" is only ever said about a real position.
 */
export function realSpot(quest) {
  if (!quest) return null
  if (typeof quest.lat === 'number' && typeof quest.lng === 'number') return [quest.lat, quest.lng]
  return known(placeKey(quest.place))
}

// In range of a quest: a sniff finishes a quest with a real position only
// within this distance of it (backend/rules.py). Wide enough for a laptop's
// rough Wi-Fi fix and for a big park.
export const RANGE_METRES = 1000

/** Are you in range of `spot`? */
export function isNear(me, spot) {
  if (!me || !spot) return false
  return metresBetween(me, spot) <= RANGE_METRES
}

// A short quest is one near you: no further than this, so it never takes a big effort.
export const SHORT_METRES = 5200

/** Open quests with a real position within SHORT_METRES of you, nearest first. */
export function nearby(me, quests = [], metres = SHORT_METRES) {
  if (!me) return []
  return quests
    .map((quest) => ({ quest, spot: realSpot(quest) }))
    .filter(({ spot }) => spot && metresBetween(me, spot) <= metres)
    .sort((a, b) => metresBetween(me, a.spot) - metresBetween(me, b.spot))
    .map(({ quest }) => quest)
}

/** The one after `currentId` in a nearest-first list ("give me another"), else the nearest. */
export function nextNearby(list, currentId) {
  const at = list.findIndex((q) => q.id === currentId)
  return at >= 0 && list.length > 1 ? list[(at + 1) % list.length] : (list[0] ?? null)
}

/** place name -> [lat, lng] for every place: the same spot on every visit.
 * `fixed`: {place: [lat, lng]} real coordinates, used before anything else. */
export function layout(places, fixed = {}) {
  const out = new Map()
  const taken = []
  const near = ([a, b]) => taken.some(([ta, tb]) => Math.abs(ta - a) < CLOSE && Math.abs(tb - b) < CLOSE)
  for (const place of places) {
    const key = placeKey(place)
    const h = hash(key)
    const base = fixed[place] ?? known(key) ?? [
      LONDON[0] + ((h % 1000) / 1000 - 0.5) * SPREAD,
      LONDON[1] + (((h >>> 10) % 1000) / 1000 - 0.5) * SPREAD * 1.4,
    ]
    let spot = base
    for (let tries = 1; near(spot) && tries < 40; tries += 1) {
      const angle = (hash(`${key}#${tries}`) % 360) * (Math.PI / 180)
      const step = CLOSE * (1 + tries / 4)
      spot = [base[0] + Math.sin(angle) * step, base[1] + Math.cos(angle) * step * 1.4]
    }
    taken.push(spot)
    out.set(place, spot)
  }
  return out
}

/** Metres between two [lat, lng] points, as the crow flies. */
export function metresBetween([lat1, lng1], [lat2, lng2]) {
  const rad = Math.PI / 180
  const dLat = (lat2 - lat1) * rad
  const dLng = (lng2 - lng1) * rad
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2
  return 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

/**
 * "About 1.2 km from you." Worked out in the browser from your own location,
 * which is never sent anywhere. Straight-line, so it says so.
 */
export function away(me, there) {
  if (!me || !there) return null
  const m = metresBetween(me, there)
  if (m < 60) return 'You are here.'
  const said = m < 1000 ? `${Math.round(m / 50) * 50} m` : `${(m / 1000).toFixed(1)} km`
  return `About ${said} from you, as the crow flies.`
}

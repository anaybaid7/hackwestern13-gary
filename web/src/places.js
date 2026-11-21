// Where each place is on the real map, as [latitude, longitude]. This only
// decides where to draw. Which places exist and which are cleared still
// comes from the backend.
//
// ponytail: hand-placed spots for the places the scout and the seed quests
// use. If the scout starts finding many new places, add optional lat/lng to
// the contract and read them here instead.
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

/** place name -> [lat, lng] for every place: the same spot on every visit. */
export function layout(places) {
  const out = new Map()
  const taken = []
  const near = ([a, b]) => taken.some(([ta, tb]) => Math.abs(ta - a) < CLOSE && Math.abs(tb - b) < CLOSE)
  for (const place of places) {
    const key = placeKey(place)
    const h = hash(key)
    const base = known(key) ?? [
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

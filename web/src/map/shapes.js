// The shapes the 3D map draws, worked out from the state: the fog with the
// cleared places cut out of it, the lime rim along the edge of what you have
// explored, the dashed trail between cleared places, and the quest's beacon.
// Plain functions of [lat, lng] points, so they can be tested without a map.
//
// GeoJSON wants [lng, lat]; everything that goes in here is [lat, lng], as in
// places.js, and is turned round on the way out.
import polygonClipping from 'polygon-clipping'

export const CLEAR_METRES = 350 // the same clearing as the flat map
export const REVEAL_MS = 1400 // a place that has just cleared opens up over this long
const STEPS = 64 // corners on a clearing's circle
const METRES_PER_DEGREE = 111320

// The fog covers this much: a little more than the map can be moved to.
export const FOG_EXTENT = [[42.4, -82.2], [43.6, -80.3]]

function metresToDegrees([lat], north, east) {
  return [north / METRES_PER_DEGREE, east / (METRES_PER_DEGREE * Math.cos((lat * Math.PI) / 180))]
}

/** A closed ring of [lng, lat] round `at`, `metres` across from centre to edge. */
export function circle(at, metres, steps = STEPS) {
  const ring = []
  for (let i = 0; i < steps; i += 1) {
    const angle = (i / steps) * Math.PI * 2
    const [dLat, dLng] = metresToDegrees(at, Math.sin(angle) * metres, Math.cos(angle) * metres)
    ring.push([at[1] + dLng, at[0] + dLat])
  }
  ring.push(ring[0])
  return ring
}

/** How far open a clearing is, 0 to 1, `ms` into its reveal: it bursts open, then settles. */
export function opening(ms) {
  const t = Math.max(0, Math.min(1, ms / REVEAL_MS))
  return 1 - (1 - t) ** 3
}

/**
 * The fog and its edge. `clearings`: [{ at: [lat, lng], open: 0..1 }].
 * -> { fog, edges }: fog is a GeoJSON MultiPolygon of everything still
 * unexplored (clearings that overlap make one bigger hole), and edges are the
 * rings of [lng, lat] where explored ground meets the fog.
 */
export function fogShape(clearings, metres = CLEAR_METRES) {
  const [[south, west], [north, east]] = FOG_EXTENT
  const world = [[[west, south], [east, south], [east, north], [west, north], [west, south]]]
  const holes = clearings
    .filter(({ at, open = 1 }) => at && open * metres >= 1)
    .map(({ at, open = 1 }) => [circle(at, metres * open)])
  if (holes.length === 0) return { fog: { type: 'MultiPolygon', coordinates: [world] }, edges: [] }
  const explored = polygonClipping.union(...holes)
  const fog = polygonClipping.difference(world, explored)
  return { fog: { type: 'MultiPolygon', coordinates: fog }, edges: explored.flat() }
}

/**
 * Short flat quads along a line of [lng, lat] points, `wide` metres across:
 * `on` metres drawn, then `off` metres left out. The 3D map raises them into
 * a dashed ribbon. -> [ring of [lng, lat]]
 */
export function dashes(line, wide, on, off = 0) {
  const out = []
  const half = wide / 2
  let drawing = true
  let left = on // metres left in this dash (drawing) or this gap
  for (let i = 0; i + 1 < line.length; i += 1) {
    const [lng1, lat1] = line[i]
    const [lng2, lat2] = line[i + 1]
    const perLng = METRES_PER_DEGREE * Math.cos((lat1 * Math.PI) / 180)
    const dx = (lng2 - lng1) * perLng // east, metres
    const dy = (lat2 - lat1) * METRES_PER_DEGREE // north, metres
    const length = Math.hypot(dx, dy)
    if (length === 0) continue
    // one metre along the segment, and half the width across it, in degrees
    const along = [dx / length / perLng, dy / length / METRES_PER_DEGREE]
    const across = [((-dy / length) * half) / perLng, ((dx / length) * half) / METRES_PER_DEGREE]
    const point = (m, side) => [lng1 + along[0] * m + across[0] * side, lat1 + along[1] * m + across[1] * side]
    let done = 0
    while (done < length) {
      const step = Math.min(left, length - done)
      if (drawing && step > 0.05) { // never a sliver left by rounding
        const a = done
        const b = done + step
        out.push([point(a, 1), point(b, 1), point(b, -1), point(a, -1), point(a, 1)])
      }
      done += step
      left -= step
      if (left <= 0) {
        drawing = off > 0 ? !drawing : true
        left = drawing ? on : off
      }
    }
  }
  return out
}

/** A GeoJSON FeatureCollection of polygons, one per ring. */
export function polygons(rings, properties = {}) {
  return {
    type: 'FeatureCollection',
    features: rings.map((ring) => ({ type: 'Feature', properties, geometry: { type: 'Polygon', coordinates: [ring] } })),
  }
}

// The flat map: OpenStreetMap tiles in Leaflet, with the fog painted on a
// canvas above the streets and below the pins. This is the map every browser
// can draw, and the one used when the 3D map cannot start (no WebGL, an old
// browser, a phone that would rather not). It draws; MapScreen decides.
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useImperativeHandle, useRef } from 'react'
import { CREAM, INK, escape, pinClass, pinHtml, pinLabel, shortName, stillPlease, trailOf } from '../map/marks.js'

const CLEAR_METRES = 350
const START_ZOOM = 14
// thick enough that a cleared place stands out; streets only just show through
const FOG_COLOUR = 'rgba(44, 58, 78, 0.78)' // a dusky slate, like unexplored ground in a game
const FOG_DITHER = 'rgba(255, 255, 255, 0.07)'
const FRONTIER = 'rgba(200, 245, 107, 1)' // the LCD lime: the edge of what you have explored
const REVEAL_MS = 1400 // a place that has just cleared opens up over this long

/** A 6 x 6 tile of two dither pixels, so the fog reads as fog and not as a tint. */
function ditherTile() {
  const tile = document.createElement('canvas')
  tile.width = 6
  tile.height = 6
  const ctx = tile.getContext?.('2d')
  if (!ctx) return null
  ctx.fillStyle = FOG_DITHER
  ctx.fillRect(0, 0, 2, 2)
  ctx.fillRect(3, 3, 2, 2)
  return tile
}

/**
 * The fog, painted on a canvas above the streets and below the pins. Each
 * cleared place rubs out a soft-edged circle; circles that overlap simply
 * merge. A dashed lime frontier runs round the edge of the explored ground,
 * and a place that has just cleared opens up from nothing. Redrawn whenever
 * the map moves.
 */
function makeFog(map) {
  const pane = map.createPane('fog')
  pane.style.zIndex = 450
  pane.style.pointerEvents = 'none'
  // 'leaflet-zoom-animated' lets it glide through a zoom with the streets, like Leaflet's own overlays
  const canvas = L.DomUtil.create('canvas', 'fog-canvas leaflet-zoom-animated', pane)
  let spots = [] // { key, at, born }: born is when its reveal started, 0 for none
  let dither = null
  let frame = 0
  function draw() {
    frame = 0
    const size = map.getSize()
    const ratio = window.devicePixelRatio || 1
    canvas.width = size.x * ratio
    canvas.height = size.y * ratio
    canvas.style.width = `${size.x}px`
    canvas.style.height = `${size.y}px`
    L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]))
    const ctx = canvas.getContext?.('2d')
    if (!ctx) return // no canvas here (tests): the pins still say what is cleared
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    ctx.globalCompositeOperation = 'source-over'
    ctx.fillStyle = FOG_COLOUR
    ctx.fillRect(0, 0, size.x, size.y)
    dither = dither ?? ditherTile()
    if (dither) {
      // anchored to the map, so the dither slides with the streets
      const world = map.containerPointToLayerPoint([0, 0]).add(map.getPixelOrigin())
      ctx.save()
      ctx.translate(-(((world.x % 6) + 6) % 6), -(((world.y % 6) + 6) % 6))
      ctx.fillStyle = ctx.createPattern(dither, 'repeat')
      ctx.fillRect(0, 0, size.x + 6, size.y + 6)
      ctx.restore()
    }
    const now = performance.now()
    let opening = false
    const holes = spots.map(({ at, born }) => {
      const centre = map.latLngToContainerPoint(at)
      const edge = map.latLngToContainerPoint([at[0] + CLEAR_METRES / 111320, at[1]])
      const full = Math.max(16, centre.y - edge.y) // never smaller than a pin, even zoomed out
      const t = born ? Math.min(1, (now - born) / REVEAL_MS) : 1
      if (t < 1) opening = true
      return { centre, r: full * (1 - (1 - t) ** 3) } // eases out, so it bursts open then settles
    })
    ctx.globalCompositeOperation = 'destination-out'
    for (const { centre, r } of holes) {
      if (r < 1) continue
      const glow = ctx.createRadialGradient(centre.x, centre.y, r * 0.55, centre.x, centre.y, r)
      glow.addColorStop(0, 'rgba(0,0,0,1)')
      glow.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = glow
      ctx.beginPath()
      ctx.arc(centre.x, centre.y, r, 0, Math.PI * 2)
      ctx.fill()
    }
    // the frontier: painted only where fog remains, so where clearings meet it vanishes
    ctx.globalCompositeOperation = 'source-atop'
    ctx.strokeStyle = FRONTIER
    ctx.lineWidth = 3
    ctx.setLineDash?.([4, 5])
    for (const { centre, r } of holes) {
      if (r < 6) continue
      ctx.beginPath()
      ctx.arc(centre.x, centre.y, r * 0.86, 0, Math.PI * 2)
      ctx.stroke()
    }
    ctx.globalCompositeOperation = 'source-over'
    if (opening) frame = requestAnimationFrame(draw)
  }
  function redraw() {
    if (frame) cancelAnimationFrame(frame)
    draw()
  }
  map.on('move zoomend resize viewreset', redraw)
  map.on('unload', () => frame && cancelAnimationFrame(frame))
  // during an animated zoom, scale the painted fog the same way the tiles are scaled
  map.on('zoomanim', (event) => {
    const scale = map.getZoomScale(event.zoom)
    const offset = map._latLngToNewLayerPoint(map.containerPointToLatLng([0, 0]), event.zoom, event.center)
    L.DomUtil.setTransform(canvas, offset, scale)
  })
  return {
    /** next: [{ key, at, fresh }]. A fresh place keeps its reveal going across redraws. */
    set(next) {
      const was = new Map(spots.map((spot) => [spot.key, spot.born]))
      const now = performance.now()
      const still = stillPlease()
      spots = next.map(({ key, at, fresh }) => ({ key, at, born: fresh && !still ? was.get(key) || now : 0 }))
      redraw()
    },
  }
}


/**
 * tiles: state.map. spots: place -> [lat, lng]. fresh: places that just cleared.
 * ref gets { goTo(at, zoom), fit(points) } for the buttons over the map.
 */
export default function FlatWorld({ ref, tiles, spots, questPlace, picked, fresh, onPick, me, others = [], first, onStreets }) {
  const box = useRef(null)
  const leaflet = useRef(null)

  // the map itself, once
  useEffect(() => {
    const m = L.map(box.current, { zoomControl: false, minZoom: 11, maxBounds: [[42.7, -81.7], [43.25, -80.8]] })
    m.setView(first, START_ZOOM)
    const streets = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(m)
    // no network: say so once, and keep the fog and pins working
    let loaded = false
    streets.on('tileload', () => {
      loaded = true
      onStreets('on')
    })
    streets.on('tileerror', () => !loaded && onStreets('off'))
    L.control.zoom({ position: 'bottomright' }).addTo(m)
    const trailPane = m.createPane('trail')
    trailPane.style.zIndex = 460 // above the fog, below the pins
    trailPane.style.pointerEvents = 'none'
    leaflet.current = {
      map: m,
      fog: makeFog(m),
      trail: L.layerGroup().addTo(m),
      layers: L.layerGroup().addTo(m),
      me: L.layerGroup().addTo(m),
      others: L.layerGroup().addTo(m),
    }
    // the box can change size without the window doing so (the handheld frame, a rotated phone)
    const watch = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => m.invalidateSize())
    watch?.observe(box.current)
    return () => {
      watch?.disconnect()
      m.remove()
      leaflet.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- made once; the effects below keep it current
  }, [])

  useImperativeHandle(ref, () => ({
    goTo(at, zoom = null) {
      const m = leaflet.current?.map
      if (!m || !at) return
      if (zoom == null) m.panTo(at, { animate: !stillPlease() })
      else m.setView(at, Math.max(m.getZoom(), zoom))
    },
    fit(points) {
      if (leaflet.current && points.length) leaflet.current.map.fitBounds(L.latLngBounds(points), { padding: [36, 36], maxZoom: 15 })
    },
  }), [])

  // the fog, the trail and the pins, whenever the state changes
  const signature = JSON.stringify([tiles.map((t) => [t.place, t.cleared, t.cleared_at ?? null]), questPlace, fresh, picked])
  useEffect(() => {
    const { layers, fog, trail } = leaflet.current
    layers.clearLayers()
    trail.clearLayers()
    fog.set(tiles.filter((tile) => tile.cleared).map((tile) => ({ key: tile.place, at: spots.get(tile.place), fresh: fresh.includes(tile.place) })))
    const route = trailOf(tiles, spots)
    if (route.length > 1) {
      const line = { pane: 'trail', interactive: false, lineCap: 'square', lineJoin: 'miter' }
      L.polyline(route, { ...line, className: 'trail-under', color: CREAM, weight: 9, opacity: 0.85 }).addTo(trail)
      L.polyline(route, { ...line, className: 'trail', color: INK, weight: 4, dashArray: '2 9' }).addTo(trail)
    }
    for (const tile of tiles) {
      const here = !tile.cleared && questPlace === tile.place
      const marker = L.marker(spots.get(tile.place), {
        icon: L.divIcon({
          className: pinClass(tile, { here, fresh: fresh.includes(tile.place), picked: picked === tile.place }),
          html: pinHtml(tile, here),
          iconSize: null,
        }),
        keyboard: true,
        riseOnHover: true,
      }).addTo(layers)
      const el = marker.getElement()
      el.setAttribute('role', 'button')
      el.setAttribute('aria-label', pinLabel(tile, here))
      el.setAttribute('aria-pressed', String(picked === tile.place))
      marker.on('click', () => onPick(tile.place))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `signature` is everything these layers draw
  }, [signature])

  // you
  useEffect(() => {
    const layer = leaflet.current?.me
    if (!layer) return
    layer.clearLayers()
    if (!me.at) return
    L.circle(me.at, { radius: me.accuracy ?? 30, stroke: false, fillColor: '#3E8EDE', fillOpacity: 0.15, interactive: false }).addTo(layer)
    L.marker(me.at, { icon: L.divIcon({ className: 'me', html: '<span></span>', iconSize: [18, 18] }), interactive: false, title: 'You are here' }).addTo(layer)
  }, [me.at, me.accuracy])

  // explorers nearby (only when you have switched it on): one dot each, moved as they move
  const where = others.map((o) => `${o.tag}:${o.lat},${o.lon}:${o.same_quest}`).join('|')
  useEffect(() => {
    const layer = leaflet.current?.others
    if (!layer) return
    layer.clearLayers()
    for (const other of others) {
      L.marker([other.lat, other.lon], {
        icon: L.divIcon({ className: `other${other.same_quest ? ' same' : ''}`, html: `<span></span><b>${escape(shortName(other.name))}</b>`, iconSize: [16, 16] }),
        interactive: true,
        title: `${other.name}${other.same_quest ? ', on your quest' : ''}`,
      }).addTo(layer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `where` is everything these dots draw
  }, [where])

  return <div className="world-map" ref={box} aria-label="Map of London, Ontario" />
}

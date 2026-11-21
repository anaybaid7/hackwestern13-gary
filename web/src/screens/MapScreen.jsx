// The fog-of-war map (issue #26), on OpenStreetMap: real streets and park
// names, dimmed by fog everywhere except round the places you have cleared.
// Each place from a quest is a pin. Your own position is a dot, read from
// the browser and kept there: it is never sent anywhere.
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { clock, dayName, dayKey } from '../format.js'
import { LONDON, layout } from '../places.js'

const CLEAR_METRES = 350
const START_ZOOM = 14
// thick enough that a cleared place stands out; streets only just show through
const FOG_COLOUR = 'rgba(44, 58, 78, 0.78)' // a dusky slate, like unexplored ground in a game
const FOG_DITHER = 'rgba(255, 255, 255, 0.07)'

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
 * merge. Redrawn whenever the map moves.
 */
function makeFog(map) {
  const pane = map.createPane('fog')
  pane.style.zIndex = 450
  pane.style.pointerEvents = 'none'
  // 'leaflet-zoom-animated' lets it glide through a zoom with the streets, like Leaflet's own overlays
  const canvas = L.DomUtil.create('canvas', 'fog-canvas leaflet-zoom-animated', pane)
  let spots = []
  let dither = null
  function draw() {
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
    ctx.globalCompositeOperation = 'destination-out'
    for (const [lat, lng] of spots) {
      const centre = map.latLngToContainerPoint([lat, lng])
      const edge = map.latLngToContainerPoint([lat + CLEAR_METRES / 111320, lng])
      const r = Math.max(8, centre.y - edge.y)
      const glow = ctx.createRadialGradient(centre.x, centre.y, r * 0.55, centre.x, centre.y, r)
      glow.addColorStop(0, 'rgba(0,0,0,1)')
      glow.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = glow
      ctx.beginPath()
      ctx.arc(centre.x, centre.y, r, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  map.on('move zoomend resize viewreset', draw)
  // during an animated zoom, scale the painted fog the same way the tiles are scaled
  map.on('zoomanim', (event) => {
    const scale = map.getZoomScale(event.zoom)
    const offset = map._latLngToNewLayerPoint(map.containerPointToLatLng([0, 0]), event.zoom, event.center)
    L.DomUtil.setTransform(canvas, offset, scale)
  })
  return {
    set(next) {
      spots = next
      draw()
    },
  }
}

function pinHtml(tile, here) {
  const mark = tile.cleared ? '' : here ? '!' : '?'
  const name = tile.cleared || here ? `<span class="tile-name">${escape(tile.place)}</span>` : '' // shown on hover or tap
  return `<span class="pin" aria-hidden="true">${mark}</span>${name}`
}

function escape(text) {
  return String(text).replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`)
}

/** Follows the browser's location while the map is open. */
function useWhereAmI() {
  const [me, setMe] = useState({ state: 'off', at: null, accuracy: null })
  useEffect(() => {
    const geo = navigator.geolocation
    if (!geo) return undefined
    setMe((m) => ({ ...m, state: 'asking' }))
    const id = geo.watchPosition(
      (pos) => setMe({ state: 'on', at: [pos.coords.latitude, pos.coords.longitude], accuracy: pos.coords.accuracy }),
      () => setMe({ state: 'denied', at: null, accuracy: null }),
      { enableHighAccuracy: true, maximumAge: 10000 },
    )
    return () => geo.clearWatch(id)
  }, [])
  return me
}

export default function MapScreen({ map, flash, quest = null, focusPlace = null }) {
  const [picked, setPicked] = useState(focusPlace)
  const box = useRef(null)
  const leaflet = useRef(null)
  const me = useWhereAmI()
  const spots = layout(map.map((tile) => tile.place))
  const cleared = map.filter((tile) => tile.cleared)
  const chosen = map.find((tile) => tile.place === picked) ?? null
  const questPlace = quest?.place
  const first = spots.get(focusPlace) ?? spots.get(questPlace) ?? spots.get(cleared[0]?.place) ?? LONDON

  // the map itself, once
  useEffect(() => {
    const m = L.map(box.current, { zoomControl: false, minZoom: 11, maxBounds: [[42.7, -81.7], [43.25, -80.8]] })
    m.setView(first, START_ZOOM)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(m)
    L.control.zoom({ position: 'bottomright' }).addTo(m)
    leaflet.current = { map: m, fog: makeFog(m), layers: L.layerGroup().addTo(m), me: L.layerGroup().addTo(m) }
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

  // the fog and the pins, whenever the state changes
  const signature = JSON.stringify([map.map((t) => [t.place, t.cleared]), questPlace, flash.cleared, picked])
  useEffect(() => {
    const { layers, fog } = leaflet.current
    layers.clearLayers()
    fog.set(cleared.map((tile) => spots.get(tile.place)))
    for (const tile of map) {
      const here = !tile.cleared && questPlace === tile.place
      const fresh = flash.cleared.includes(tile.place)
      const marker = L.marker(spots.get(tile.place), {
        icon: L.divIcon({
          className: `tile ${tile.cleared ? 'cleared' : 'fog'}${fresh ? ' fresh' : ''}${here ? ' here' : ''}${picked === tile.place ? ' picked' : ''}`,
          html: pinHtml(tile, here),
          iconSize: null,
        }),
        keyboard: true,
        riseOnHover: true,
      }).addTo(layers)
      const el = marker.getElement()
      el.setAttribute('role', 'button')
      el.setAttribute('aria-label', tile.cleared ? `${tile.place}, uncovered` : here ? 'Fog. Your quest is here' : 'Fog')
      el.setAttribute('aria-pressed', String(picked === tile.place))
      marker.on('click', () => setPicked((p) => (p === tile.place ? null : tile.place)))
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

  // "See on map" from a quest: fly there
  useEffect(() => {
    if (!focusPlace || !leaflet.current) return
    setPicked(focusPlace)
    const at = spots.get(focusPlace)
    if (at) leaflet.current.map.setView(at, Math.max(leaflet.current.map.getZoom(), 15))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when asked to look somewhere new
  }, [focusPlace])

  function findMe() {
    if (me.at) leaflet.current.map.setView(me.at, Math.max(leaflet.current.map.getZoom(), 15))
  }

  return (
    <div className="screen map-screen">
      <div className="map-head">
        <h2>Map</h2>
        <span className="chip chip-count">
          {cleared.length}/{map.length} uncovered
        </span>
      </div>

      <div className="world">
        <div className="world-map" ref={box} aria-label="Map of London, Ontario" />
        <button type="button" className="locate" onClick={findMe} disabled={!me.at}
                aria-label={me.at ? 'Show where I am' : me.state === 'denied' ? 'Location is off' : 'Finding you'}>
          ◎
        </button>
      </div>
      {me.state === 'denied' && <p className="small">Location is off. Allow it to see yourself on the map.</p>}

      <div className="sheet" aria-live="polite">
        {!chosen && <p className="empty">Tap a pin.</p>}
        {chosen && !chosen.cleared && (
          <>
            <h3>{questPlace === chosen.place ? chosen.place : 'Still in fog'}</h3>
            {questPlace === chosen.place && <p className="small">Your quest is here.{quest.note ? ` ${quest.note}` : ''}</p>}
          </>
        )}
        {chosen?.cleared && (
          <>
            <h3>{chosen.place}</h3>
            {chosen.cleared_at && (
              <p className="small">
                Uncovered {dayName(dayKey(chosen.cleared_at))}, {clock(chosen.cleared_at)}
              </p>
            )}
            <ul className="tile-finds">
              {(chosen.finds ?? []).map((find, n) => (
                <li key={n}>
                  {find.label} · {clock(find.ts)}
                  {find.friend ? ' · Herd' : ''}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}

// The fog-of-war map (issue #26), on OpenStreetMap: real streets and park
// names, dimmed by fog everywhere except round the places you have cleared.
// Each place from a quest is a pin. Your own position is a dot, read from
// the browser and kept there: it is never sent anywhere.
//
// Everything here only draws what the state says. Which places are cleared,
// and when, comes from the backend; the trail, the frontier and the reveal
// are pictures of that.
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { useWhereAmI } from '../whereAmI.js'
import { clock, dayName, dayKey } from '../format.js'
import { LONDON, away, layout, realSpots } from '../places.js'

const CLEAR_METRES = 350
const START_ZOOM = 14
// thick enough that a cleared place stands out; streets only just show through
const FOG_COLOUR = 'rgba(44, 58, 78, 0.78)' // a dusky slate, like unexplored ground in a game
const FOG_DITHER = 'rgba(255, 255, 255, 0.07)'
const FRONTIER = 'rgba(200, 245, 107, 1)' // the LCD lime: the edge of what you have explored
const REVEAL_MS = 1400 // a place that has just cleared opens up over this long
const INK = '#14202b'
const CREAM = '#fff4da'

function stillPlease() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}

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

function pinHtml(tile, here) {
  const mark = tile.cleared ? '' : here ? '!' : '?'
  const name = tile.cleared || here ? `<span class="tile-name">${escape(tile.place)}</span>` : '' // shown on hover or tap
  return `<span class="pin" aria-hidden="true">${mark}</span>${name}`
}

function escape(text) {
  return String(text).replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`)
}

/** Cleared places in the order they were uncovered: the route of your week so far. */
function trailOf(map, spots) {
  return map
    .filter((tile) => tile.cleared)
    .map((tile, n) => ({ at: spots.get(tile.place), when: Date.parse(tile.cleared_at ?? '') || 0, n }))
    .sort((a, b) => a.when - b.when || a.n - b.n)
    .map((stop) => stop.at)
}

export default function MapScreen({ map, flash, quest = null, focusPlace = null, quests = [], onPickQuest = null, busy = false }) {
  const [picked, setPicked] = useState(focusPlace)
  const [streets, setStreets] = useState('loading') // 'loading' | 'on' | 'off': whether street tiles arrive
  const box = useRef(null)
  const leaflet = useRef(null)
  const me = useWhereAmI()
  const spots = layout(map.map((tile) => tile.place), realSpots(map))
  const cleared = map.filter((tile) => tile.cleared)
  const chosen = map.find((tile) => tile.place === picked) ?? null
  const questPlace = quest?.place
  const questAt = questPlace ? spots.get(questPlace) : null
  const first = spots.get(focusPlace) ?? questAt ?? spots.get(cleared[0]?.place) ?? LONDON

  // the map itself, once
  useEffect(() => {
    const m = L.map(box.current, { zoomControl: false, minZoom: 11, maxBounds: [[42.7, -81.7], [43.25, -80.8]] })
    m.setView(first, START_ZOOM)
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(m)
    // no network: say so once, and keep the fog and pins working
    let loaded = false
    tiles.on('tileload', () => {
      loaded = true
      setStreets('on')
    })
    tiles.on('tileerror', () => !loaded && setStreets('off'))
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

  // the fog, the trail and the pins, whenever the state changes
  const signature = JSON.stringify([map.map((t) => [t.place, t.cleared, t.cleared_at ?? null]), questPlace, flash.cleared, picked])
  useEffect(() => {
    const { layers, fog, trail } = leaflet.current
    layers.clearLayers()
    trail.clearLayers()
    fog.set(cleared.map((tile) => ({ key: tile.place, at: spots.get(tile.place), fresh: flash.cleared.includes(tile.place) })))
    const route = trailOf(map, spots)
    if (route.length > 1) {
      const line = { pane: 'trail', interactive: false, lineCap: 'square', lineJoin: 'miter' }
      L.polyline(route, { ...line, className: 'trail-under', color: CREAM, weight: 9, opacity: 0.85 }).addTo(trail)
      L.polyline(route, { ...line, className: 'trail', color: INK, weight: 4, dashArray: '2 9' }).addTo(trail)
    }
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

  // a place that has just cleared: bring it into view so its reveal is seen
  const freshPlace = flash.cleared.find((place) => spots.has(place)) ?? null
  useEffect(() => {
    if (!freshPlace || focusPlace || !leaflet.current) return
    leaflet.current.map.panTo(spots.get(freshPlace), { animate: !stillPlease() })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when a new place clears
  }, [freshPlace])

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

  function goToQuest() {
    if (!questAt) return
    setPicked(questPlace)
    leaflet.current.map.setView(questAt, Math.max(leaflet.current.map.getZoom(), 15))
  }

  function showAll() {
    const all = [...spots.values()]
    if (me.at) all.push(me.at)
    if (all.length === 0) return
    leaflet.current.map.fitBounds(L.latLngBounds(all), { padding: [36, 36], maxZoom: 15 })
  }

  const chosenAway = chosen && me.at ? away(me.at, spots.get(chosen.place)) : null
  // an open quest at the tapped place, other than the one you are on: you can switch to it from here
  const waiting = chosen && !chosen.cleared ? quests.find((q) => q.id === chosen.quest_id && q.id !== quest?.id) ?? null : null

  return (
    <div className="screen map-screen">
      <div className="map-head">
        <h2>Map</h2>
        <span className="chip chip-count">
          {cleared.length}/{map.length} uncovered
        </span>
      </div>
      {map.length > 0 && (
        <div className="explored" aria-hidden="true">
          {map.map((_, n) => (
            <span key={n} className={`explored-cell${n < cleared.length ? ' on' : ''}${n < cleared.length && n >= cleared.length - flash.cleared.length ? ' fresh' : ''}`} />
          ))}
        </div>
      )}

      <div className="world">
        <div className="world-map" ref={box} aria-label="Map of London, Ontario" />
        <div className="map-tools">
          <button type="button" onClick={goToQuest} disabled={!questAt}>Quest</button>
          <button type="button" onClick={showAll} disabled={map.length === 0 && !me.at}>All places</button>
        </div>
        <button type="button" className="locate" onClick={findMe} disabled={!me.at}
                aria-label={me.at ? 'Show where I am' : me.state === 'denied' ? 'Location is off' : 'Finding you'}>
          ◎
        </button>
        {streets === 'off' && <p className="map-note" role="status">No street map right now. The fog and the pins still work.</p>}
      </div>
      {me.state === 'denied' && <p className="small">Location is off. Allow it to see yourself on the map.</p>}

      <ul className="map-key">
        <li><span className="key-mark key-fog">?</span>Fog</li>
        <li><span className="key-mark key-quest">!</span>Your quest</li>
        <li><span className="key-mark key-flag" />Uncovered</li>
        <li><span className="key-mark key-trail" />Your trail</li>
      </ul>

      <div className="sheet" aria-live="polite">
        {!chosen && <p className="empty">Tap a pin.</p>}
        {chosen && !chosen.cleared && (questPlace === chosen.place || !waiting) && (
          <>
            <h3>{questPlace === chosen.place ? chosen.place : 'Still in fog'}</h3>
            {questPlace === chosen.place && <p className="small">Your quest is here.{quest.note ? ` ${quest.note}` : ''}</p>}
          </>
        )}
        {waiting && questPlace !== chosen.place && (
          <>
            <h3>{waiting.place}</h3>
            <p className="small">
              {waiting.title} · {waiting.time === 'long' ? 'Long' : 'Short'} · +{waiting.xp} XP
            </p>
            {onPickQuest && (
              <button type="button" className="button primary" disabled={busy} onClick={() => onPickQuest(waiting)}>
                Make this my quest
              </button>
            )}
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
        {chosenAway && <p className="small away">{chosenAway}</p>}
      </div>
    </div>
  )
}

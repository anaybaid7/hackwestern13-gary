// The 3D map: London in MapLibre, tilted, with real building heights and the
// Thames valley shaded in, drawn in Gary's Pocket Pixel colours, with street,
// park, river and neighbourhood names. The fog dims all the ground you have not
// explored (the buildings on it stay clear); each cleared place is a bright
// clearing ringed by a wall of fog with a lime rim on top. Your trail floats
// over it, and your quest is a coral beacon you can see from across town.
//
// Loaded only when this browser can draw it (MapScreen checks for WebGL), so
// MapLibre never weighs on the first page load. If it fails to start, it says
// so through onFail and MapScreen draws the flat map instead.
//
// It draws; MapScreen decides. The pins are the same as the flat map's.
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useImperativeHandle, useRef } from 'react'
import { CORAL, CREAM, INK, LIME, pinClass, pinHtml, pinLabel, stillPlease, trailOf } from '../map/marks.js'
import { circle, dashes, fogShape, opening, polygons } from '../map/shapes.js'

// Free vector tiles of the whole world (OpenStreetMap data, OpenMapTiles
// layers), and free elevation tiles for the hill shading. Neither needs a key.
const STREETS = 'https://tiles.openfreemap.org/planet'
const HEIGHTS = 'https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png'

const GLYPHS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'

const START_ZOOM = 15.4
const PITCH = 60
const BEARING = -18
const FOG_TOP = 20 // metres: the wall of fog round each clearing
const BEACON_TOP = 320 // metres: the quest can be seen from across town
const EMPTY = { type: 'FeatureCollection', features: [] }

// Ground a shade darker than the buildings, so every building stands out of it
const LAND = '#e6d9b8'
const PARK = '#b9db7f'
const WOOD = '#9fca6e'
const WATER = '#6fbde0'
const ROAD = '#ffffff'
const ROAD_EDGE = '#b3a27c'
const BUILDING = '#fcf2da'
const TOWER = '#ffc97a'
const FOG = '#3d4c63'
const FOG_GROUND = 0.55 // unexplored ground is dimmed; the buildings on it stay clear
const REGULAR = ['Noto Sans Regular']
const BOLD = ['Noto Sans Bold']
// every name has a cream halo, so it reads over fog, parks and roads alike
const NAME = { 'text-color': INK, 'text-halo-color': CREAM, 'text-halo-width': 1.6, 'text-halo-blur': 0.2 }
const NAME_TEXT = ['coalesce', ['get', 'name:en'], ['get', 'name']]

function lngLat([lat, lng]) {
  return [lng, lat]
}

/** The whole look, written here so nothing but tiles is fetched. */
function style() {
  return {
    version: 8,
    glyphs: GLYPHS,
    // the sun from the south-west, so each building has a lit side and a shaded one
    light: { anchor: 'viewport', color: '#ffffff', intensity: 0.42, position: [1.4, 225, 35] },
    sources: {
      streets: { type: 'vector', url: STREETS, attribution: '© OpenFreeMap · © OpenMapTiles · © OpenStreetMap contributors' },
      ground: { type: 'raster-dem', tiles: [HEIGHTS], encoding: 'terrarium', tileSize: 256, maxzoom: 13, attribution: 'Terrain: Mapzen, AWS' },
      fog: { type: 'geojson', data: EMPTY },
      wall: { type: 'geojson', data: EMPTY },
      rim: { type: 'geojson', data: EMPTY },
      trail: { type: 'geojson', data: EMPTY },
      route: { type: 'geojson', data: EMPTY },
      edge: { type: 'geojson', data: EMPTY },
      beacon: { type: 'geojson', data: EMPTY },
      me: { type: 'geojson', data: EMPTY },
    },
    sky: {
      'sky-color': '#bfe3f2',
      'horizon-color': CREAM,
      'fog-color': '#e8dcc0',
      'sky-horizon-blend': 0.6,
      'horizon-fog-blend': 0.6,
      'fog-ground-blend': 0.7,
      'atmosphere-blend': 0,
    },
    layers: [
      { id: 'land', type: 'background', paint: { 'background-color': LAND } },
      { id: 'green', type: 'fill', source: 'streets', 'source-layer': 'landcover',
        filter: ['in', ['get', 'class'], ['literal', ['grass', 'wood', 'farmland', 'wetland']]],
        paint: { 'fill-color': ['match', ['get', 'class'], 'wood', WOOD, PARK], 'fill-opacity': 0.75 } },
      { id: 'park', type: 'fill', source: 'streets', 'source-layer': 'park', paint: { 'fill-color': PARK, 'fill-opacity': 0.9 } },
      { id: 'park-edge', type: 'line', source: 'streets', 'source-layer': 'park', paint: { 'line-color': '#9cc565', 'line-width': 1.5 } },
      { id: 'hills', type: 'hillshade', source: 'ground',
        paint: { 'hillshade-shadow-color': INK, 'hillshade-highlight-color': CREAM, 'hillshade-accent-color': '#6d7c5a', 'hillshade-exaggeration': 0.35 } },
      { id: 'water', type: 'fill', source: 'streets', 'source-layer': 'water', paint: { 'fill-color': WATER } },
      { id: 'river', type: 'line', source: 'streets', 'source-layer': 'waterway',
        paint: { 'line-color': WATER, 'line-width': ['interpolate', ['linear'], ['zoom'], 12, 1, 17, 6] } },
      { id: 'road-edge', type: 'line', source: 'streets', 'source-layer': 'transportation',
        filter: ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor', 'service']]],
        layout: { 'line-cap': 'square', 'line-join': 'miter' },
        paint: { 'line-color': ROAD_EDGE,
          'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 12, ['match', ['get', 'class'], ['motorway', 'trunk', 'primary'], 3, 1], 18,
            ['match', ['get', 'class'], ['motorway', 'trunk', 'primary'], 30, ['secondary', 'tertiary'], 22, 12]] } },
      { id: 'road', type: 'line', source: 'streets', 'source-layer': 'transportation',
        filter: ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor', 'service']]],
        layout: { 'line-cap': 'square', 'line-join': 'miter' },
        paint: { 'line-color': ROAD,
          'line-width': ['interpolate', ['exponential', 1.6], ['zoom'], 12, ['match', ['get', 'class'], ['motorway', 'trunk', 'primary'], 1.5, 0.4], 18,
            ['match', ['get', 'class'], ['motorway', 'trunk', 'primary'], 24, ['secondary', 'tertiary'], 17, 8]] } },
      { id: 'path', type: 'line', source: 'streets', 'source-layer': 'transportation', minzoom: 14,
        filter: ['in', ['get', 'class'], ['literal', ['path', 'track']]],
        paint: { 'line-color': '#a08a5e', 'line-width': 1.5, 'line-dasharray': [2, 2] } },
      // the fog: unexplored ground dimmed, the explored ground cut out of it bright
      { id: 'fog', type: 'fill', source: 'fog', paint: { 'fill-color': FOG, 'fill-opacity': FOG_GROUND, 'fill-antialias': false } },
      { id: 'buildings', type: 'fill-extrusion', source: 'streets', 'source-layer': 'building', minzoom: 13,
        paint: {
          'fill-extrusion-color': ['interpolate', ['linear'], ['coalesce', ['get', 'render_height'], 6], 0, BUILDING, 40, BUILDING, 90, TOWER],
          'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 13, 0, 14.5, ['coalesce', ['get', 'render_height'], 6]],
          'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
          'fill-extrusion-opacity': 1,
          'fill-extrusion-vertical-gradient': true,
        } },
      { id: 'me-accuracy', type: 'fill', source: 'me', paint: { 'fill-color': '#3e8ede', 'fill-opacity': 0.18 } },
      // the fog round each clearing rises as a wall, so a clearing reads as a hole in the fog
      { id: 'wall', type: 'fill-extrusion', source: 'wall',
        paint: { 'fill-extrusion-color': FOG, 'fill-extrusion-height': FOG_TOP, 'fill-extrusion-base': 0,
          'fill-extrusion-opacity': 0.8, 'fill-extrusion-vertical-gradient': true } },
      // the frontier: a dashed lime rim along the top of the fog's edge
      { id: 'rim', type: 'fill-extrusion', source: 'rim',
        minzoom: 14.5,
        paint: { 'fill-extrusion-color': LIME, 'fill-extrusion-height': FOG_TOP + 1.5, 'fill-extrusion-base': FOG_TOP - 0.5,
          'fill-extrusion-opacity': 1, 'fill-extrusion-vertical-gradient': false } },
      // the trail between cleared places, floating over the fog
      { id: 'trail', type: 'fill-extrusion', source: 'trail', minzoom: 14.5,
        paint: { 'fill-extrusion-color': ['match', ['get', 'part'], 'under', CREAM, INK],
          'fill-extrusion-height': ['match', ['get', 'part'], 'under', FOG_TOP + 3, FOG_TOP + 4],
          'fill-extrusion-base': ['match', ['get', 'part'], 'under', FOG_TOP + 2, FOG_TOP + 3],
          'fill-extrusion-opacity': 1, 'fill-extrusion-vertical-gradient': false } },
      // zoomed out, the raised rim and trail are too thin to see: flat lines over the fog say the same
      { id: 'edge-far', type: 'line', source: 'edge', maxzoom: 15.5,
        paint: { 'line-color': LIME, 'line-width': 2.5, 'line-dasharray': [2, 1.5],
          'line-opacity': ['interpolate', ['linear'], ['zoom'], 14.5, 1, 15.5, 0] } },
      { id: 'route-under', type: 'line', source: 'route', layout: { 'line-cap': 'square', 'line-join': 'miter' },
        paint: { 'line-color': CREAM, 'line-width': 7, 'line-opacity': ['interpolate', ['linear'], ['zoom'], 14.5, 0.9, 15.5, 0] } },
      { id: 'route', type: 'line', source: 'route', layout: { 'line-cap': 'butt', 'line-join': 'miter' },
        paint: { 'line-color': INK, 'line-width': 3, 'line-dasharray': [1, 2.5],
          'line-opacity': ['interpolate', ['linear'], ['zoom'], 14.5, 1, 15.5, 0] } },
      // your quest: a beacon
      { id: 'beacon', type: 'fill-extrusion', source: 'beacon',
        paint: { 'fill-extrusion-color': CORAL, 'fill-extrusion-height': BEACON_TOP, 'fill-extrusion-base': 0,
          'fill-extrusion-opacity': 0.6, 'fill-extrusion-vertical-gradient': true } },
      // names last, over everything, so the map says where you are even in the fog
      { id: 'water-name', type: 'symbol', source: 'streets', 'source-layer': 'water_name', minzoom: 12,
        layout: { 'text-field': NAME_TEXT, 'text-font': REGULAR, 'text-size': 12, 'symbol-placement': 'point' },
        paint: { ...NAME, 'text-color': '#1f5f80' } },
      { id: 'river-name', type: 'symbol', source: 'streets', 'source-layer': 'waterway', minzoom: 13,
        layout: { 'text-field': NAME_TEXT, 'text-font': REGULAR, 'text-size': 12, 'symbol-placement': 'line', 'text-letter-spacing': 0.15 },
        paint: { ...NAME, 'text-color': '#1f5f80' } },
      { id: 'road-name', type: 'symbol', source: 'streets', 'source-layer': 'transportation_name', minzoom: 14,
        filter: ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor']]],
        layout: { 'text-field': NAME_TEXT, 'text-font': BOLD, 'symbol-placement': 'line', 'text-max-angle': 30,
          'text-size': ['interpolate', ['linear'], ['zoom'], 14, 11, 17, 15] },
        paint: NAME },
      { id: 'park-name', type: 'symbol', source: 'streets', 'source-layer': 'park', minzoom: 13,
        filter: ['has', 'name'],
        layout: { 'text-field': NAME_TEXT, 'text-font': BOLD, 'text-size': 12, 'text-max-width': 8 },
        paint: { ...NAME, 'text-color': '#2f5212' } },
      { id: 'area-name', type: 'symbol', source: 'streets', 'source-layer': 'place', minzoom: 11, maxzoom: 16,
        filter: ['in', ['get', 'class'], ['literal', ['suburb', 'neighbourhood', 'quarter']]],
        layout: { 'text-field': NAME_TEXT, 'text-font': BOLD, 'text-transform': 'uppercase', 'text-letter-spacing': 0.12,
          'text-size': ['interpolate', ['linear'], ['zoom'], 11, 10, 15, 13], 'text-max-width': 9 },
        paint: { ...NAME, 'text-color': '#3b4654' } },
    ],
  }
}

/** The rim and the trail as GeoJSON, from the explored edges and the route. The rim sits on the fog's wall. */
function rimOf(edges) {
  return polygons(edges.flatMap((ring) => dashes(ring, 9, 26, 16)))
}

function trailFeatures(route) {
  if (route.length < 2) return EMPTY
  const line = route.map(lngLat)
  const under = polygons(dashes(line, 22, 1e9), { part: 'under' }).features
  const over = polygons(dashes(line, 9, 24, 34), { part: 'over' }).features
  return { type: 'FeatureCollection', features: [...under, ...over] }
}

export default function World3D({ ref, tiles, spots, questPlace, picked, fresh, onPick, me, first, onStreets, onFail }) {
  const box = useRef(null)
  const world = useRef(null) // { map, ready, markers, meMarker, born, frame }

  // the map itself, once
  useEffect(() => {
    let map
    try {
      map = new maplibregl.Map({
        container: box.current,
        style: style(),
        center: lngLat(first),
        zoom: START_ZOOM,
        pitch: PITCH,
        bearing: BEARING,
        minZoom: 11,
        maxPitch: 72,
        maxBounds: [[-81.7, 42.7], [-80.8, 43.25]],
        attributionControl: { compact: true },
        fadeDuration: 0,
        canvasContextAttributes: { antialias: true }, // smooth building edges
      })
    } catch (error) {
      onFail(error)
      return undefined
    }
    const here = { map, ready: false, markers: [], meMarker: null, born: new Map(), frame: 0, draw: null }
    world.current = here
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right')
    map.on('webglcontextlost', () => onFail(new Error('the 3D map lost its drawing surface')))
    let loaded = false
    map.on('sourcedata', (event) => {
      if (event.sourceId === 'streets' && event.isSourceLoaded && !loaded) {
        loaded = true
        onStreets('on')
      }
    })
    map.on('error', (event) => {
      // the street tiles could not be fetched: the fog and the pins still work
      if (!loaded && (event.sourceId === 'streets' || /openfreemap/.test(String(event.error?.url ?? event.error?.message ?? '')))) onStreets('off')
    })
    map.on('load', () => {
      // the credits start folded into their (i) button, as on the flat map's small line
      box.current?.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show')
      here.ready = true
      here.draw?.()
    })
    const watch = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => map.resize())
    watch?.observe(box.current)
    return () => {
      watch?.disconnect()
      cancelAnimationFrame(here.frame)
      map.remove()
      world.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- made once; the effects below keep it current
  }, [])

  useImperativeHandle(ref, () => ({
    goTo(at, zoom = null) {
      const map = world.current?.map
      if (!map || !at) return
      const still = stillPlease()
      map.easeTo({ center: lngLat(at), zoom: zoom == null ? map.getZoom() : Math.max(map.getZoom(), zoom + 0.6),
        pitch: Math.max(map.getPitch(), 45), duration: still ? 0 : 1100 })
    },
    fit(points) {
      const map = world.current?.map
      if (!map || !points.length) return
      const bounds = new maplibregl.LngLatBounds(lngLat(points[0]), lngLat(points[0]))
      for (const point of points) bounds.extend(lngLat(point))
      map.fitBounds(bounds, { padding: 60, maxZoom: 15.5, pitch: 50, bearing: map.getBearing(), duration: stillPlease() ? 0 : 1200 })
    },
  }), [])

  // the fog, the rim, the trail, the beacon and the pins, whenever the state changes
  const signature = JSON.stringify([tiles.map((t) => [t.place, t.cleared, t.cleared_at ?? null]), questPlace, fresh, picked])
  useEffect(() => {
    const here = world.current
    if (!here) return
    const { map } = here

    // pins: the same marks as the flat map
    for (const marker of here.markers) marker.remove()
    here.markers = tiles.map((tile) => {
      const quest = !tile.cleared && questPlace === tile.place
      const el = document.createElement('div')
      el.className = pinClass(tile, { here: quest, fresh: fresh.includes(tile.place), picked: picked === tile.place })
      el.innerHTML = pinHtml(tile, quest)
      el.tabIndex = 0
      el.setAttribute('role', 'button')
      el.setAttribute('aria-label', pinLabel(tile, quest))
      el.setAttribute('aria-pressed', String(picked === tile.place))
      el.addEventListener('click', (event) => {
        event.stopPropagation()
        // in 3D a tap also flies down to the place, so its clearing (or its fog) is seen up close
        if (picked !== tile.place) {
          map.easeTo({ center: lngLat(spots.get(tile.place)), zoom: Math.max(map.getZoom(), 15.8), pitch: Math.max(map.getPitch(), 55),
            duration: stillPlease() ? 0 : 1100 })
        }
        onPick(tile.place)
      })
      el.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onPick(tile.place)
        }
      })
      return new maplibregl.Marker({ element: el, anchor: 'top-left' }).setLngLat(lngLat(spots.get(tile.place))).addTo(map)
    })

    // a place that has just cleared opens up from nothing; the rest are open
    const now = performance.now()
    const still = stillPlease()
    const born = new Map()
    for (const place of fresh) if (!still) born.set(place, here.born.get(place) ?? now)
    here.born = born
    const clearings = tiles.filter((tile) => tile.cleared).map((tile) => ({ place: tile.place, at: spots.get(tile.place) }))
    const route = trailOf(tiles, spots)
    const questAt = questPlace && !tiles.find((t) => t.place === questPlace)?.cleared ? spots.get(questPlace) : null

    here.draw = () => {
      if (!here.ready) return
      const t = performance.now()
      let moving = false
      const open = clearings.map(({ place, at }) => {
        const start = here.born.get(place)
        const amount = start == null ? 1 : opening(t - start)
        if (amount < 1) moving = true
        return { at, open: amount }
      })
      const { fog, edges } = fogShape(open)
      map.getSource('fog').setData({ type: 'Feature', properties: {}, geometry: fog })
      map.getSource('rim').setData(rimOf(edges))
      map.getSource('wall').setData(polygons(edges.flatMap((ring) => dashes(ring, 8, 1e9))))
      map.getSource('trail').setData(trailFeatures(route))
      map.getSource('route').setData(route.length > 1
        ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: route.map(lngLat) } } : EMPTY)
      map.getSource('edge').setData({ type: 'Feature', properties: {}, geometry: { type: 'MultiLineString', coordinates: edges } })
      map.getSource('beacon').setData(questAt ? polygons([circle(questAt, 16, 24)]) : EMPTY)
      cancelAnimationFrame(here.frame)
      here.frame = moving ? requestAnimationFrame(here.draw) : 0
    }
    here.draw()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `signature` is everything these layers draw
  }, [signature])

  // you
  useEffect(() => {
    const here = world.current
    if (!here) return
    here.meMarker?.remove()
    here.meMarker = null
    const setMe = () => here.ready && here.map.getSource('me').setData(me.at ? polygons([circle(me.at, me.accuracy ?? 30, 32)]) : EMPTY)
    if (here.ready) setMe()
    else here.map.once('load', setMe)
    if (!me.at) return
    const el = document.createElement('div')
    el.className = 'me'
    el.title = 'You are here'
    el.innerHTML = '<span></span>'
    here.meMarker = new maplibregl.Marker({ element: el }).setLngLat(lngLat(me.at)).addTo(here.map)
  }, [me.at, me.accuracy])

  return <div className="world-map world-3d" ref={box} aria-label="Map of London, Ontario, in 3D" />
}

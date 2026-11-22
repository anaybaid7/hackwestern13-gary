// The 3D map: its shapes, the choice between 3D and flat, and the 3D map's
// pins, with a stand-in for MapLibre (the test page has no WebGL).
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import example from '../../../contract/examples/state.json'
import story from '../../../contract/examples/story.json'
import { CLEAR_METRES, circle, dashes, fogShape, opening } from '../map/shapes.js'
import { can3d, forgetWebgl, savedLook, saveLook } from '../map/look.js'
import { metresBetween } from '../places.js'

// A stand-in for MapLibre: enough of a map to draw pins and take data.
const made = vi.hoisted(() => ({ maps: [], fail: false }))
vi.mock('maplibre-gl', () => {
  class Map {
    constructor(options) {
      if (made.fail) throw new Error('no WebGL here')
      this.options = options
      this.handlers = {}
      this.data = {}
      this.container = options.container
      this.camera = { zoom: options.zoom, pitch: options.pitch, bearing: options.bearing, center: options.center }
      made.maps.push(this)
      queueMicrotask(() => this.fire('load'))
    }
    on(name, fn) {
      ;(this.handlers[name] ??= []).push(fn)
      return this
    }
    once(name, fn) {
      return this.on(name, fn)
    }
    fire(name, event = {}) {
      for (const fn of this.handlers[name] ?? []) fn(event)
    }
    addControl() {}
    getSource(id) {
      return { setData: (data) => (this.data[id] = data) }
    }
    getZoom() {
      return this.camera.zoom
    }
    getPitch() {
      return this.camera.pitch
    }
    getBearing() {
      return this.camera.bearing
    }
    easeTo(to) {
      Object.assign(this.camera, to)
    }
    fitBounds(bounds, options) {
      this.fitted = { bounds, options }
    }
    resize() {}
    remove() {
      this.removed = true
    }
  }
  class Marker {
    constructor({ element }) {
      this.element = element
    }
    setLngLat(at) {
      this.at = at
      return this
    }
    addTo(map) {
      map.container.appendChild(this.element)
      return this
    }
    remove() {
      this.element.remove()
    }
  }
  class LngLatBounds {
    constructor(a, b) {
      this.points = [a, b]
    }
    extend(p) {
      this.points.push(p)
    }
  }
  const lib = { Map, Marker, LngLatBounds, NavigationControl: class {} }
  return { default: lib, ...lib }
})

// MapScreen asks look.js whether to draw in 3D; these tests say yes unless told otherwise.
const webgl = vi.hoisted(() => ({ ok: true }))
vi.mock('../map/look.js', async (real) => {
  const actual = await real()
  return { ...actual, can3d: () => webgl.ok }
})

const { default: MapScreen } = await import('./MapScreen.jsx')

const NO_FLASH = { find: null, stageUp: false, cleared: [], rankUp: null, messages: [] }
const step = (n) => story.steps[n].state

beforeEach(() => {
  made.maps.length = 0
  made.fail = false
  webgl.ok = true
  window.localStorage.clear()
})
afterEach(cleanup)

describe('3D map shapes', () => {
  test('a clearing is a closed circle CLEAR_METRES across from its centre', () => {
    const at = [42.9862, -81.2563]
    const ring = circle(at, CLEAR_METRES)
    expect(ring[0]).toEqual(ring[ring.length - 1])
    for (const [lng, lat] of ring) expect(Math.abs(metresBetween(at, [lat, lng]) - CLEAR_METRES)).toBeLessThan(2)
  })

  test('no clearings: fog everywhere; clearings that overlap make one hole, apart they make two', () => {
    expect(fogShape([]).edges).toEqual([])
    expect(fogShape([]).fog.coordinates).toHaveLength(1)
    const near = fogShape([{ at: [42.99, -81.25] }, { at: [42.9925, -81.25] }]) // about 280 m apart
    expect(near.edges).toHaveLength(1)
    const apart = fogShape([{ at: [42.99, -81.25] }, { at: [43.02, -81.25] }])
    expect(apart.edges).toHaveLength(2)
    expect(apart.fog.coordinates[0]).toHaveLength(3) // the fog: its outline and two holes
  })

  test('a fresh clearing opens from nothing, bursting then settling', () => {
    expect(opening(0)).toBe(0)
    expect(opening(700)).toBeGreaterThan(0.8)
    expect(opening(1400)).toBe(1)
    expect(opening(99999)).toBe(1)
    expect(fogShape([{ at: [42.99, -81.25], open: 0 }]).edges).toEqual([]) // not open yet: no hole
  })

  test('dashes: drawn and left out in turn, along the whole line', () => {
    const line = [[-81.25, 42.99], [-81.25, 42.99 + 1000 / 111320]] // 1 km north
    expect(dashes(line, 10, 1e9)).toHaveLength(1)
    const quads = dashes(line, 10, 30, 20) // 50 m a dash and its gap: 20 dashes
    expect(quads).toHaveLength(20)
    for (const quad of quads) expect(quad[0]).toEqual(quad[4])
  })
})

describe('which map', () => {
  test('3D unless you chose flat; the choice is kept in this browser', () => {
    expect(savedLook()).toBe('3d')
    saveLook('flat')
    expect(savedLook()).toBe('flat')
  })

  test('a page with no WebGL (like this test page) cannot draw 3D', async () => {
    const real = await vi.importActual('../map/look.js')
    real.forgetWebgl()
    expect(real.can3d()).toBe(false)
    forgetWebgl() // the mocked module's copy, untouched
  })

  test('no WebGL: the flat map, and no 3D switch', () => {
    webgl.ok = false
    const { container } = render(<MapScreen map={example.map} flash={NO_FLASH} quest={example.quest} />)
    expect(container.querySelector('.leaflet-tile-pane')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Show the map in 3D' })).toBeNull()
  })

  test('the 3D map draws by default, and the switch goes to flat and back', async () => {
    const { container } = render(<MapScreen map={example.map} flash={NO_FLASH} quest={example.quest} />)
    await waitFor(() => expect(container.querySelector('.world-3d')).toBeTruthy())
    expect(container.querySelector('.leaflet-tile-pane')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Show the flat map' }))
    expect(container.querySelector('.leaflet-tile-pane')).toBeTruthy()
    expect(savedLook()).toBe('flat')
    fireEvent.click(screen.getByRole('button', { name: 'Show the map in 3D' }))
    await waitFor(() => expect(container.querySelector('.world-3d')).toBeTruthy())
  })

  test('if the 3D map will not start, the flat map is drawn instead', async () => {
    made.fail = true
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { container } = render(<MapScreen map={example.map} flash={NO_FLASH} />)
    await waitFor(() => expect(container.querySelector('.leaflet-tile-pane')).toBeTruthy())
    expect(screen.getByText('1/3 uncovered')).toBeTruthy()
  })
})

describe('the 3D map', () => {
  async function draw(props) {
    const view = render(<MapScreen flash={NO_FLASH} {...props} />)
    await waitFor(() => expect(made.maps.length).toBe(1))
    const map = made.maps[0]
    await act(async () => {}) // its "load"
    return { ...view, map }
  }

  test('the same pins as the flat map, and a tap flies there and shows the place', async () => {
    const { container, map } = await draw({ map: example.map, quest: example.quest })
    expect(container.querySelectorAll('.tile').length).toBe(3)
    expect(container.querySelector('.tile.cleared .tile-name').textContent).toBe('Harris Park')
    expect(screen.getByRole('button', { name: 'Fog. Your quest is here' })).toBeTruthy()
    expect(map.options.pitch).toBeGreaterThan(40) // tilted: it is 3D
    fireEvent.click(screen.getByRole('button', { name: 'Harris Park, uncovered' }))
    expect(screen.getByRole('heading', { name: 'Harris Park' })).toBeTruthy()
    expect(map.camera.center).toEqual([-81.2563, 42.9862])
    expect(map.camera.zoom).toBeGreaterThanOrEqual(15.8)
  })

  test('the fog has a hole for each cleared place, and the quest has a beacon', async () => {
    const { map } = await draw({ map: example.map, quest: example.quest })
    expect(map.data.fog.geometry.coordinates[0]).toHaveLength(2) // the fog's outline and Harris Park
    expect(map.data.beacon.features).toHaveLength(1)
    expect(map.data.rim.features.length).toBeGreaterThan(0)
  })

  test('the trail joins cleared places; "All places" fits them all', async () => {
    const { map } = await draw({ map: step(9).map, quest: step(9).quest })
    expect(map.data.route.geometry.coordinates.length).toBe(step(9).map.filter((t) => t.cleared).length)
    expect(map.data.trail.features.length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'All places' }))
    expect(map.fitted.bounds.points.length).toBeGreaterThan(step(9).map.length)
  })

  test('a pin can be reached and opened from the keyboard', async () => {
    await draw({ map: example.map })
    const pin = screen.getByRole('button', { name: 'Harris Park, uncovered' })
    expect(pin.tabIndex).toBe(0)
    fireEvent.keyDown(pin, { key: 'Enter' })
    expect(screen.getByRole('heading', { name: 'Harris Park' })).toBeTruthy()
  })

  test('street tiles that cannot be fetched are said plainly; the fog and pins stay', async () => {
    const { map } = await draw({ map: example.map })
    act(() => map.fire('error', { sourceId: 'streets', error: new Error('offline') }))
    expect(screen.getByText(/No street map right now/)).toBeTruthy()
  })
})

describe('Walk there', () => {
  test('a real place gets walking directions with only the place in the link; a made-up spot gets none', () => {
    webgl.ok = false
    const nowhere = { place: 'Nowhere Park', quest_id: 'q-x', cleared: true, finds: [] }
    render(<MapScreen map={[...example.map, nowhere]} flash={NO_FLASH} />)
    fireEvent.click(screen.getByRole('button', { name: 'Harris Park, uncovered' }))
    const link = screen.getByRole('link', { name: /Walk there/ })
    expect(link.getAttribute('href')).toBe('https://www.google.com/maps/dir/?api=1&destination=42.9862,-81.2563&travelmode=walking')
    expect(link.getAttribute('href')).not.toMatch(/origin/)
    fireEvent.click(screen.getByRole('button', { name: 'Nowhere Park, uncovered' }))
    expect(screen.queryByRole('link', { name: /Walk there/ })).toBeNull()
  })
})

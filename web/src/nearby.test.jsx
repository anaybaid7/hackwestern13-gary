// Explorers nearby: off unless you say yes, and gone when you say no.
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { Shell } from './App.jsx'
import MapScreen from './screens/MapScreen.jsx'
import Settings from './screens/Settings.jsx'
import { EVERY_MS, deviceId, nearbyLine, readNearby, writeNearby } from './nearby.js'
import { createMock } from './services/mock.js'
import exampleState from '../../contract/examples/state.json'
import exampleWellness from '../../contract/examples/wellness.json'

const HERE = { latitude: 42.999, longitude: -81.2585, accuracy: 20 }

beforeEach(() => {
  window.localStorage.clear()
  // the browser knows where you are
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: { watchPosition: (ok) => (ok({ coords: HERE }), 1), clearWatch: () => {} },
  })
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  window.localStorage.clear()
})

function fakeService(nearby = []) {
  return {
    mode: 'live',
    shareSpot: vi.fn(async () => ({ nearby, range_m: 2000 })),
    leaveNearby: vi.fn(async () => ({ ok: true })),
    getWellness: vi.fn(async () => exampleWellness),
    postMood: vi.fn(async () => ({ ok: true })),
  }
}

const mapProps = { map: exampleState.map, flash: { cleared: [] }, quest: exampleState.quest }

test('it is off until you turn it on: the map sends nothing about where you are', async () => {
  expect(readNearby()).toBe(false)
  const service = fakeService()
  render(<MapScreen {...mapProps} service={service} />)
  await act(async () => {})
  expect(service.shareSpot).not.toHaveBeenCalled()
  expect(screen.queryByText(/explorers? nearby/i)).toBeNull()
})

test('switched on, the map tells the backend where you are and draws the others, again and again', async () => {
  vi.useFakeTimers()
  writeNearby(true)
  const others = [
    { tag: '3a9f01c2', lat: 43.001, lon: -81.26, same_quest: true, metres: 250, seconds_ago: 2 },
    { tag: 'b71e44d0', lat: 43.004, lon: -81.262, same_quest: false, metres: 600, seconds_ago: 5 },
  ]
  const service = fakeService(others)
  const { container } = render(<MapScreen {...mapProps} service={service} />)
  await act(async () => {})
  expect(service.shareSpot).toHaveBeenCalledTimes(1)
  const sent = service.shareSpot.mock.calls[0][0]
  expect(sent).toEqual({ id: deviceId(), lat: HERE.latitude, lon: HERE.longitude, quest_id: exampleState.quest.id })
  expect(sent.id).toMatch(/^[0-9a-f]{32}$/) // a random id from this device: no name, no account
  expect(screen.getByText('2 explorers nearby, 1 on your quest.')).toBeTruthy()
  expect(container.querySelectorAll('.other').length).toBe(2)
  expect(container.querySelectorAll('.other.same').length).toBe(1)
  expect(container.querySelector('.other').getAttribute('title')).toMatch(/Goat, on your quest$/) // a goat name, never a person's
  expect(container.querySelector('.other b').textContent).toMatch(/^[A-Z][a-z]+ [A-Z][a-z]+$/) // and it is written under the dot
  expect(screen.queryByText(/Showcase/)).toBeNull() // the usual 100 m rounding
  await act(async () => vi.advanceTimersByTime(EVERY_MS + 50))
  expect(service.shareSpot).toHaveBeenCalledTimes(2) // live: they move, so you ask again
})

test('the switch is in Settings; turning it off takes your dot off the map at once', async () => {
  const service = fakeService()
  render(<Settings service={service} stamp="1" status="live" />)
  const box = screen.getByRole('checkbox', { name: /Show me to explorers nearby/ })
  expect(box.checked).toBe(false)
  expect(screen.getByText(/rounded to about 100 m, with no name, and is never\s+kept \(a showcase server may show exact/)).toBeTruthy()
  fireEvent.click(box)
  expect(readNearby()).toBe(true)
  expect(service.leaveNearby).not.toHaveBeenCalled()
  fireEvent.click(box)
  expect(readNearby()).toBe(false)
  expect(service.leaveNearby).toHaveBeenCalledWith(deviceId())
})

test('the line under the map counts honestly', () => {
  expect(nearbyLine([])).toBe('No other explorers nearby right now.')
  expect(nearbyLine([{ same_quest: false }])).toBe('1 explorer nearby.')
  expect(nearbyLine([{ same_quest: true }, { same_quest: true }, { same_quest: false }])).toBe('3 explorers nearby, 2 on your quest.')
})

test("the demo story has explorers too, and they move", async () => {
  const service = createMock()
  const first = await service.shareSpot({ lat: 43, lon: -81.25, quest_id: 'q' })
  expect(first.demo).toBe(true)
  expect(first.nearby.length).toBe(3)
  expect(first.nearby.filter((o) => o.same_quest).length).toBe(1)
  const spy = vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 60000)
  const later = await service.shareSpot({ lat: 43, lon: -81.25, quest_id: 'q' })
  spy.mockRestore()
  expect(later.nearby.map((o) => `${o.lat},${o.lon}`)).not.toEqual(first.nearby.map((o) => `${o.lat},${o.lon}`))
})

test('on a showcase server the map says positions are exact', async () => {
  writeNearby(true)
  const service = fakeService([{ tag: '3a9f01c2', lat: 43.00961, lon: -81.27374, same_quest: false, metres: 6, seconds_ago: 1 }])
  service.shareSpot = vi.fn(async () => ({ nearby: [{ tag: '3a9f01c2', lat: 43.00961, lon: -81.27374, same_quest: false, metres: 6, seconds_ago: 1 }], range_m: 2000, rounded_m: 1.1 }))
  render(<MapScreen {...mapProps} service={service} />)
  await act(async () => {})
  expect(screen.getByText(/1 explorer nearby\. Showcase: exact positions\./)).toBeTruthy()
})

test('coming back from Auth0 finishes the sign-in at once and opens Settings', async () => {
  window.history.replaceState(null, '', '/?code=abc&state=xyz')
  const service = {
    ...fakeService(),
    now: () => new Date('2026-11-22T06:00:00Z'),
    getState: vi.fn(async () => exampleState),
    account: vi.fn(async () => {
      window.history.replaceState(null, '', '/#settings') // what the sign-in code does when it is done
      return { enabled: true, signedIn: true, signOut: () => {} }
    }),
    getMe: vi.fn(async () => ({ signed_in: true, fingerprint: '3a9f01c2aaaaaaaa', paired: false, permissions: [] })),
  }
  render(<Shell service={service} askCheckIn={false} />)
  expect(service.account).toHaveBeenCalledTimes(1) // before Settings was ever opened
  expect(await screen.findByText('Signed in')).toBeTruthy()
  window.history.replaceState(null, '', '/')
})

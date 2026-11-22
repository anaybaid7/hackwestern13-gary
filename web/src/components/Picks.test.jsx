// Picks for you: a TinyFish agent's places, on the home screen.
import { afterEach, expect, test, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Picks from './Picks.jsx'
import { nearestPlace } from '../places.js'

afterEach(cleanup)

const PICK = {
  place: 'Sifton Bog',
  quest: { id: 'q-2026-11-21-sifton-bog', title: 'Find a duck at Sifton Bog', source_url: 'https://www.londontourism.ca/hiking', source: 'tinyfish' },
  why: 'Ducks on the quiet bog.',
  reasons: ['New to you', 'You like finding ducks'],
}
const READY = { ready: true, job: null, picks: [], previous: [] }

function service(views, more = {}) {
  const queue = [...views]
  return {
    getPicks: vi.fn(async () => (queue.length > 1 ? queue.shift() : queue[0])),
    askPicks: vi.fn(async () => ({ started: true })),
    takePick: vi.fn(async () => ({ state: { quest: PICK.quest } })),
    ...more,
  }
}

test('shows the agent\'s picks with the page\'s own words, and a pick can be taken', async () => {
  const svc = service([{ ...READY, picks: [PICK], picked_at: '2026-11-21T15:00:00Z' }])
  const onTaken = vi.fn()
  render(<Picks service={svc} onTaken={onTaken} />)
  expect(await screen.findByText('Find a duck at Sifton Bog')).toBeTruthy()
  expect(screen.getByText(/Ducks on the quiet bog/)).toBeTruthy()
  expect(screen.getByRole('link', { name: 'londontourism.ca' }).getAttribute('href')).toBe(PICK.quest.source_url)
  expect(screen.getByText('You like finding ducks')).toBeTruthy()
  expect(screen.getByText(/Found by a TinyFish agent on live pages/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Take it' }))
  await waitFor(() => expect(onTaken).toHaveBeenCalledWith({ quest: PICK.quest }))
  expect(svc.takePick).toHaveBeenCalledWith(PICK.quest.id)
})

test('asking sends only the nearest known place, then follows the run until it is done', async () => {
  const svc = service([READY, { ...READY, job: { status: 'running' } }, { ...READY, job: { status: 'ok' }, picks: [PICK] }])
  const tiles = [{ place: 'Harris Park', lat: 42.9862, lng: -81.2563 }, { place: 'Far Away', lat: 43.2, lng: -81.0 }]
  render(<Picks service={svc} tiles={tiles} pollMs={20} locate={async () => [42.9849, -81.2453]} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Find places for me' }))
  await waitFor(() => expect(svc.askPicks).toHaveBeenCalledWith('Harris Park'))
  expect(await screen.findByText(/reading live London pages/)).toBeTruthy()
  expect(await screen.findByText('Find a duck at Sifton Bog')).toBeTruthy()
})

test('a failed request is said plainly, with the last good picks still shown', async () => {
  render(<Picks service={service([{ ...READY, picks: [PICK], cached: true, error: 'Tourism London: no answer after 150 seconds' }])} />)
  expect(await screen.findByText(/The last request did not work: Tourism London: no answer/)).toBeTruthy()
  expect(screen.getByText(/Showing the last good picks/)).toBeTruthy()
})

test('nothing shows when the server has no TinyFish key, or the service has no picks', async () => {
  const svc = service([{ ready: false, job: null, picks: [], previous: [] }])
  const { container } = render(<Picks service={svc} />)
  await act(async () => {})
  expect(svc.getPicks).toHaveBeenCalled()
  expect(container.innerHTML).toBe('')
  const old = render(<Picks service={{ getState: vi.fn() }} />)
  expect(old.container.innerHTML).toBe('')
})

test('the nearest known place, only within reach', () => {
  const tiles = [{ place: 'Harris Park', lat: 42.9862, lng: -81.2563 }, { place: 'No position' }]
  expect(nearestPlace([42.9849, -81.2453], tiles)).toBe('Harris Park')
  expect(nearestPlace([43.3, -80.5], tiles)).toBe(null)
  expect(nearestPlace(null, tiles)).toBe(null)
})

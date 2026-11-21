// Meet Gary: the walkthrough a new person sees first.
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App, { Shell } from '../App.jsx'
import Welcome, { garySays, readMet, writeMet } from './Welcome.jsx'
import exampleState from '../../../contract/examples/state.json'
import exampleWellness from '../../../contract/examples/wellness.json'
import { writeSound } from '../sound.js'

beforeEach(() => {
  window.localStorage.clear()
  writeSound(false) // jsdom cannot play audio
})
afterEach(() => {
  cleanup()
  window.localStorage.clear()
})

const click = (name) => fireEvent.click(screen.getByRole('button', { name }))
const meter = (name) => screen.getByLabelText(new RegExp(`^${name}:`)).getAttribute('aria-label')

function fakeService() {
  return {
    mode: 'live',
    now: () => new Date('2026-11-21T06:00:00Z'),
    getState: vi.fn(async () => exampleState),
    getWellness: vi.fn(async () => exampleWellness),
    postMood: vi.fn(async () => ({ ok: true })),
  }
}

test('five beats, one move each: wake him, sniff, pick a quest, say how you feel, go', () => {
  const onDone = vi.fn()
  render(<Welcome onDone={onDone} />)
  // he is asleep until you press his button, like the real one
  expect(screen.getByAltText(/napping/)).toBeTruthy()
  expect(screen.getByLabelText('Step 1 of 5')).toBeTruthy()
  click('Press to wake him')
  expect(screen.getByText(/I'm Gary, your pocket goat/)).toBeTruthy()
  expect(screen.getByText(/move more, explore more/)).toBeTruthy()
  expect(screen.queryByAltText(/napping/)).toBeNull()
  expect([meter('Adventure'), meter('Health')]).toEqual(['Adventure: 0 of 2', 'Health: 0 of 2'])

  click('Next')
  click('duck')
  expect(screen.getByText(/A duck! New find, \+10 XP/)).toBeTruthy()
  expect(meter('Adventure')).toBe('Adventure: 1 of 2') // a sniff is adventure

  click('Next')
  click(/15 min/)
  expect(screen.getByText(/15 minutes it is/)).toBeTruthy()
  // a quest is a walk: it counts for both sides
  expect([meter('Adventure'), meter('Health')]).toEqual(['Adventure: 2 of 2', 'Health: 1 of 2'])

  click('Next')
  click('4: Good')
  expect(screen.getByText(/Only you see it/)).toBeTruthy()
  expect(screen.getByText('Just practice: nothing was saved.')).toBeTruthy()
  expect(meter('Health')).toBe('Health: 2 of 2')

  click('Next')
  expect(screen.getByText(/No streaks, no guilt/)).toBeTruthy()
  expect(readMet()).toBe(false) // not until you finish
  click("Let's go")
  expect(onDone).toHaveBeenCalledTimes(1)
  expect(readMet()).toBe(true)
})

test('Skip leaves at once and is remembered too', () => {
  const onDone = vi.fn()
  render(<Welcome onDone={onDone} />)
  click('Skip')
  expect(onDone).toHaveBeenCalledTimes(1)
  expect(readMet()).toBe(true)
})

test('the whole hello is short enough to read in half a minute', () => {
  const said = [
    garySays('wake', true), garySays('sniff'), garySays('sniff', 'duck'), garySays('quest'), garySays('quest', 15),
    garySays('feel'), garySays('feel', 4), garySays('go'),
  ]
  const words = said.join(' ').split(/\s+/).length
  expect(words).toBeLessThanOrEqual(100) // about 20 seconds at an easy reading pace, plus nine taps
  expect(said.join(' ')).not.toMatch(/calorie|weight|steps goal|streak[^s]/i) // a partner, not a coach
})

test('a new person meets Gary before the home screen; someone he knows goes straight in', async () => {
  const service = fakeService()
  const first = render(<App service={service} />)
  expect(screen.getByRole('region', { name: 'Meet Gary' })).toBeTruthy()
  expect(service.postMood).not.toHaveBeenCalled()
  click('Skip')
  await screen.findByText('Scrambler') // the home screen
  // he asked how you feel in the hello, so the check-in does not pop up straight after
  expect(screen.queryByRole('dialog')).toBeNull()
  first.unmount()

  render(<App service={fakeService()} />)
  expect(screen.queryByRole('region', { name: 'Meet Gary' })).toBeNull()
})

test('Settings can bring the hello back', async () => {
  writeMet(true)
  render(<Shell service={fakeService()} askCheckIn={false} />)
  await screen.findByText('Scrambler')
  fireEvent.click(screen.getByRole('button', { name: /settings/i }))
  click('Meet Gary again')
  expect(screen.getByRole('region', { name: 'Meet Gary' })).toBeTruthy()
  click('Skip')
  await screen.findByText('Meet Gary again') // back where you were
})

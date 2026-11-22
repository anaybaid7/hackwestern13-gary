// Meet Gary: the walkthrough a new person sees first.
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import App, { Shell } from '../App.jsx'
import Welcome, { LINES, TARGETS, clipsFor, garySays, readMet, writeMet } from './Welcome.jsx'
import exampleState from '../../../contract/examples/state.json'
import exampleWellness from '../../../contract/examples/wellness.json'
import { VOICE, writeSound } from '../sound.js'

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

test('five beats: wake him, sniff through his eye, pick a walk, say how you feel, go', () => {
  const onDone = vi.fn()
  const { container } = render(<Welcome onDone={onDone} />)
  // he is asleep indoors until you press his button, like the real one
  expect(screen.getByAltText(/napping/)).toBeTruthy()
  expect(container.querySelector('.welcome-stage.inside')).toBeTruthy()
  expect(screen.getByLabelText('Step 1 of 5')).toBeTruthy()
  click('Press to wake him')
  // awake, he is outside, and says that is where he belongs
  expect(screen.getByText(/I belong outside: trails, parks, hills/)).toBeTruthy()
  expect(container.querySelector('.welcome-stage.outside .welcome-scene')).toBeTruthy()
  expect(screen.queryByAltText(/napping/)).toBeNull()
  expect([meter('Adventure'), meter('Health')]).toEqual(['Adventure: 0 of 2', 'Health: 0 of 2'])

  click('Next')
  // his eye is on the first thing; pressing the button sniffs what it is on
  expect(container.querySelector('.welcome-reticle.locked')).toBeNull()
  click('Sniff!')
  expect(screen.getByText("That's a duck! Ooh, a new one for the journal!")).toBeTruthy()
  expect(container.querySelector('.welcome-reticle.locked').textContent).toBe('duck')
  expect(container.querySelector('.welcome-flash')).toBeTruthy() // the shutter
  expect(meter('Adventure')).toBe('Adventure: 1 of 2') // a sniff is adventure

  click('Next')
  // a foggy map with two real trails; the short walk lifts the fog it passes, not all of it
  expect(container.querySelectorAll('.welcome-fog').length).toBe(16)
  expect(container.querySelectorAll('.welcome-fog.lifting').length).toBe(0)
  click(/15 min/)
  expect(container.querySelectorAll('.welcome-fog.lifting').length).toBe(8)
  expect(container.querySelector('.welcome-walker.walking').style.left).toBe('33%') // Gary walks there, beside the pin
  expect(screen.getByText('Off we go. Every walk lifts the fog.')).toBeTruthy()
  // a quest is a walk: it counts for both sides
  expect([meter('Adventure'), meter('Health')]).toEqual(['Adventure: 2 of 2', 'Health: 1 of 2'])

  click('Next')
  click('4: Good')
  expect(screen.getByText(/Only you see it/)).toBeTruthy()
  expect(screen.getByText(/Just practice: nothing was saved/)).toBeTruthy()
  expect(meter('Health')).toBe('Health: 2 of 2')

  click('Next')
  expect(screen.getByText(/No streaks, no guilt/)).toBeTruthy()
  expect(readMet()).toBe(false) // not until you finish
  click("Let's go")
  expect(onDone).toHaveBeenCalledTimes(1)
  expect(readMet()).toBe(true)
})

test("Gary's eye wanders, and the long walk lifts all the fog", () => {
  vi.useFakeTimers()
  try {
    const { container } = render(<Welcome onDone={() => {}} />)
    click('Press to wake him')
    click('Next')
    act(() => vi.advanceTimersByTime(1150)) // his eye has moved on to the tree
    click('Sniff!')
    expect(screen.getByText("That's a tree! Ooh, a new one for the journal!")).toBeTruthy()
    click('Next')
    click(/40 min/)
    expect(container.querySelectorAll('.welcome-fog.lifting').length).toBe(16)
  } finally {
    vi.useRealTimers()
  }
})

test('Skip leaves at once and is remembered too', () => {
  const onDone = vi.fn()
  render(<Welcome onDone={onDone} />)
  click('Skip')
  expect(onDone).toHaveBeenCalledTimes(1)
  expect(readMet()).toBe(true)
})

test('the whole hello is short enough to hear in half a minute, and is about going outside', () => {
  const said = [
    garySays('wake', true), garySays('sniff'), garySays('sniff', 'duck'), garySays('quest'), garySays('quest', 15),
    garySays('feel'), garySays('feel', 4), garySays('go'),
  ].join(' ')
  expect(said.split(/\s+/).length).toBeLessThanOrEqual(90)
  expect(said).toMatch(/outside/)
  expect(said).toMatch(/trails/)
  expect(said).toMatch(/walk/)
  expect(said).not.toMatch(/calorie|weight|steps goal/i) // a partner, not a coach
})

test('every line has a spoken clip, with the same words the voice script sends to ElevenLabs', () => {
  const script = readFileSync(resolve(process.cwd(), '../device/make_voice.py'), 'utf8')
  for (const [clip, words] of Object.entries(LINES)) {
    expect(script).toContain(`"${clip}": "${words}"`)
  }
  // each beat asks only for clips the script makes, or his existing first-find lines
  for (const beat of ['wake', 'sniff', 'quest', 'feel', 'go']) {
    for (const clip of [...clipsFor(beat), ...clipsFor(beat, beat === 'sniff' ? 'duck' : 1)]) {
      expect(clip in LINES || ['say_duck', 'say_new'].includes(clip)).toBe(true)
    }
  }
  expect(TARGETS.map((t) => t.name).every((name) => VOICE[`say_${name}`])).toBe(true) // those clips exist today
})

test('a new person meets Gary before the home screen; someone he knows goes straight in', async () => {
  window.sessionStorage.clear()
  const service = fakeService()
  const first = render(<App service={service} />)
  await screen.findByRole('button', { name: 'Start' }) // the landing page first
  click('Start')
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

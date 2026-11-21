// The whole page with a stand-in service. Run with: npm test
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'
import story from '../../contract/examples/story.json'
import { Shell, whatChanged } from './App.jsx'
import { createMock } from './services/mock.js'

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '#')
})

const step = (n) => story.steps[n].state

/** A service whose state the test changes by hand. */
function fakeService(first) {
  const service = {
    mode: 'live',
    api: 'http://gary.test',
    state: first,
    fail: false,
    now: () => new Date('2026-11-21T15:41:00Z'),
    getState: vi.fn(async () => {
      if (service.fail) throw new Error('HTTP 503')
      return service.state
    }),
    chooseQuest: vi.fn(async (time) => {
      service.state = { ...service.state, quest: service.state.quest_options[time], quest_choice: time }
      return { quest: service.state.quest, state: service.state }
    }),
    postMood: vi.fn(async () => ({ ok: true })),
    getWellness: vi.fn(async () => story.steps[0].wellness),
  }
  return service
}

describe('what changed between two states', () => {
  test('nothing on the first state, and nothing when nothing happened', () => {
    expect(whatChanged(null, step(0))).toBeNull()
    expect(whatChanged(step(4), step(4))).toBeNull()
    expect(whatChanged(step(0), step(1))).toBeNull() // a private check-in changes nothing here
  })

  test('a find, a cleared place, a new stage and a climb up the cup', () => {
    const quest = whatChanged(step(2), step(3)) // the bicycle at Springbank Park
    expect(quest.find.label).toBe('bicycle')
    expect(quest.cleared).toEqual(['Springbank Park'])
    expect(quest.messages).toEqual(['New find: bicycle. +20 XP.', 'The fog lifted over Springbank Park.'])

    const herd = whatChanged(step(4), step(5)) // the dog, with a friend: the kid becomes a scrambler
    expect(herd.stageUp).toBe(true)
    expect(herd.rankUp).toEqual({ from: 5, to: 3 })
    expect(herd.messages).toEqual([
      'New find: dog. +40 XP.',
      'Gary grew. He is a Scrambler now.',
      'The fog lifted over Gibbons Park.',
      'Your herd moved up to 3rd in the Herd Cup.',
    ])
  })

  test('stepping back in the demo story celebrates nothing', () => {
    expect(whatChanged(step(5), step(4))).toBeNull()
    expect(whatChanged(step(9), step(0))).toBeNull()
  })

  test('a new week resets the cup without calling it a move', () => {
    const monday = { ...step(5), herd: { ...step(5).herd, cup: { ...step(0).herd.cup, week: '2026-W48', rank: 5 } } }
    expect(whatChanged(step(5), monday)).toBeNull()
    const back = { ...monday, herd: { ...monday.herd, cup: { ...monday.herd.cup, rank: 3 } } }
    expect(whatChanged(monday, back).rankUp).toEqual({ from: 5, to: 3 })
  })
})

describe('the page', () => {
  test('draws the state, then celebrates what arrives', async () => {
    const service = fakeService(step(4))
    const { container } = render(<Shell service={service} pollMs={20} />)
    expect(await screen.findByText('30 XP. 30 more to Scrambler.')).toBeTruthy()
    expect(screen.getByText('Live')).toBeTruthy()
    expect(container.querySelector('.toast')).toBeNull()

    service.state = step(5) // the device sniffs a dog, with a friend in the frame
    expect(await screen.findByText('New find: dog. +40 XP.')).toBeTruthy()
    expect(screen.getByText('Gary grew. He is a Scrambler now.')).toBeTruthy()
    expect(screen.getByText('The fog lifted over Gibbons Park.')).toBeTruthy()
    expect(screen.getByText('Your herd moved up to 3rd in the Herd Cup.')).toBeTruthy()
    expect(screen.getByText('70 XP. 80 more to Ibex.')).toBeTruthy()
    expect(container.querySelector('.burst')).toBeTruthy()
    expect(container.querySelector('.gary.grew')).toBeTruthy()
    expect(container.querySelector('.specimen.fresh').textContent).toContain('dog') // the field guide beside Gary
  })

  test('the five screens, and the address remembers which one', async () => {
    const service = fakeService(step(5))
    const { container } = render(<Shell service={service} pollMs={1000} />)
    await screen.findByRole('heading', { name: 'Scrambler' })
    expect(screen.getByRole('button', { name: 'Gary' }).getAttribute('aria-current')).toBe('page')
    expect(container.querySelector('.app').dataset.tab).toBe('gary')

    fireEvent.click(screen.getByRole('button', { name: 'Map' }))
    expect(screen.getByRole('heading', { name: 'Map' })).toBeTruthy()
    expect(window.location.hash).toBe('#map')
    expect(container.querySelector('.app').dataset.tab).toBe('map')

    fireEvent.click(screen.getByRole('button', { name: 'Herd' }))
    expect(screen.getByRole('heading', { name: 'Herd Cup, week 47' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'You' }))
    expect(await screen.findByText(/Private\. Only you see this page/)).toBeTruthy()
    expect(service.getWellness).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Field guide' }))
    expect(screen.getByText('3 of 79 found')).toBeTruthy()

    // back on Gary's screen, the last side screen stays beside him on a wide display
    fireEvent.click(screen.getByRole('button', { name: 'Gary' }))
    expect(container.querySelector('.tab-guide').className).toContain('beside')
    cleanup()
    window.history.replaceState(null, '', '#herd')
    render(<Shell service={fakeService(step(5))} pollMs={1000} />)
    expect(await screen.findByRole('heading', { name: 'Herd Cup, week 47' })).toBeTruthy()
  })

  test('short or long asks the service, and the card changes at once', async () => {
    const service = fakeService(step(0))
    render(<Shell service={service} pollMs={100000} />)
    await screen.findByRole('heading', { name: 'Find a water bottle at your table' })
    fireEvent.click(screen.getByRole('button', { name: /Long/ }))
    await waitFor(() => expect(service.chooseQuest).toHaveBeenCalledWith('long'))
    expect(await screen.findByRole('heading', { name: 'Find a bird at Kains Woods' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Long/ }).getAttribute('aria-pressed')).toBe('true')
    expect(service.getState.mock.calls.length).toBe(1) // no extra round trip: the reply carried the state
  })

  test('when the backend goes away the last state stays, marked as old', async () => {
    const service = fakeService(step(4))
    render(<Shell service={service} pollMs={20} />)
    await screen.findByText('Live')
    service.fail = true
    expect(await screen.findByText('Offline. Showing the last state')).toBeTruthy()
    expect(screen.getByText('30 XP. 30 more to Scrambler.')).toBeTruthy()
    service.fail = false
    expect(await screen.findByText('Live')).toBeTruthy()
  })

  test('a backend that never answers says so, and offers the demo story', async () => {
    const service = fakeService(step(0))
    service.fail = true
    render(<Shell service={service} pollMs={100000} />)
    expect(await screen.findByText(/Cannot reach Gary's backend at http:\/\/gary\.test \(HTTP 503\)/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Open the demo story instead.' }).getAttribute('href')).toBe('?mock')
  })
})

describe('mock mode: the same screens with no backend (issue #24)', () => {
  test('the demo story plays step by step', async () => {
    const service = createMock()
    render(<Shell service={service} pollMs={100000} />)
    expect(await screen.findByText('Demo story')).toBeTruthy()
    expect(screen.getByText(/Demo story, step 1 of 10: Saturday morning/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Back' }).disabled).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'Next' })) // the private check-in
    fireEvent.click(screen.getByRole('button', { name: 'Next' })) // short quest
    expect(await screen.findByRole('heading', { name: 'Find a bicycle at Springbank Park' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Next' })) // the sniff
    expect(await screen.findByText('New find: bicycle. +20 XP.')).toBeTruthy()
    expect(screen.getByText('The fog lifted over Springbank Park.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(await screen.findByText(/step 3 of 10/)).toBeTruthy()
    for (let i = 0; i < 7; i += 1) fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText(/step 10 of 10: Welcome back/)).toBeTruthy()
    expect(await screen.findByText('125 XP. 25 more to Ibex.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Start again' }))
    expect(await screen.findByText(/step 1 of 10/)).toBeTruthy()
  })

  test('choosing and checking in work in mock mode too', async () => {
    const service = createMock()
    render(<Shell service={service} pollMs={100000} />)
    await screen.findByText('Demo story')
    fireEvent.click(screen.getByRole('button', { name: /Long/ }))
    expect(await screen.findByRole('heading', { name: 'Find a bird at Kains Woods' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'You' }))
    fireEvent.click(await screen.findByRole('button', { name: '3: Okay' }))
    expect(await screen.findByRole('heading', { name: 'Noted' })).toBeTruthy()
    expect(screen.getByText('Demo data from the demo story. Not yours.')).toBeTruthy()
  })
})

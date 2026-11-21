// The whole page with a stand-in service. Run with: npm test
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'
import story from '../../contract/examples/story.json'
import { Shell, whatChanged } from './App.jsx'
import { CLIPS, VOICE, pickClip, playClip, voiceFor, writeSound } from './sound.js'
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

describe("Gary's sounds on the page", () => {
  test('each kind of find has its clip, and nothing else makes a sound', () => {
    expect(pickClip(null)).toBeNull()
    expect(pickClip({ find: null, stageUp: true })).toBeNull()
    expect(pickClip({ find: { label: 'bottle', new: true, quest_id: 'q-demo-bottle', friend: false } })).toBe('quest')
    expect(pickClip({ find: { label: 'backpack', new: true, quest_id: 'q-demo-backpack', friend: true } })).toBe('herd')
    expect(pickClip({ find: { label: 'squirrel', new: true, quest_id: null } })).toBe('new')
    expect(pickClip({ find: { label: 'squirrel', new: false, quest_id: null } })).toBe('again')
    expect(pickClip(whatChanged(step(2), step(3)))).toBe('quest') // the story's bicycle quest
    for (const name of ['quest', 'herd', 'new', 'again', 'hello']) expect(CLIPS[name], name).toBeTruthy()
  })

  test('Gary says what he found, by the same rule as the device', () => {
    const find = (more) => ({ find: { label: 'bottle', new: true, quest_id: null, friend: false, ...more } })
    const open = { quests_open: 2, quest: { target: 'backpack', herd: true } }
    expect(voiceFor(find({ quest_id: 'q' }), open, { quests_open: 1 })).toEqual(['say_found_bottle'])
    expect(voiceFor(find({ quest_id: 'q' }), open, { quests_open: 0 })).toEqual(['say_found_bottle', 'say_done'])
    expect(voiceFor(find({ label: 'backpack' }), open, open)).toEqual(['say_backpack', 'say_need_friend'])
    expect(voiceFor(find({ label: 'fire hydrant' }), open, open)).toEqual(['say_not_it', 'say_fire_hydrant'])
    expect(voiceFor(find(), { quests_open: 0 }, { quests_open: 0 })).toEqual(['say_bottle', 'say_new'])
    expect(voiceFor(find({ quest_id: 'q', friend: true }), open, open)).toEqual(['say_found_bottle', 'say_herd'])
    expect(voiceFor(find({ label: 'no such thing' }), {}, {})).toBeNull() // no clip: the chime plays instead
    expect(voiceFor({ find: null }, {}, {})).toBeNull()
    expect(voiceFor({ find: null, miss: true }, {}, {})).toEqual(['say_nothing']) // "Can you move closer?"
    expect(pickClip({ find: null, miss: true })).toBe('nothing')
    const before = { ...step(3), last_miss: null }
    expect(whatChanged(before, { ...before, last_miss: { id: 'm-1', ts: 'x' } }).miss).toBe(true)
    expect(whatChanged({ ...before, last_miss: { id: 'm-1' } }, { ...before, last_miss: { id: 'm-1' } })).toBeNull()
    expect(Object.keys(VOICE).length).toBeGreaterThan(180)
  })

  test('the page plays the clip when a find arrives, unless sound is switched off', async () => {
    const played = []
    vi.stubGlobal('Audio', class {
      constructor(url) {
        this.url = url
      }
      play() {
        played.push(this.src ?? this.url)
        return Promise.reject(new Error('not allowed yet')) // a browser that has not been tapped: no crash
      }
    })
    try {
      window.localStorage.clear()
      const service = fakeService(step(2))
      const { unmount } = render(<Shell service={service} pollMs={20} askCheckIn={false} />)
      await screen.findByText('Kid')
      expect(played).toEqual([]) // the first state is not news
      service.state = step(3)
      await waitFor(() => expect(played).toEqual([VOICE.say_found_bicycle])) // Gary says it, in his voice
      unmount()

      writeSound(false)
      const quiet = fakeService(step(2))
      render(<Shell service={quiet} pollMs={20} askCheckIn={false} />)
      await screen.findByText('Kid')
      quiet.state = step(3)
      await screen.findByText('Quest complete!') // the page did see the find
      expect(played).toEqual([VOICE.say_found_bicycle]) // nothing more
      expect(playClip('no-such-clip')).toBe(false)
    } finally {
      window.localStorage.clear()
      vi.unstubAllGlobals()
    }
  })
})

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
    expect(quest.messages).toEqual(['New find: bicycle. +30 XP.', 'The fog lifted over Springbank Park.'])

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
    const { container } = render(<Shell service={service} pollMs={20} askCheckIn={false} />)
    expect(await screen.findByText('40 XP · 20 to Scrambler')).toBeTruthy()
    expect(screen.getByText('Live')).toBeTruthy()
    expect(container.querySelector('.toast')).toBeNull()

    service.state = step(5) // the device sniffs a dog with a friend in the frame: a quest is done
    const reward = await screen.findByRole('dialog', { name: 'Quest complete!' })
    expect(within(reward).getByText('dog')).toBeTruthy()
    expect(within(reward).getByText('+40 XP')).toBeTruthy()
    expect(within(reward).getByText('☁ Fog lifted over Gibbons Park')).toBeTruthy()
    expect(within(reward).getByText('★ Gary grew: Scrambler')).toBeTruthy()
    expect(within(reward).getByText('▲ Herd up to 3rd in the cup')).toBeTruthy()
    expect(container.querySelector('.toast')).toBeNull() // the reward says it all
    expect(screen.getByText('80 XP · 70 to Ibex')).toBeTruthy()
    expect(container.querySelector('.burst')).toBeTruthy()
    expect(container.querySelector('.gary.grew')).toBeTruthy()
    expect(container.querySelector('.nav-journal .nav-dot')).toBeTruthy() // something new in the journal
    expect(container.querySelector('.nav-map .nav-dot')).toBeTruthy()
    expect(container.querySelector('.nav-cup .nav-dot')).toBeTruthy()
    fireEvent.click(within(reward).getByRole('button', { name: 'Nice!' }))
    expect(screen.queryByRole('dialog')).toBeNull() // check-ins are off in this test
  })

  test('after a quest is done, "how do you feel now?" follows the reward', async () => {
    const service = fakeService(step(4))
    render(<Shell service={service} pollMs={20} askCheckIn />)
    fireEvent.click(await screen.findByRole('button', { name: 'Skip' })) // the check-in on opening
    service.state = step(5)
    fireEvent.click(await screen.findByRole('button', { name: 'Nice!' }))
    const after = await screen.findByRole('dialog', { name: 'Now that you are back' })
    fireEvent.click(within(after).getByRole('button', { name: '4: Good' }))
    await waitFor(() => expect(service.postMood).toHaveBeenCalledWith('after', 4))
    fireEvent.click(await screen.findByRole('button', { name: 'Off we go' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  test('a find that finishes no quest is a toast, not a reward', async () => {
    const service = fakeService(step(0))
    render(<Shell service={service} pollMs={20} askCheckIn={false} />)
    await screen.findByText('0 XP · 60 to Scrambler')
    const top = { id: 'loose-1', ts: '2026-11-21T15:40:00Z', label: 'cup', score: 0.9, friend: false, new: true, quest_id: null, latency_ms: 40, xp: 5, place: null }
    service.state = { ...step(0), gary: { ...step(0).gary, xp: 5 }, journal: [top] }
    expect(await screen.findByText('New find: cup. +5 XP.')).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  test('the five screens, and the address remembers which one', async () => {
    const service = fakeService(step(5))
    const { container } = render(<Shell service={service} pollMs={1000} askCheckIn={false} />)
    await screen.findByRole('heading', { name: 'Scrambler' })
    expect(screen.getByRole('button', { name: 'Home' }).getAttribute('aria-current')).toBe('page')
    expect(container.querySelector('.app').dataset.tab).toBe('home')

    fireEvent.click(screen.getByRole('button', { name: 'Map' }))
    expect(screen.getByRole('heading', { name: 'Map' })).toBeTruthy()
    expect(window.location.hash).toBe('#map')
    expect(container.querySelector('.app').dataset.tab).toBe('map')

    fireEvent.click(screen.getByRole('button', { name: 'Cup' }))
    expect(screen.getByRole('heading', { name: 'Herd Cup, week 47' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByRole('heading', { name: 'Wellness' })).toBeTruthy()
    expect(service.getWellness).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Journal' }))
    expect(screen.getByText('3 of 90 found')).toBeTruthy()

    cleanup()
    window.history.replaceState(null, '', '#cup')
    render(<Shell service={fakeService(step(5))} pollMs={1000} askCheckIn={false} />)
    expect(await screen.findByRole('heading', { name: 'Herd Cup, week 47' })).toBeTruthy()
    // an address from before the redesign still lands on the right screen
    cleanup()
    window.history.replaceState(null, '', '#herd')
    render(<Shell service={fakeService(step(5))} pollMs={1000} askCheckIn={false} />)
    expect(await screen.findByRole('heading', { name: 'Herd Cup, week 47' })).toBeTruthy()
  })

  test('the check-in pops up on the home screen once, and Skip sends nothing', async () => {
    const service = fakeService(step(5))
    render(<Shell service={service} pollMs={100000} askCheckIn />)
    expect(await screen.findByRole('dialog')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(service.postMood).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Map' }))
    fireEvent.click(screen.getByRole('button', { name: 'Home' }))
    expect(screen.queryByRole('dialog')).toBeNull() // once per visit
  })

  test('on a locked Gary a visitor without the passphrase sees the world and is asked nothing', async () => {
    const service = fakeService(step(5))
    service.getWellness = vi.fn(async () => {
      throw Object.assign(new Error('HTTP 401'), { locked: true })
    })
    render(<Shell service={service} pollMs={100000} askCheckIn />)
    expect(await screen.findByRole('heading', { name: 'Scrambler' })).toBeTruthy()
    await waitFor(() => expect(service.getWellness).toHaveBeenCalled())
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(service.postMood).not.toHaveBeenCalled()
    // the private side says it is locked, and nothing of it shows
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByText('🔒 Locked')).toBeTruthy()
    expect(screen.getByLabelText('Passphrase')).toBeTruthy()
    expect(screen.queryByText(/You reported/)).toBeNull()
  })

  test('short or long asks the service, and the card changes at once', async () => {
    const service = fakeService(step(0))
    render(<Shell service={service} pollMs={100000} askCheckIn={false} />)
    await screen.findByRole('heading', { name: 'Find a water bottle at your table' })
    fireEvent.click(screen.getByRole('button', { name: /Long/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Start quest' }))
    await waitFor(() => expect(service.chooseQuest).toHaveBeenCalledWith('long'))
    expect(await screen.findByRole('heading', { name: 'Find a bird at Kains Woods' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Long/ }).getAttribute('aria-pressed')).toBe('true')
    expect(service.getState.mock.calls.length).toBe(1) // no extra round trip: the reply carried the state
  })

  test('"See on map" from a quest goes to the map, on that place', async () => {
    const service = fakeService(step(0))
    const { container } = render(<Shell service={service} pollMs={100000} askCheckIn={false} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Find a water bottle at your table' }))
    fireEvent.click(screen.getByRole('button', { name: 'See on map' }))
    expect(container.querySelector('.app').dataset.tab).toBe('map')
    expect(screen.getByRole('heading', { name: 'Hack Western, your table' })).toBeTruthy()
  })

  test('when the backend goes away the last state stays, marked as old', async () => {
    const service = fakeService(step(4))
    render(<Shell service={service} pollMs={20} askCheckIn={false} />)
    await screen.findByText('Live')
    service.fail = true
    expect(await screen.findByText('Offline. Showing the last state')).toBeTruthy()
    expect(screen.getByText('40 XP · 20 to Scrambler')).toBeTruthy()
    service.fail = false
    expect(await screen.findByText('Live')).toBeTruthy()
  })

  test('a backend that never answers says so, and offers the demo story', async () => {
    const service = fakeService(step(0))
    service.fail = true
    render(<Shell service={service} pollMs={100000} askCheckIn={false} />)
    expect(await screen.findByText(/Cannot reach Gary's backend at http:\/\/gary\.test \(HTTP 503\)/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Open the demo story instead.' }).getAttribute('href')).toBe('?mock')
  })
})

describe('mock mode: the same screens with no backend (issue #24)', () => {
  test('the demo story plays step by step', async () => {
    const service = createMock()
    render(<Shell service={service} pollMs={100000} askCheckIn={false} />)
    expect(await screen.findByText('Demo story')).toBeTruthy()
    expect(screen.getByText(/Demo story, step 1 of 10: Saturday morning/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Back' }).disabled).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'Next' })) // the private check-in
    fireEvent.click(screen.getByRole('button', { name: 'Next' })) // short quest
    expect(await screen.findByRole('heading', { name: 'Find a bicycle at Springbank Park' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Next' })) // the sniff
    expect(await screen.findByText('☁ Fog lifted over Springbank Park')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Nice!' }))

    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(await screen.findByText(/step 3 of 10/)).toBeTruthy()
    for (let i = 0; i < 7; i += 1) fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText(/step 10 of 10: Welcome back/)).toBeTruthy()
    expect(await screen.findByText('135 XP · 15 to Ibex')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Start again' }))
    expect(await screen.findByText(/step 1 of 10/)).toBeTruthy()
  })

  test('choosing and checking in work in mock mode too', async () => {
    const service = createMock()
    render(<Shell service={service} pollMs={100000} askCheckIn={false} />)
    await screen.findByText('Demo story')
    fireEvent.click(screen.getByRole('button', { name: /Long/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Start quest' }))
    expect(await screen.findByRole('heading', { name: 'Find a bird at Kains Woods' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Check in' }))
    fireEvent.click(await screen.findByRole('button', { name: '3: Okay' }))
    expect(await screen.findByRole('heading', { name: 'Noted' })).toBeTruthy()
    expect(screen.getByText('Demo story data')).toBeTruthy()
  })
})

describe('Been there: the page knows you are at the quest, and says only that', () => {
  afterEach(() => {
    delete navigator.geolocation
  })
  const at = (latitude, longitude, accuracy = 20) => {
    navigator.geolocation = {
      watchPosition: (ok) => (ok({ coords: { latitude, longitude, accuracy } }), 1),
      clearWatch: () => {},
    }
  }

  test('at the place: the card says so, and the backend hears the quest id once, never a position', async () => {
    at(43.0097, -81.2736) // a few metres from the Hack Western spot
    const service = { ...fakeService(step(0)), postVisit: vi.fn(async () => ({ ok: true })) }
    render(<Shell service={service} pollMs={20} askCheckIn={false} />)
    expect(await screen.findByText(/You're here\. Sniff it now/)).toBeTruthy()
    await new Promise((r) => setTimeout(r, 80)) // a few polls later, still once
    expect(service.postVisit).toHaveBeenCalledTimes(1)
    expect(service.postVisit).toHaveBeenCalledWith('q-demo-bottle')
  })

  test('far away: how far, and nothing is sent', async () => {
    at(42.9849, -81.2453) // downtown
    const service = { ...fakeService(step(0)), postVisit: vi.fn(async () => ({ ok: true })) }
    render(<Shell service={service} pollMs={20} askCheckIn={false} />)
    expect(await screen.findByText(/km from you, as the crow flies/)).toBeTruthy()
    expect(service.postVisit).not.toHaveBeenCalled()
  })
})

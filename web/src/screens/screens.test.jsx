// The screens against the contract's example files. Run with: npm test
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'
import example from '../../../contract/examples/state.json'
import story from '../../../contract/examples/story.json'
import exampleWellness from '../../../contract/examples/wellness.json'
import QuestCard from '../components/QuestCard.jsx'
import Guide from './Guide.jsx'
import Herd from './Herd.jsx'
import Home from './Home.jsx'
import MapScreen from './MapScreen.jsx'
import Settings from './Settings.jsx'
import You, { suggestPhase } from './You.jsx'
import CheckIn from '../components/CheckIn.jsx'
import { LONDON, layout, placeKey } from '../places.js'

afterEach(cleanup)

const NO_FLASH = { find: null, stageUp: false, cleared: [], rankUp: null, messages: [] }
const at = (text) => new Date(text)
const step = (n) => story.steps[n].state

describe('Gary (issue #25)', () => {
  test('draws the contract example: stage, climb, his line, the recap, the quest', () => {
    render(<Home state={example} flash={NO_FLASH} now={at(example.journal[0].ts)} />)
    expect(screen.getByRole('heading', { name: 'Scrambler' })).toBeTruthy()
    expect(screen.getByAltText('Gary the goat, Scrambler')).toBeTruthy()
    expect(screen.getByText('80 XP · 70 to Ibex')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Find a water bottle at your table' })).toBeTruthy()
    expect(screen.getByText('Stage 2')).toBeTruthy()
    expect(screen.getByText(/A bench\. I respect anything that holds still\./)).toBeTruthy()
    // the home screen stays calm: the finds live in the journal
    expect(screen.queryByText('+80 XP')).toBeNull()
  })

  test('a fresh Gary naps: no guilt, no pressure, nothing lost', () => {
    render(<Home state={step(0)} flash={NO_FLASH} now={at(story.steps[0].now)} />)
    expect(screen.getByRole('heading', { name: 'Kid' })).toBeTruthy()
    expect(screen.getByAltText('Gary the goat, Kid, napping')).toBeTruthy()
    expect(screen.getByText(/Gary is napping\. No guilt/)).toBeTruthy()
    expect(screen.getByText('0 XP · 60 to Scrambler')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/streak|missed|lost|sad/i)
  })

  test('a welcome-back line after a nap, and a napping pose that keeps the XP', () => {
    render(<Home state={step(9)} flash={NO_FLASH} now={at(story.steps[9].now)} />)
    expect(screen.getByText(/you are back\. Good\. I saved you a rock/)).toBeTruthy()
    cleanup()
    render(<Home state={step(7)} flash={NO_FLASH} now={at(story.steps[7].now)} />)
    expect(screen.getByAltText('Gary the goat, Scrambler, napping')).toBeTruthy()
    expect(screen.getByText('70 XP · 80 to Ibex')).toBeTruthy()
  })

  test('the top of the mountain and an empty quest list do not break the page', () => {
    const top = {
      ...example,
      gary: { ...example.gary, stage: 'summit-elder', stage_index: 3, xp: 400, stage_xp: 300, next_stage_xp: null },
      quest: null, quest_choice: null, quest_options: { short: null, long: null }, quests_open: 0,
    }
    render(<Home state={top} flash={NO_FLASH} now={at(example.journal[0].ts)} />)
    expect(screen.getByRole('heading', { name: 'Summit Elder' })).toBeTruthy()
    expect(screen.getByText('400 XP · summit')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'All quests done' })).toBeTruthy()
    expect(screen.getAllByText('none open').length).toBe(2)
  })

  test('a new find is celebrated, and a stage Gary does not know yet still draws', () => {
    const flash = { ...NO_FLASH, find: example.journal[0], stageUp: true }
    const { container } = render(<Home state={example} flash={flash} now={at(example.journal[0].ts)} />)
    expect(container.querySelector('.burst')).toBeTruthy()
    expect(container.querySelector('.gary.grew')).toBeTruthy()
    cleanup()
    const odd = { ...example, gary: { ...example.gary, stage: 'cloud-walker', stage_index: 7 } }
    render(<Home state={odd} flash={NO_FLASH} now={at(example.journal[0].ts)} />)
    expect(screen.getByRole('heading', { name: 'cloud-walker' })).toBeTruthy()
  })
})

describe('Quest card (issue #28)', () => {
  const scoutQuest = step(2).quest // the scout's Springbank Park quest, chosen with "short"

  test('shows the place, the thing, and where the scout found it', () => {
    render(<QuestCard quest={scoutQuest} choice="short" options={step(2).quest_options} open={6} />)
    expect(screen.getByRole('heading', { name: 'Find a bicycle at Springbank Park' })).toBeTruthy()
    expect(screen.getByText('📍 Springbank Park')).toBeTruthy()
    const link = screen.getByRole('link', { name: 'Scout · london.ca' })
    expect(link.getAttribute('href')).toBe('https://london.ca/parks-london')
  })

  test('Short and Long open the quest\'s details; starting it asks the backend', async () => {
    const onChoose = vi.fn(async () => {})
    const onShowMap = vi.fn()
    render(<QuestCard quest={scoutQuest} choice="short" options={step(2).quest_options} onChoose={onChoose} onShowMap={onShowMap} />)
    expect(screen.getByRole('button', { name: /Short/ }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: /Long/ }))
    const sheet = screen.getByRole('dialog')
    expect(within(sheet).getByText(/Long quest · trail walk/)).toBeTruthy()
    expect(onChoose).not.toHaveBeenCalled() // looking is not choosing
    fireEvent.click(within(sheet).getByRole('button', { name: 'Start quest' }))
    await waitFor(() => expect(onChoose).toHaveBeenCalledWith('long'))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    // the active quest: everything about it, another of the same length, or the map
    fireEvent.click(screen.getByRole('button', { name: scoutQuest.title }))
    const active = screen.getByRole('dialog', { name: scoutQuest.title })
    expect(within(active).getByText(/Short quest · active/)).toBeTruthy()
    expect(within(active).getByText('📍 Springbank Park')).toBeTruthy()
    expect(within(active).getByText(scoutQuest.note)).toBeTruthy()
    expect(within(active).getByRole('link', { name: 'london.ca' })).toBeTruthy()
    fireEvent.click(within(active).getByRole('button', { name: 'Another short' }))
    await waitFor(() => expect(onChoose).toHaveBeenLastCalledWith('short'))
    fireEvent.click(screen.getByRole('button', { name: scoutQuest.title }))
    fireEvent.click(screen.getByRole('button', { name: 'See on map' }))
    expect(onShowMap).toHaveBeenCalledWith('Springbank Park')
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  test('a length with nothing open cannot be pressed, and a co-op quest says what it needs', () => {
    const onChoose = vi.fn()
    const herdQuest = step(3).quest // the Gibbons Park quest for two
    render(<QuestCard quest={herdQuest} choice={null} options={{ short: herdQuest, long: null }} open={1} onChoose={onChoose} />)
    expect(screen.getByText('Needs a friend')).toBeTruthy()
    const long = screen.getByRole('button', { name: /Long/ })
    expect(long.disabled).toBe(true)
    fireEvent.click(long)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(onChoose).not.toHaveBeenCalled()
  })

  test('chips: the XP, the herd bonus, and a long quest marked as a trail walk', () => {
    const long = step(0).quest_options.long
    render(<QuestCard quest={long} choice="long" options={step(0).quest_options} open={2} />)
    expect(screen.getByText(`+${long.xp} XP`)).toBeTruthy()
    expect(screen.getByText('Trail')).toBeTruthy()
    expect(screen.getByText('Herd x2')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Long.*trail/ })).toBeTruthy()
    cleanup()
    render(<QuestCard quest={example.quest} choice={null} options={example.quest_options} open={2} />)
    expect(screen.queryByText('Trail')).toBeNull()
  })

  test('a seed quest is not passed off as the scout\'s', () => {
    render(<QuestCard quest={example.quest} choice={null} options={example.quest_options} open={2} />)
    expect(screen.getByText('Starter')).toBeTruthy()
    expect(screen.queryByText(/Scout/)).toBeNull()
  })

  test('only a quest from a live agent run is credited to the scout, whatever address it carries', () => {
    // scout.py --from-file: hand-written places, with the page a person took them from
    const sample = { ...scoutQuest, source: 'sample' }
    const { unmount } = render(<QuestCard quest={sample} choice={null} options={{}} open={1} />)
    expect(screen.getByText('Sample')).toBeTruthy()
    expect(screen.queryByText(/Scout/)).toBeNull()
    expect(screen.queryByRole('link')).toBeNull()
    unmount()
    // a quest someone posted by hand with an address
    const byHand = render(<QuestCard quest={{ ...scoutQuest, source: 'manual' }} choice={null} options={{}} open={1} />)
    expect(screen.getByText('Starter')).toBeTruthy()
    expect(screen.queryByText(/Scout/)).toBeNull()
    byHand.unmount()
    // the scout's quest with something that is not a web address: no link is made of it
    for (const source_url of ['javascript:alert(1)', 'data:text/html,hello', null, 'london.ca']) {
      const view = render(<QuestCard quest={{ ...scoutQuest, source_url }} choice={null} options={{}} open={1} />)
      expect(screen.getByText('Scout')).toBeTruthy()
      expect(screen.queryByRole('link')).toBeNull()
      view.unmount()
    }
  })
})

describe('Map (issue #26)', () => {
  afterEach(() => {
    delete navigator.geolocation
  })

  test('every place is a pin on the street map; fog everywhere but the cleared places', () => {
    const { container } = render(<MapScreen map={example.map} flash={NO_FLASH} quest={example.quest} />)
    expect(container.querySelectorAll('.tile').length).toBe(3)
    expect(container.querySelector('.tile.cleared .tile-name').textContent).toBe('Harris Park')
    expect(screen.getByRole('button', { name: 'Fog. Your quest is here' }).textContent).toContain('Hack Western, your table')
    expect(screen.getByRole('button', { name: 'Fog' }).querySelector('.tile-name')).toBeNull() // fog names nothing
    expect(container.querySelector('canvas.fog-canvas')).toBeTruthy()
    expect(container.querySelector('.leaflet-tile-pane')).toBeTruthy()
    expect(screen.getByText('1/3 uncovered')).toBeTruthy()
  })

  test('tapping a cleared place shows what was found there and when', () => {
    render(<MapScreen map={example.map} flash={NO_FLASH} />)
    expect(screen.getByText('Tap a pin.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Harris Park, uncovered' }))
    expect(screen.getByRole('heading', { name: 'Harris Park' })).toBeTruthy()
    expect(screen.getByText(/^Uncovered /)).toBeTruthy()
    expect(screen.getByText(/bench · .* · Herd/)).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button', { name: 'Fog' })[0])
    expect(screen.getByRole('heading', { name: 'Still in fog' })).toBeTruthy()
  })

  test('"See on map" opens the map on that place, with the scout\'s note on where to stand', () => {
    const quest = { ...example.quest, note: 'Stay on public paths.' }
    render(<MapScreen map={example.map} flash={NO_FLASH} quest={quest} focusPlace="Hack Western, your table" />)
    expect(screen.getByRole('heading', { name: 'Hack Western, your table' })).toBeTruthy()
    expect(screen.getByText(/Your quest is here\. Stay on public paths\./)).toBeTruthy()
  })

  test('the place that just cleared is marked for its animation', () => {
    const { container } = render(<MapScreen map={example.map} flash={{ ...NO_FLASH, cleared: ['Harris Park'] }} />)
    expect(container.querySelector('.tile.cleared.fresh').textContent).toBe('Harris Park')
    expect(container.querySelectorAll('.tile.fresh').length).toBe(1)
  })

  test('your position is drawn from the browser, and a refusal is said plainly', () => {
    navigator.geolocation = {
      watchPosition: (ok) => {
        ok({ coords: { latitude: 42.99, longitude: -81.25, accuracy: 20 } })
        return 7
      },
      clearWatch: vi.fn(),
    }
    const { container, unmount } = render(<MapScreen map={example.map} flash={NO_FLASH} />)
    expect(container.querySelector('.me')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Show where I am' }).disabled).toBe(false)
    unmount()
    expect(navigator.geolocation.clearWatch).toHaveBeenCalledWith(7)
    navigator.geolocation = { watchPosition: (ok, no) => (no({ code: 1 }), 8), clearWatch: () => {} }
    render(<MapScreen map={example.map} flash={NO_FLASH} />)
    expect(screen.getByText(/Location is off/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Location is off' }).disabled).toBe(true)
  })

  test('many places still draw', () => {
    const many = Array.from({ length: 25 }, (_, i) => ({ place: `Place ${i}`, quest_id: `q-${i}`, cleared: i % 2 === 0, finds: [] }))
    const { container } = render(<MapScreen map={many} flash={NO_FLASH} />)
    expect(container.querySelectorAll('.tile').length).toBe(25)
  })
})

describe('Where places sit on the map', () => {
  test('known places by name, spelled any way, the same spot every time', () => {
    const spots = layout(['Harris Park', 'Hack Western, your table', 'Hack Western, the next table'])
    expect(spots.get('Harris Park')).toEqual([42.9862, -81.2563])
    expect(placeKey('harris  PARK')).toBe('harris park')
    // two places at one spot are nudged apart, but stay close (well under a kilometre)
    const [a, b] = [spots.get('Hack Western, your table'), spots.get('Hack Western, the next table')]
    expect(a).not.toEqual(b)
    expect(Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1])).toBeLessThan(0.008)
  })

  test('a place nobody has placed lands near downtown, always in the same spot', () => {
    const one = layout(['Some Brand New Park']).get('Some Brand New Park')
    expect(layout(['Some Brand New Park']).get('Some Brand New Park')).toEqual(one)
    expect(Math.abs(one[0] - LONDON[0])).toBeLessThan(0.02)
    expect(Math.abs(one[1] - LONDON[1])).toBeLessThan(0.03)
  })
})

describe('Field guide and journal (issue #27)', () => {
  test('all 104 things: found ones named and in colour, the rest locked silhouettes', () => {
    const { container } = render(<Guide guide={example.guide} journal={example.journal} now={at(example.journal[0].ts)} flash={NO_FLASH} />)
    expect(container.querySelectorAll('.specimen').length).toBe(0) // the finds tab comes first
    fireEvent.click(screen.getByRole('button', { name: 'Field guide' }))
    expect(screen.getByText('1 of 104 found')).toBeTruthy()
    expect(container.querySelectorAll('.specimen').length).toBe(104)
    expect(container.querySelectorAll('.specimen.got').length).toBe(1)
    expect(container.querySelectorAll('.specimen.locked').length).toBe(103)
    expect(container.querySelector('.specimen.got').textContent).toContain('bench')
    expect(container.querySelectorAll('.specimen.locked .thing-icon.locked').length).toBe(103)
    expect(container.querySelector('.specimen.locked').getAttribute('aria-label')).toBe('Not found yet')
    expect(screen.getByText('1 of 58')).toBeTruthy() // outdoors
    expect(screen.getByText('0 of 46')).toBeTruthy() // indoors
  })

  test('the counter comes from the state, not from counting on the page', () => {
    render(<Guide guide={{ total: 104, found: step(9).guide.found }} journal={[]} now={at(story.steps[9].now)} flash={NO_FLASH} />)
    expect(screen.getByText('4 of 104 found')).toBeTruthy()
  })

  test("today's finds, newest first, with marks and the device's time; older ones under Earlier", () => {
    const journal = step(9).journal // Sunday's bird, then Saturday's three
    const { container } = render(<Guide guide={step(9).guide} journal={journal} now={at(story.steps[9].now)} flash={NO_FLASH} />)
    const lists = container.querySelectorAll('ul.finds')
    expect(lists.length).toBe(2)
    expect([...lists[0].querySelectorAll('.find-label')].map((el) => el.textContent)).toEqual(['bird'])
    expect([...lists[1].querySelectorAll('.find-label')].map((el) => el.textContent)).toEqual(['dog', 'fire hydrant', 'bicycle'])
    expect(screen.getByRole('heading', { name: 'Earlier' })).toBeTruthy()
    expect(within(lists[1]).getByText('Herd')).toBeTruthy()
    expect(within(lists[0]).getByText(/41 ms/)).toBeTruthy()
  })

  test('a find row: marks, the place, and the time the device took', () => {
    render(<Guide guide={example.guide} journal={example.journal} now={at(example.journal[0].ts)} flash={NO_FLASH} />)
    const find = screen.getByText('+80 XP').closest('li')
    expect(within(find).getByText('bench')).toBeTruthy()
    expect(within(find).getByText('new')).toBeTruthy()
    expect(within(find).getByText('Herd')).toBeTruthy()
    expect(within(find).getByText('quest')).toBeTruthy()
    expect(within(find).getByText(/41 ms/)).toBeTruthy()
    expect(within(find).getByText(/Harris Park/)).toBeTruthy()
  })

  test('a thing found just now is highlighted', () => {
    const flash = { ...NO_FLASH, find: example.journal[0] }
    const { container } = render(<Guide guide={example.guide} journal={example.journal} now={at(example.journal[0].ts)} flash={flash} view="guide" />)
    expect(container.querySelector('.specimen.fresh').textContent).toContain('bench')
  })
})

describe('Herd and the Herd Cup (issue #29)', () => {
  test('the cup table: the top herds and yours, herds only', () => {
    const { container } = render(<Herd herd={example.herd} journal={example.journal} flash={NO_FLASH} />)
    const rows = [...container.querySelectorAll('.cup-row')].map((row) => row.textContent)
    expect(rows.length).toBe(3)
    expect(rows[0]).toContain('Cliff Hangers')
    expect(container.querySelector('.cup-row.you').textContent).toContain('Your herd')
    expect(container.querySelector('.cup-row.you .cup-rank').textContent).toBe('3')
    expect(screen.getByText(/1 quest together, 1 place uncovered/)).toBeTruthy()
    expect(screen.getByText('2 points to pass The Bleat Goes On')).toBeTruthy()
    expect(screen.getByText(/rival herds are demo data/)).toBeTruthy()
    expect(screen.getByText(/3rd of 6/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Herd Cup, week 47' })).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/leaderboard|your rank among friends|last place/i)
  })

  test('a new herd is shown its own row, never last, with the next step up', () => {
    const { container } = render(<Herd herd={step(0).herd} journal={[]} flash={NO_FLASH} />)
    expect(container.querySelectorAll('.cup-row').length).toBe(4)
    expect(container.querySelector('.cup-row.you .cup-rank').textContent).toBe('5')
    expect(screen.getByText('1 point to pass Kid You Not')).toBeTruthy()
    expect(screen.getByText(/5th of 6/)).toBeTruthy()
  })

  test('the friend-in-frame confirmation, the co-op quest and the shared badges', () => {
    const { container } = render(<Herd herd={example.herd} journal={example.journal} flash={NO_FLASH} />)
    expect(screen.getByText(/Friend in frame · bench/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Find a backpack, with a friend in frame' })).toBeTruthy()
    expect(screen.getByText('Quest for two')).toBeTruthy()
    expect([...container.querySelectorAll('.badge.earned .badge-name')].map((el) => el.textContent)).toEqual(['First herd', 'Herd quest'])
    expect(container.querySelectorAll('.badge').length).toBe(4)
    expect(screen.getByText('Five finds together')).toBeTruthy() // how to earn the next one
    cleanup()
    render(<Herd herd={step(0).herd} journal={step(4).journal} flash={NO_FLASH} />)
    expect(screen.getByText(/Get a friend in frame/)).toBeTruthy()
  })

  test('moving up the cup is marked and said', () => {
    const { container } = render(<Herd herd={example.herd} journal={example.journal} flash={{ ...NO_FLASH, rankUp: { from: 5, to: 3 } }} />)
    expect(container.querySelector('.cup-row.you.moved')).toBeTruthy()
    expect(screen.getByText(/Up from 5th to 3rd!/)).toBeTruthy()
  })

  test('leading the cup, no co-op quest, and a badge this page has never heard of', () => {
    const herd = {
      ...example.herd, quest: null, badges: ['first-herd', 'moon-walkers'],
      cup: { ...example.herd.cup, rank: 1, ahead: null, table: [{ herd: 'Your herd', score: 9, quests: 5, places: 4, you: true }] },
    }
    render(<Herd herd={herd} journal={[]} flash={NO_FLASH} />)
    expect(screen.getByText('Your herd leads this week')).toBeTruthy()
    expect(screen.queryByText('Quest for two')).toBeNull()
    expect(screen.getByText('moon-walkers')).toBeTruthy()
  })
})

describe('You: the private wellness view (issue #30)', () => {
  function fakeService(wellness = exampleWellness, now = '2026-11-21T06:00:00Z') {
    return {
      mode: 'live',
      now: () => new Date(now),
      postMood: vi.fn(async () => ({ ok: true })),
      getWellness: vi.fn(async () => wellness),
    }
  }

  test('a label that says only what is true, the summary, stat tiles and before-and-after moods', async () => {
    // exampleWellness comes from a backend with no passphrase, so the view must not call itself private
    const { container } = render(<You service={fakeService()} stamp="a" />)
    expect(await screen.findByText('You reported feeling better after your outing.')).toBeTruthy()
    expect(screen.getByText('Not locked')).toBeTruthy()
    expect(screen.getByText(/anyone who has this page's address can\s+open it/)).toBeTruthy()
    expect(screen.queryByText('🔒 Private')).toBeNull()
    const stats = [...container.querySelectorAll('.stat')].map((el) => el.textContent)
    expect(stats).toEqual(['1outings', '10min outside', '1with a friend'])
    const pair = container.querySelector('.pairs li')
    expect(pair.querySelector('.mood-3').textContent).toContain('Okay')
    expect(pair.querySelector('.mood-4').textContent).toContain('Good')
    expect(screen.getByText('10 min')).toBeTruthy()
    expect(screen.queryByText(/Demo story data|demo data/)).toBeNull()
  })

  test('"Check in" opens the check-in; a tap is sent as the suggested phase and the view reloads', async () => {
    const service = fakeService({ ...exampleWellness, checkins: [], pairs: [] })
    render(<You service={service} stamp="a" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Check in' }))
    expect(await screen.findByRole('dialog', { name: 'Before you head out' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '4: Good' }))
    await waitFor(() => expect(service.postMood).toHaveBeenCalledWith('before', 4))
    fireEvent.click(await screen.findByRole('button', { name: 'Off we go' }))
    await waitFor(() => expect(service.getWellness.mock.calls.length).toBeGreaterThanOrEqual(3))
  })

  test('with a "before" already in today, the next one is offered as an "after"', () => {
    const open = { ...exampleWellness, checkins: [{ ts: '2026-11-21T17:00:00Z', phase: 'before', value: 3, source: 'device' }], pairs: [] }
    expect(suggestPhase(open.checkins, new Date('2026-11-21T17:01:00Z'))).toBe('after')
    expect(suggestPhase(exampleWellness.checkins, new Date('2026-11-21T05:51:00Z'))).toBe('before') // the pair is complete
    expect(suggestPhase(open.checkins, new Date('2026-11-23T17:01:00Z'))).toBe('before') // a new day starts fresh
  })

  test('the person can say which kind of check-in it is, or skip it and send nothing', async () => {
    const service = fakeService({ ...exampleWellness, checkins: [], pairs: [] })
    render(<You service={service} stamp="a" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Check in' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Already back' }))
    expect(screen.getByRole('dialog', { name: 'Now that you are back' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(service.postMood).not.toHaveBeenCalled()
  })

  test('behind a passphrase the view wears the Private chip, and can be locked again on this device', async () => {
    const service = { ...fakeService({ ...exampleWellness, locked: true }), forgetKey: vi.fn() }
    render(<You service={service} stamp="a" />)
    expect(await screen.findByText('🔒 Private')).toBeTruthy()
    expect(screen.queryByText('Not locked')).toBeNull()
    expect(screen.queryByText(/no lock yet/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Lock on this device' }))
    expect(service.forgetKey).toHaveBeenCalled()
    expect(screen.getByText('🔒 Locked')).toBeTruthy()
    expect(screen.queryByText('You reported feeling better after your outing.')).toBeNull()
  })

  test('a locked view shows nothing private until the passphrase opens it', async () => {
    const lockedError = Object.assign(new Error('HTTP 401'), { locked: true })
    const service = {
      mode: 'live',
      now: () => new Date('2026-11-21T06:00:00Z'),
      postMood: vi.fn(async () => ({ ok: true })),
      getWellness: vi.fn(async () => {
        throw lockedError
      }),
      unlock: vi.fn(async (passphrase) => {
        if (passphrase !== 'goats climb at dawn') throw lockedError
        return { ...exampleWellness, locked: true }
      }),
      forgetKey: vi.fn(),
    }
    render(<You service={service} stamp="a" />)
    expect(await screen.findByText('🔒 Locked')).toBeTruthy()
    // nothing private is on the screen, and no check-in can be started
    expect(screen.queryByText('You reported feeling better after your outing.')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Check in' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Sample week' })).toBeNull()
    const open = screen.getByRole('button', { name: 'Open' })
    expect(open.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('Passphrase'), { target: { value: 'a guess' } })
    fireEvent.click(open)
    expect(await screen.findByText('That passphrase did not open it.')).toBeTruthy()
    expect(screen.queryByText('You reported feeling better after your outing.')).toBeNull()

    fireEvent.change(screen.getByLabelText('Passphrase'), { target: { value: 'goats climb at dawn' } })
    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(await screen.findByText('You reported feeling better after your outing.')).toBeTruthy()
    expect(screen.getByText('🔒 Private')).toBeTruthy()
    expect(screen.queryByLabelText('Passphrase')).toBeNull()
  })

  test('seeded history is labelled as demo data, wherever it comes from', async () => {
    render(<You service={fakeService({ ...exampleWellness, demo: true })} stamp="a" />)
    expect(await screen.findByText('Demo story data')).toBeTruthy()
    // the demo story never calls itself private, locked or unlocked
    expect(screen.queryByText(/Not locked|🔒/)).toBeNull()
    cleanup()
    render(<You service={fakeService({ ...exampleWellness, pairs: [], summary: 'No before-and-after check-ins yet. They are always optional.' })} stamp="a" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Sample week' }))
    expect(screen.getByText('Sample week · demo data')).toBeTruthy()
    expect(screen.getByText('You reported feeling better after 3 of 4 outings.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'My own view' }))
    expect(screen.queryByText(/demo data/)).toBeNull()
  })

  test('a backend that cannot be reached is said plainly', async () => {
    const service = fakeService()
    service.getWellness = vi.fn(async () => {
      throw new Error('HTTP 503')
    })
    render(<You service={service} stamp="a" />)
    expect(await screen.findByText(/Could not load \(HTTP 503\)/)).toBeTruthy()
  })
})

describe('The check-in pop-up and Settings', () => {
  function fakeService(wellness = { ...exampleWellness, checkins: [], pairs: [] }) {
    return {
      mode: 'live',
      api: 'http://gary.test',
      now: () => new Date('2026-11-21T06:00:00Z'),
      postMood: vi.fn(async () => ({ ok: true })),
      getWellness: vi.fn(async () => wellness),
    }
  }

  test('asks how you feel; skipping sends nothing', async () => {
    const service = fakeService()
    const onClose = vi.fn()
    render(<CheckIn service={service} onClose={onClose} />)
    expect(await screen.findByRole('dialog', { name: 'Before you head out' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Skip' }))
    expect(onClose).toHaveBeenCalled()
    expect(service.postMood).not.toHaveBeenCalled()
  })

  test('a tap is sent as the suggested phase, then says it was noted', async () => {
    const service = fakeService()
    render(<CheckIn service={service} onClose={() => {}} />)
    fireEvent.click(await screen.findByRole('button', { name: '4: Good' }))
    await waitFor(() => expect(service.postMood).toHaveBeenCalledWith('before', 4))
    expect(await screen.findByRole('heading', { name: 'Noted' })).toBeTruthy()
  })

  test('the sheet says Private only when the private side is behind a passphrase', async () => {
    render(<CheckIn service={fakeService()} onClose={() => {}} />)
    await screen.findByRole('dialog', { name: 'Before you head out' })
    expect(screen.getByText('Skip anytime')).toBeTruthy()
    expect(screen.queryByText(/Private/)).toBeNull()
    cleanup()
    render(<CheckIn service={fakeService({ ...exampleWellness, checkins: [], pairs: [], locked: true })} onClose={() => {}} />)
    await screen.findByRole('dialog', { name: 'Before you head out' })
    expect(screen.getByText('Private · skip anytime')).toBeTruthy()
  })

  test('a visitor without the passphrase is never asked how they feel', async () => {
    const service = fakeService()
    service.getWellness = vi.fn(async () => {
      throw Object.assign(new Error('HTTP 401'), { locked: true })
    })
    for (const phase of [null, 'after']) {
      const onClose = vi.fn()
      render(<CheckIn service={service} onClose={onClose} phase={phase} />)
      await waitFor(() => expect(onClose).toHaveBeenCalled())
      expect(screen.queryByRole('dialog')).toBeNull()
      cleanup()
    }
    expect(service.postMood).not.toHaveBeenCalled()
    // a backend that is merely unreachable still lets the person try
    service.getWellness = vi.fn(async () => {
      throw new Error('HTTP 503')
    })
    render(<CheckIn service={service} onClose={() => {}} phase="after" />)
    expect(await screen.findByRole('dialog', { name: 'Now that you are back' })).toBeTruthy()
  })

  test('Settings turns the pop-up off and on, and shows the wellness view and the connection', async () => {
    window.localStorage.clear()
    render(<Settings service={fakeService(exampleWellness)} stamp="a" status="live" />)
    const box = screen.getByRole('checkbox', { name: 'Ask how I feel when I open Gary' })
    expect(box.checked).toBe(true)
    fireEvent.click(box)
    expect(box.checked).toBe(false)
    expect(window.localStorage.getItem('gary.askCheckIn')).toBe('no')
    expect(await screen.findByText('You reported feeling better after your outing.')).toBeTruthy()
    expect(screen.getByText('Backend: http://gary.test')).toBeTruthy()
    expect(screen.getByText(/Herds are ranked\. People never are\./)).toBeTruthy()
    expect(screen.getByText("Check-ins never show in Gary's world or the herd.")).toBeTruthy()
    window.localStorage.clear()
  })
})

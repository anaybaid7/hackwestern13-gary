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
import You, { suggestPhase } from './You.jsx'

afterEach(cleanup)

const NO_FLASH = { find: null, stageUp: false, cleared: [], rankUp: null, messages: [] }
const at = (text) => new Date(text)
const step = (n) => story.steps[n].state

describe('Gary (issue #25)', () => {
  test('draws the contract example: stage, climb, his line, the recap, the quest, the find', () => {
    render(<Home state={example} flash={NO_FLASH} now={at(example.journal[0].ts)} />)
    expect(screen.getByRole('heading', { name: 'Scrambler' })).toBeTruthy()
    expect(screen.getByAltText('Gary the goat, Scrambler')).toBeTruthy()
    expect(screen.getByText('80 XP. 70 more to Ibex.')).toBeTruthy()
    expect(screen.getByText('Today you and a friend found a bench at Harris Park.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Find a water bottle at your table' })).toBeTruthy()
    const find = screen.getByText('+80 XP').closest('li')
    expect(within(find).getByText('bench')).toBeTruthy()
    expect(within(find).getByText('new')).toBeTruthy()
    expect(within(find).getByText('Herd')).toBeTruthy()
    expect(within(find).getByText('quest')).toBeTruthy()
    expect(within(find).getByText(/named on the device in 41 ms/)).toBeTruthy()
    expect(within(find).getByText(/at Harris Park/)).toBeTruthy()
    // his line for the find is in the bubble and on the row
    expect(screen.getAllByText(/A bench\. I respect anything that holds still\./).length).toBe(2)
  })

  test('a fresh Gary naps: no guilt, no pressure, nothing lost', () => {
    render(<Home state={step(0)} flash={NO_FLASH} now={at(story.steps[0].now)} />)
    expect(screen.getByRole('heading', { name: 'Kid' })).toBeTruthy()
    expect(screen.getByAltText('Gary the goat, Kid, napping')).toBeTruthy()
    expect(screen.getByText(/Gary is napping\. No guilt/)).toBeTruthy()
    expect(screen.getByText('0 XP. 60 more to Scrambler.')).toBeTruthy()
    expect(screen.getByText('No finds yet today. Gary is in no hurry.')).toBeTruthy()
    expect(screen.getByText(/Nothing yet\. Point Gary at something/)).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/streak|missed|lost|sad/i)
  })

  test('a welcome-back line after a nap, and a napping pose that keeps the XP', () => {
    render(<Home state={step(9)} flash={NO_FLASH} now={at(story.steps[9].now)} />)
    expect(screen.getByText(/you are back\. Good\. I saved you a rock/)).toBeTruthy()
    cleanup()
    render(<Home state={step(7)} flash={NO_FLASH} now={at(story.steps[7].now)} />)
    expect(screen.getByAltText('Gary the goat, Scrambler, napping')).toBeTruthy()
    expect(screen.getByText('70 XP. 80 more to Ibex.')).toBeTruthy()
  })

  test('the top of the mountain and an empty quest list do not break the page', () => {
    const top = {
      ...example,
      gary: { ...example.gary, stage: 'summit-elder', stage_index: 3, xp: 400, stage_xp: 300, next_stage_xp: null },
      quest: null, quest_choice: null, quest_options: { short: null, long: null }, quests_open: 0,
    }
    render(<Home state={top} flash={NO_FLASH} now={at(example.journal[0].ts)} />)
    expect(screen.getByRole('heading', { name: 'Summit Elder' })).toBeTruthy()
    expect(screen.getByText('400 XP. Gary is at the summit.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Every quest is done' })).toBeTruthy()
    expect(screen.getAllByText('none open').length).toBe(2)
  })

  test('a new find is celebrated, and a stage Gary does not know yet still draws', () => {
    const flash = { ...NO_FLASH, find: example.journal[0], stageUp: true }
    const { container } = render(<Home state={example} flash={flash} now={at(example.journal[0].ts)} />)
    expect(container.querySelector('.burst')).toBeTruthy()
    expect(container.querySelector('.gary.grew')).toBeTruthy()
    expect(container.querySelector('.find.fresh')).toBeTruthy()
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
    expect(screen.getByText(/At Springbank Park\. Sniff a bicycle, about 15 minutes\. Worth 20 XP\./)).toBeTruthy()
    const link = screen.getByRole('link', { name: 'london.ca' })
    expect(link.getAttribute('href')).toBe('https://london.ca/parks-london')
    expect(screen.getByText(/Found by the scout on/)).toBeTruthy()
    expect(screen.getByText(/6 quests open/)).toBeTruthy()
    // the scout's line about where to stand
    expect(screen.getByText('Any safe, accessible spot in the park counts. Stay on public paths.')).toBeTruthy()
  })

  test('two buttons, short and long, ask for a quest of that length', () => {
    const onChoose = vi.fn()
    render(<QuestCard quest={scoutQuest} choice="short" options={step(2).quest_options} open={6} onChoose={onChoose} />)
    const short = screen.getByRole('button', { name: /Short/ })
    const long = screen.getByRole('button', { name: /Long/ })
    expect(short.getAttribute('aria-pressed')).toBe('true')
    expect(long.getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(long)
    fireEvent.click(short)
    expect(onChoose.mock.calls).toEqual([['long'], ['short']])
    expect(screen.getByText(/Press the same button again for a different quest/)).toBeTruthy()
  })

  test('a length with nothing open cannot be pressed, and a co-op quest says what it needs', () => {
    const onChoose = vi.fn()
    const herdQuest = step(3).quest // the Gibbons Park quest for two
    render(<QuestCard quest={herdQuest} choice={null} options={{ short: herdQuest, long: null }} open={1} onChoose={onChoose} />)
    expect(screen.getByText('Needs a friend in the frame.')).toBeTruthy()
    const long = screen.getByRole('button', { name: /Long/ })
    expect(long.disabled).toBe(true)
    fireEvent.click(long)
    expect(onChoose).not.toHaveBeenCalled()
    expect(screen.getByText(/Pick how long you have/)).toBeTruthy()
    expect(screen.getByText(/1 quest open/)).toBeTruthy()
  })

  test('a seed quest is not passed off as the scout\'s', () => {
    render(<QuestCard quest={example.quest} choice={null} options={example.quest_options} open={2} />)
    expect(screen.getByText('A starter quest. The scout did not find this one.')).toBeTruthy()
    expect(screen.queryByText(/Found by the scout/)).toBeNull()
  })

  test('only a quest from a live agent run is credited to the scout, whatever address it carries', () => {
    // scout.py --from-file: hand-written places, with the page a person took them from
    const sample = { ...scoutQuest, source: 'sample' }
    const { unmount } = render(<QuestCard quest={sample} choice={null} options={{}} open={1} />)
    expect(screen.getByText('A sample quest, written by hand. The scout did not find this one.')).toBeTruthy()
    expect(screen.queryByText(/Found by the scout/)).toBeNull()
    expect(screen.queryByRole('link')).toBeNull()
    unmount()
    // a quest someone posted by hand with an address
    const byHand = render(<QuestCard quest={{ ...scoutQuest, source: 'manual' }} choice={null} options={{}} open={1} />)
    expect(screen.getByText('A starter quest. The scout did not find this one.')).toBeTruthy()
    expect(screen.queryByText(/Found by the scout/)).toBeNull()
    byHand.unmount()
    // the scout's quest with something that is not a web address: no link is made of it
    for (const source_url of ['javascript:alert(1)', 'data:text/html,hello', null, 'london.ca']) {
      const view = render(<QuestCard quest={{ ...scoutQuest, source_url }} choice={null} options={{}} open={1} />)
      expect(screen.getByText('Found by the scout.')).toBeTruthy()
      expect(screen.queryByRole('link')).toBeNull()
      view.unmount()
    }
  })
})

describe('Map (issue #26)', () => {
  test('always 5 by 5: a cleared tile shows its name, fog shows nothing', () => {
    const { container } = render(<MapScreen map={example.map} flash={NO_FLASH} questPlace="Hack Western, your table" />)
    expect(container.querySelectorAll('.tile').length).toBe(25)
    expect(container.querySelectorAll('.tile.cleared').length).toBe(1)
    expect(container.querySelector('.tile.cleared').textContent).toBe('Harris Park')
    for (const fog of container.querySelectorAll('.tile.fog, .tile.empty')) expect(fog.textContent).toBe('')
    expect(container.querySelectorAll('button.tile').length).toBe(3) // only real places can be tapped
    expect(screen.getByText(/1 of 3 places uncovered/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Fog. Your quest is here' })).toBeTruthy()
  })

  test('tapping a cleared tile shows what was found there and when', () => {
    render(<MapScreen map={example.map} flash={NO_FLASH} />)
    expect(screen.getByText(/Tap an uncovered place/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Harris Park, uncovered' }))
    expect(screen.getByRole('heading', { name: 'Harris Park' })).toBeTruthy()
    expect(screen.getByText(/Uncovered on/)).toBeTruthy()
    expect(screen.getByText(/A bench, at .*with a friend in the frame\./)).toBeTruthy()
    // tapping fog names nothing
    fireEvent.click(screen.getAllByRole('button', { name: 'Fog' })[0])
    expect(screen.getByText(/Something is out here/)).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Harris Park' })).toBeNull()
  })

  test('the tile that just cleared is marked for its animation', () => {
    const { container } = render(<MapScreen map={example.map} flash={{ ...NO_FLASH, cleared: ['Harris Park'] }} />)
    expect(container.querySelector('.tile.cleared.fresh').textContent).toBe('Harris Park')
    expect(container.querySelectorAll('.tile.fresh').length).toBe(1)
  })

  test('more than 25 places still draws 25 tiles', () => {
    const many = Array.from({ length: 30 }, (_, i) => ({ place: `Place ${i}`, quest_id: `q-${i}`, cleared: false, finds: [] }))
    const { container } = render(<MapScreen map={many} flash={NO_FLASH} />)
    expect(container.querySelectorAll('.tile').length).toBe(25)
  })
})

describe('Field guide and journal (issue #27)', () => {
  test('all 79 things: found ones named and in colour, the rest locked silhouettes', () => {
    const { container } = render(<Guide guide={example.guide} journal={example.journal} now={at(example.journal[0].ts)} flash={NO_FLASH} />)
    expect(screen.getByText('1 of 79 found')).toBeTruthy()
    expect(container.querySelectorAll('.specimen').length).toBe(79)
    expect(container.querySelectorAll('.specimen.got').length).toBe(1)
    expect(container.querySelectorAll('.specimen.locked').length).toBe(78)
    expect(container.querySelector('.specimen.got').textContent).toContain('bench')
    expect(container.querySelectorAll('.specimen.locked .thing-icon.locked').length).toBe(78)
    expect(container.querySelector('.specimen.locked').getAttribute('aria-label')).toBe('Not found yet')
    expect(screen.getByText('1 of 33')).toBeTruthy() // outdoors
    expect(screen.getByText('0 of 46')).toBeTruthy() // indoors
  })

  test('the counter comes from the state, not from counting on the page', () => {
    render(<Guide guide={{ total: 79, found: step(9).guide.found }} journal={[]} now={at(story.steps[9].now)} flash={NO_FLASH} />)
    expect(screen.getByText('4 of 79 found')).toBeTruthy()
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
    expect(within(lists[0]).getByText(/named on the device in 41 ms/)).toBeTruthy()
  })

  test('a thing found just now is highlighted', () => {
    const flash = { ...NO_FLASH, find: example.journal[0] }
    const { container } = render(<Guide guide={example.guide} journal={example.journal} now={at(example.journal[0].ts)} flash={flash} />)
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
    expect(screen.getByText('2 more points to pass The Bleat Goes On.')).toBeTruthy()
    expect(screen.getByText(/Herds compete\. People are never ranked\. The rival herds are demo data\./)).toBeTruthy()
    expect(screen.getByText(/Your herd is 3rd of 6 this week/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Herd Cup, week 47' })).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/leaderboard|your rank among friends|last place/i)
  })

  test('a new herd is shown its own row, never last, with the next step up', () => {
    const { container } = render(<Herd herd={step(0).herd} journal={[]} flash={NO_FLASH} />)
    expect(container.querySelectorAll('.cup-row').length).toBe(4)
    expect(container.querySelector('.cup-row.you .cup-rank').textContent).toBe('5')
    expect(screen.getByText('1 more point to pass Kid You Not.')).toBeTruthy()
    expect(screen.getByText(/Your herd is 5th of 6 this week/)).toBeTruthy()
  })

  test('the friend-in-frame confirmation, the co-op quest and the shared badges', () => {
    const { container } = render(<Herd herd={example.herd} journal={example.journal} flash={NO_FLASH} />)
    expect(screen.getByText(/Friend in the frame: confirmed by Gary's camera at .* on the bench\./)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Find a backpack, with a friend in frame' })).toBeTruthy()
    expect(screen.getByText(/It only completes with a friend in the frame/)).toBeTruthy()
    expect([...container.querySelectorAll('.badge.earned .badge-name')].map((el) => el.textContent)).toEqual(['First herd', 'Herd quest'])
    expect(container.querySelectorAll('.badge').length).toBe(4)
    expect(screen.getByText('Five finds together')).toBeTruthy() // how to earn the next one
    expect(screen.getByText(/Gary never identifies anyone/)).toBeTruthy()
    cleanup()
    render(<Herd herd={step(0).herd} journal={step(4).journal} flash={NO_FLASH} />)
    expect(screen.getByText(/No friend in the last sniff/)).toBeTruthy()
  })

  test('moving up the cup is marked and said', () => {
    const { container } = render(<Herd herd={example.herd} journal={example.journal} flash={{ ...NO_FLASH, rankUp: { from: 5, to: 3 } }} />)
    expect(container.querySelector('.cup-row.you.moved')).toBeTruthy()
    expect(screen.getByText(/Up from 5th to 3rd\./)).toBeTruthy()
  })

  test('leading the cup, no co-op quest, and a badge this page has never heard of', () => {
    const herd = {
      ...example.herd, quest: null, badges: ['first-herd', 'moon-walkers'],
      cup: { ...example.herd.cup, rank: 1, ahead: null, table: [{ herd: 'Your herd', score: 9, quests: 5, places: 4, you: true }] },
    }
    render(<Herd herd={herd} journal={[]} flash={NO_FLASH} />)
    expect(screen.getByText('Your herd leads this week.')).toBeTruthy()
    expect(screen.getByText('No co-op quest is open right now.')).toBeTruthy()
    expect(screen.getByText('moon-walkers')).toBeTruthy()
  })
})

describe('You: the private check-in and the wellness view (issue #30)', () => {
  function fakeService(wellness = exampleWellness, now = '2026-11-21T06:00:00Z') {
    return {
      mode: 'live',
      now: () => new Date(now),
      postMood: vi.fn(async () => ({ ok: true })),
      getWellness: vi.fn(async () => wellness),
    }
  }

  test('a clear private label, and the view the backend wrote', async () => {
    render(<You service={fakeService()} stamp="a" />)
    expect(screen.getByText(/Private\. Only you see this page/)).toBeTruthy()
    expect(await screen.findByText('You reported feeling better after your outing.')).toBeTruthy()
    expect(screen.getByText('3 to 4')).toBeTruthy()
    expect(screen.getByText(/Okay before, Good after, 35 minutes apart/)).toBeTruthy()
    expect(screen.getByText('10 min')).toBeTruthy()
    expect(screen.getByText(/About 10 minutes in all\. An estimate from Gary's sniffs/)).toBeTruthy()
    expect(screen.getByText('0 finds alone, 1 with a friend in the frame.')).toBeTruthy()
    expect(screen.queryByText(/Demo data/)).toBeNull()
  })

  test('a tap sends the check-in, as a "before" when none is open', async () => {
    const service = fakeService({ ...exampleWellness, checkins: [], pairs: [] })
    render(<You service={service} stamp="a" />)
    expect(await screen.findByRole('heading', { name: 'Before you head out' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '4: Good' }))
    await waitFor(() => expect(service.postMood).toHaveBeenCalledWith('before', 4))
    expect(await screen.findByRole('heading', { name: 'Noted' })).toBeTruthy()
    expect(screen.getByText(/Good \(4 of 5\), before heading out\. Only you see this\./)).toBeTruthy()
    expect(service.getWellness.mock.calls.length).toBe(2) // loaded, then loaded again after the tap
  })

  test('with a "before" already in today, the next one is offered as an "after"', async () => {
    const open = { ...exampleWellness, checkins: [{ ts: '2026-11-21T17:00:00Z', phase: 'before', value: 3, source: 'device' }], pairs: [] }
    const service = fakeService(open, '2026-11-21T17:01:00Z')
    render(<You service={service} stamp="a" />)
    expect(await screen.findByRole('heading', { name: 'Now that you are back' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '5: Great' }))
    await waitFor(() => expect(service.postMood).toHaveBeenCalledWith('after', 5))
    expect(suggestPhase(open.checkins, new Date('2026-11-21T17:01:00Z'))).toBe('after')
    expect(suggestPhase(exampleWellness.checkins, new Date('2026-11-21T05:51:00Z'))).toBe('before') // the pair is complete
    expect(suggestPhase(open.checkins, new Date('2026-11-23T17:01:00Z'))).toBe('before') // a new day starts fresh
  })

  test('the person can say which kind of check-in it is', async () => {
    const service = fakeService({ ...exampleWellness, checkins: [], pairs: [] })
    render(<You service={service} stamp="a" />)
    fireEvent.click(await screen.findByRole('button', { name: 'I am already back' }))
    expect(screen.getByRole('heading', { name: 'Now that you are back' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '2: A bit low' }))
    await waitFor(() => expect(service.postMood).toHaveBeenCalledWith('after', 2))
  })

  test('every emotional question can be skipped, and skipping sends nothing', async () => {
    const service = fakeService()
    render(<You service={service} stamp="a" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Skip' }))
    expect(screen.getByText('Nothing was recorded. Check-ins are always optional.')).toBeTruthy()
    expect(service.postMood).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: '3: Okay' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Check in after all' }))
    expect(screen.getByRole('button', { name: '3: Okay' })).toBeTruthy()
  })

  test('seeded history is labelled as demo data, wherever it comes from', async () => {
    // mock mode: the story's own wellness, marked demo by the mock service
    render(<You service={fakeService({ ...exampleWellness, demo: true })} stamp="a" />)
    expect(await screen.findByText('Demo data from the demo story. Not yours.')).toBeTruthy()
    cleanup()
    // live with little history: a sample week can be shown, and it says what it is
    render(<You service={fakeService({ ...exampleWellness, pairs: [], summary: 'No before-and-after check-ins yet. They are always optional.' })} stamp="a" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Show a sample week (demo data)' }))
    expect(screen.getByText('A sample week. Demo data, not yours.')).toBeTruthy()
    expect(screen.getByText('You reported feeling better after 3 of 4 outings.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Back to my own view' }))
    expect(screen.queryByText(/Demo data/)).toBeNull()
    expect(screen.getByText('No before-and-after check-ins yet. They are always optional.')).toBeTruthy()
  })

  test('a backend that cannot be reached is said plainly', async () => {
    const service = fakeService()
    service.getWellness = vi.fn(async () => {
      throw new Error('HTTP 503')
    })
    render(<You service={service} stamp="a" />)
    expect(await screen.findByText(/Could not load your wellness view \(HTTP 503\)/)).toBeTruthy()
  })
})

// Gary's voice and the recap of the day (issue #25). Run with: npm test
import { expect, test } from 'vitest'
import example from '../../contract/examples/state.json'
import story from '../../contract/examples/story.json'
import { garyLine, lineFor, recap, withArticle } from './voice.js'

const entry = (more) => ({ id: 'e-1', label: 'bench', new: true, friend: false, quest_id: null, xp: 10, ...more })

test('a first find of a thing gets its own line', () => {
  expect(lineFor(entry())).toBe('A bench. I respect anything that holds still.')
  expect(lineFor(entry({ label: 'dog' }))).toMatch(/^A dog\./)
})

test('the same entry always gets the same line, and different entries vary', () => {
  const again = entry({ new: false })
  expect(lineFor(again)).toBe(lineFor({ ...again }))
  const lines = new Set(Array.from({ length: 40 }, (_, i) => lineFor(entry({ id: `e-${i}`, label: 'zebra', new: false }))))
  expect(lines.size).toBeGreaterThan(1)
})

test('quests, repeats and friends each sound different', () => {
  const quest = lineFor(entry({ label: 'zebra', new: false, quest_id: 'q-1' }))
  const repeat = lineFor(entry({ label: 'zebra', new: false }))
  const fresh = lineFor(entry({ label: 'zebra' }))
  expect(new Set([quest, repeat, fresh]).size).toBe(3)
  expect(lineFor(entry({ friend: true }))).toMatch(/herd|Two of you/)
  expect(lineFor(entry({ friend: true })).startsWith('A bench.')).toBe(true)
})

test('every line is short, and none of them nags or guilts', () => {
  const labels = ['bench', 'dog', 'bird', 'bicycle', 'bottle', 'backpack', 'fire hydrant', 'stop sign', 'car', 'laptop', 'zebra']
  for (const label of labels) {
    for (const more of [{}, { new: false }, { quest_id: 'q' }, { friend: true }, { new: false, friend: true }]) {
      for (let i = 0; i < 5; i += 1) {
        const line = lineFor(entry({ label, id: `x-${i}`, ...more }))
        expect(line.length, line).toBeLessThan(120)
        expect(line.toLowerCase()).not.toMatch(/should|lazy|missed|streak|shame|failed|only \d+|must/)
      }
    }
  }
})

test('what Gary says under his picture', () => {
  const gary = { napping: false, welcome_back: false }
  expect(garyLine({ ...gary, napping: true }, entry())).toMatch(/napping\. No guilt/)
  expect(garyLine({ ...gary, welcome_back: true }, entry())).toMatch(/you are back/)
  expect(garyLine(gary, entry())).toBe(lineFor(entry()))
  expect(garyLine(gary, undefined)).toMatch(/awake and nosy/)
})

test('a or an, and things that take neither', () => {
  expect(withArticle('bench')).toBe('a bench')
  expect(withArticle('apple')).toBe('an apple')
  expect(withArticle('umbrella')).toBe('an umbrella')
  expect(withArticle('skis')).toBe('skis')
})

test('the recap is one sentence about today', () => {
  const now = new Date('2026-11-21T15:41:00Z')
  expect(recap([], now)).toBe('No finds yet today. Gary is in no hurry.')
  const state = story.steps[5].state // bicycle at Springbank Park, a fire hydrant, then a dog with a friend at Gibbons Park
  expect(recap(state.journal, now)).toBe(
    'Today you and a friend found a bicycle, a fire hydrant and a dog at Springbank Park and Gibbons Park.',
  )
  // yesterday's finds are not today's
  expect(recap(state.journal, new Date('2026-11-22T16:00:00Z'))).toBe('No finds yet today. Gary is in no hurry.')
  // alone, one find, one place
  expect(recap(example.journal.map((e) => ({ ...e, friend: false })), new Date(example.journal[0].ts))).toBe(
    'Today you found a bench at Harris Park.',
  )
  // more than three things are counted, and a find with no place has no "at"
  const many = ['dog', 'cup', 'kite', 'bird', 'car'].map((label, i) => entry({ id: `m-${i}`, label, ts: '2026-11-21T15:00:00Z', place: null }))
  expect(recap(many, now)).toBe('Today you found a car, a bird, a kite and 2 more.')
})

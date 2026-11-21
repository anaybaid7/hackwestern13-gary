// Gary's voice (issue #25). One short line for each find, a fact about the
// thing, and a one-sentence recap of the day. Picked here, on the web side;
// the backend sends facts only. The words are in gary_lines.json, written
// once by Gemini (scout/gary_lines.py) and read by a person, so Gary talks
// with no network at all. The few hand-written lines below are only a
// fallback for a pool the file leaves empty.
//
// Gary is a mountain goat: dry, nosy, unimpressed by flat ground. He never
// nags and never guilts. Missing a day is a nap, nothing more.
import { isToday, list } from './format.js'
import written from './gary_lines.json'
import { STAGES, STAGE_NAMES } from './words.js'

const THINGS = written.things ?? {}
const FALLBACK = {
  quest: ['Quest done. I knew you could walk that far.'],
  new: ['New to me. Writing it down.'],
  again: ['Seen one. Still counts, a little.'],
  friend: ['And you brought someone. That is a herd.'],
  napping: ['Zzz. Gary is napping. No guilt. He was tired anyway.'],
  welcome_back: ['Oh, you are back. Good. I saved you a rock.'],
  awake: ['Gary is awake and nosy. Point him at something.'],
}
/** Gary's lines for one situation: Gemini's, else the fallback. */
export const pool = (name) => (written.pools?.[name]?.length ? written.pools[name] : FALLBACK[name])

/** A small, stable number from a string, so one entry always gets the same line. */
function pick(lines, key) {
  let sum = 0
  for (const ch of String(key)) sum = (sum * 31 + ch.charCodeAt(0)) % 9973
  return lines[sum % lines.length]
}

/** Gary's line for one journal entry. The same entry always gets the same line. */
export function lineFor(entry) {
  const own = THINGS[entry.label]?.line
  let line
  if (entry.quest_id) line = own && entry.new ? own : pick(pool('quest'), entry.id)
  else if (entry.new) line = own ?? pick(pool('new'), entry.id)
  else line = pick(pool('again'), entry.id)
  return entry.friend ? `${line} ${pick(pool('friend'), entry.id)}` : line
}

/** A fact Gary knows about what was found, or null. The same entry always gets the same one. */
export function factFor(entry) {
  const facts = THINGS[entry?.label]?.facts ?? []
  return facts.length ? pick(facts, entry.id) : null
}

/** One of the quest's trail tidbits (from the scout, with Gemini), or null. Stable for a quest. */
export function tidbitFor(quest, salt = '') {
  const lines = quest?.tidbits ?? []
  return lines.length ? pick(lines, `${quest.id}${salt}`) : null
}

const ALMOST_XP = 25 // this close to the next stage, Gary mentions it

/**
 * Gary's line about your own progress: today's finds (or today's quest, if
 * there are none yet), and how close he is to growing. Gemini wrote the
 * templates (gary_lines.json "progress"); the numbers come from the state.
 * Null when the file has none.
 */
export function progressLine(state, now = new Date()) {
  const templates = written.progress ?? {}
  const { gary, journal = [], quest, guide } = state
  const today = journal.filter((entry) => isToday(entry.ts, now)).length
  const next = STAGES[gary.stage_index + 1]
  const xpLeft = gary.next_stage_xp == null ? null : gary.next_stage_xp - gary.xp
  const slots = {
    target: quest ? withArticle(quest.target) : null,
    place: quest?.place,
    finds_today: `${today} find${today === 1 ? '' : 's'}`,
    last: journal[0] ? withArticle(journal[0].label) : null,
    xp_left: xpLeft == null ? null : `${xpLeft} XP`,
    next_stage: next ? (STAGE_NAMES[next] ?? next) : null,
    guide: guide ? `${guide.found.length} of ${guide.total} things` : null,
  }
  const key = `${journal[0]?.id ?? 'none'}:${today}`
  const say = (name) => {
    const usable = (templates[name] ?? []).filter((line) =>
      [...line.matchAll(/\{(\w+)\}/g)].every(([, slot]) => slots[slot] != null),
    )
    return usable.length ? pick(usable, key).replace(/\{(\w+)\}/g, (_, slot) => slots[slot]) : null
  }
  const parts = [today > 0 ? say('today') : quest ? say('start') : null]
  // then: how close he is to growing, or else a nudge for body, mind and friends outdoors
  parts.push(xpLeft != null && gary.xp > 0 && xpLeft <= ALMOST_XP ? say('almost') : say('encourage'))
  if (!parts.some(Boolean)) parts.push(say('guide'))
  const line = parts.filter(Boolean).join(' ')
  return line || null
}

/** What Gary says under his picture. */
export function garyLine(gary, latest) {
  const key = latest?.id ?? 'gary'
  if (gary.napping) return pick(pool('napping'), key)
  if (gary.welcome_back) return pick(pool('welcome_back'), key)
  if (latest) return lineFor(latest)
  return pick(pool('awake'), key)
}

const NO_ARTICLE = new Set(['skis', 'scissors', 'broccoli'])

/** "bench" -> "a bench", "apple" -> "an apple", "skis" -> "skis". */
export function withArticle(label) {
  if (NO_ARTICLE.has(label)) return label
  return `${/^[aeiou]/.test(label) ? 'an' : 'a'} ${label}`
}

/**
 * One sentence about today: "Today you and a friend found a bench and a dog at
 * Harris Park." It says "you and a friend" only when a friend was in the frame
 * for every find; otherwise it says how many were shared.
 */
export function recap(journal, now) {
  const today = journal.filter((entry) => isToday(entry.ts, now))
  if (today.length === 0) return 'No finds yet today. Gary is in no hurry.'
  const labels = [...new Set(today.map((entry) => entry.label))].reverse() // oldest first
  const shown = labels.slice(0, 3).map(withArticle)
  if (labels.length > 3) shown.push(`${labels.length - 3} more`)
  const places = [...new Set(today.map((entry) => entry.place).filter(Boolean))].reverse()
  const where = places.length === 0 ? '' : places.length <= 2 ? ` at ${list(places)}` : ` at ${places.length} places`
  const shared = today.filter((entry) => entry.friend).length
  if (shared === today.length) return `Today you and a friend found ${list(shown)}${where}.`
  if (shared === 0) return `Today you found ${list(shown)}${where}.`
  return `Today you found ${list(shown)}, ${shared === 1 ? 'one' : 'some'} of them with a friend${where ? `,${where}` : ''}.`
}

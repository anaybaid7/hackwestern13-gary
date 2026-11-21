// Gary's voice (issue #25). One short line for each find, a fact about the
// thing, and a one-sentence recap of the day. Picked here, on the web side;
// the backend sends facts only. The hand-written lines below come first; the
// rest are in gary_lines.json, written once by Gemini (scout/gary_lines.py)
// and read by a person, so Gary talks with no network at all.
//
// Gary is a mountain goat: dry, nosy, unimpressed by flat ground. He never
// nags and never guilts. Missing a day is a nap, nothing more.
import { isToday, list } from './format.js'
import written from './gary_lines.json'

const THINGS = written.things ?? {}
const POOLS = written.pools ?? {}

// Lines tied to a thing. Used the first time Gary finds it, and for quests.
const BY_THING = {
  bench: 'A bench. I respect anything that holds still.',
  dog: 'A dog. Loud, loyal, cannot climb. Still, a decent animal.',
  bird: 'A bird. It shows off about the flying, but fine.',
  bicycle: 'A bicycle. Two wheels and nobody fell off. Impressive.',
  bottle: 'A bottle. The lowland version of licking a glacier.',
  backpack: 'A backpack. Someone here is planning to go somewhere. Good.',
  'fire hydrant': 'A fire hydrant. Short, red, stubborn. We could be friends.',
  'stop sign': 'A stop sign. I have never once obeyed one.',
  'traffic light': 'A traffic light. It changed its mind three times while I watched.',
  car: 'A car. Fast. Cannot climb stairs.',
  bus: 'A bus. A whole herd in one box.',
  kite: 'A kite. A thing that climbs with no legs. Suspicious.',
  boat: 'A boat. Mountains do not need those.',
  umbrella: 'An umbrella. Rain is only the sky licking you.',
  skateboard: 'A skateboard. Four wheels, no hooves.',
  'sports ball': 'A ball. It rolls downhill. So do most things.',
  cat: 'A cat. Climbs well. Arrogant about it.',
  sheep: 'A sheep. A cousin. We do not talk.',
  laptop: 'A laptop. An indoor thing. Noted, barely.',
  cup: 'A cup. Indoors again, I see.',
  'cell phone': 'A phone. You are holding another one right now.',
  'potted plant': 'A potted plant. A snack that someone locked in a pot.',
  book: 'A book. I ate one once. Dry.',
  chair: 'A chair. A bench for one.',
}

// General lines, by what happened.
const QUEST = [
  'Quest done. I knew you could walk that far.',
  'That is the one I asked for. Well found.',
  'Done. The fog was getting boring anyway.',
  ...(POOLS.quest ?? []),
]
const NEW = ['New to me. Writing it down.', 'Never sniffed one of those before.', 'That goes in the field guide.', ...(POOLS.new ?? [])]
const AGAIN = ['Seen one. Still counts, a little.', 'Again. Fine. One point for effort.', 'I know that one. Hello again.', ...(POOLS.again ?? [])]
// kept short and hand-written: it is said after another line
const FRIEND = ['And you brought someone. That is a herd.', 'Two of you. Better than one.']

/** A small, stable number from a string, so one entry always gets the same line. */
function pick(lines, key) {
  let sum = 0
  for (const ch of String(key)) sum = (sum * 31 + ch.charCodeAt(0)) % 9973
  return lines[sum % lines.length]
}

/** Gary's line for one journal entry. The same entry always gets the same line. */
export function lineFor(entry) {
  const own = BY_THING[entry.label] ?? THINGS[entry.label]?.line
  let line
  if (entry.quest_id) line = own && entry.new ? own : pick(QUEST, entry.id)
  else if (entry.new) line = own ?? pick(NEW, entry.id)
  else line = pick(AGAIN, entry.id)
  return entry.friend ? `${line} ${pick(FRIEND, entry.id)}` : line
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

/** What Gary says under his picture. */
export function garyLine(gary, latest) {
  if (gary.napping) return 'Zzz. Gary is napping. No guilt. He was tired anyway.'
  if (gary.welcome_back) return 'Oh, you are back. Good. I saved you a rock.'
  if (latest) return lineFor(latest)
  return 'Gary is awake and nosy. Point him at something.'
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

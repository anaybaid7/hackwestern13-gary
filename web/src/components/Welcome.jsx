// Meet Gary: the first thing a new person sees. Gary wakes up, steps outside,
// and lets you try his three moves once each: sniff a thing through his eye,
// pick a walk and watch the fog lift, say how you feel. Five short beats,
// under half a minute. Nothing here talks to the backend and nothing is
// saved, except that this device remembers it has met Gary.
//
// Two small meters fill as you go, one for each side of Gary: Adventure
// (sniffs and quests) and Health (the walk a quest is, and the check-in).
//
// Gary says every line out loud when Sound is on: the clips are made by
// device/make_voice.py (ElevenLabs), like the rest of his voice. A clip that
// is missing falls back to a chime, so the walkthrough never depends on it.
import { useEffect, useRef, useState } from 'react'
import Gary from './Gary.jsx'
import ThingIcon from './ThingIcon.jsx'
import { VOICE, playClip, playVoice, readSound, unlockSound } from '../sound.js'
import { garySrc } from '../sprites.js'
import { MOOD_WORDS } from '../words.js'

const MET_KEY = 'gary.met'

/** Has this device met Gary? Storage may be missing: then he introduces himself each visit. */
export function readMet() {
  try {
    return window.localStorage.getItem(MET_KEY) === 'yes'
  } catch {
    return false
  }
}

export function writeMet(met) {
  try {
    if (met) window.localStorage.setItem(MET_KEY, 'yes')
    else window.localStorage.removeItem(MET_KEY)
  } catch {
    // no storage: nothing to remember
  }
}

const BEATS = ['wake', 'sniff', 'quest', 'feel', 'go']

// What Gary's eye passes over on the practice sniff, and where it is in the scene (percent).
export const TARGETS = [
  { name: 'duck', x: 20, y: 70 },
  { name: 'tree', x: 52, y: 38 },
  { name: 'bench', x: 82, y: 68 },
]
const PAN_MS = 1100

// Two real trails in London, Ontario, as examples of a short and a long walk.
export const WALKS = [
  { minutes: 15, place: 'Thames Valley Parkway', pin: '🌳', x: 42, y: 34, clears: [2, 3] },
  { minutes: 40, place: 'Medway Valley Trail', pin: '⛰️', x: 84, y: 48, clears: [2, 3, 4, 5] },
]
const FOG_COLS = 6
const FOG_ROWS = 4

// Gary's lines. The same words are in device/make_voice.py, which makes the clips.
export const LINES = {
  say_meet_wake: "Baa! I'm Gary, your pocket goat. I belong outside: trails, parks, hills. Come with me?",
  say_meet_sniff: 'On a walk, point me at things. Press my button to sniff.',
  say_meet_quest: 'I find quests on real trails near you. Pick a walk.',
  say_meet_walk: 'Off we go. Every walk lifts the fog.',
  say_meet_feel: 'Before we head out: how do you feel?',
  say_meet_felt: 'Thanks. I ask again after. Only you see it.',
  say_meet_go: "No streaks, no guilt. A break is just a nap. Let's get outside!",
}

/** The clips for a beat: what Gary says there, before and after you answer. */
export function clipsFor(beat, answer) {
  const answered = answer !== undefined && answer !== null
  switch (beat) {
    case 'wake':
      return answered ? ['say_meet_wake'] : []
    case 'sniff':
      return answered ? [`say_${answer}`, 'say_new'] : ['say_meet_sniff'] // his real voice for a first find
    case 'quest':
      return answered ? ['say_meet_walk'] : ['say_meet_quest']
    case 'feel':
      return answered ? ['say_meet_felt'] : ['say_meet_feel']
    default:
      return ['say_meet_go']
  }
}

/** The same, as words on the screen. */
export function garySays(beat, answer) {
  const answered = answer !== undefined && answer !== null
  if (beat === 'wake' && !answered) return 'Zzz…'
  if (beat === 'sniff' && answered) {
    return `That's ${/^[aeiou]/.test(answer) ? 'an' : 'a'} ${answer}! Ooh, a new one for the journal!`
  }
  return clipsFor(beat, answer)
    .map((clip) => LINES[clip])
    .join(' ')
}

const CHIMES = { wake: 'hello', sniff: 'new', quest: 'quest' }

function speak(beat, answer) {
  if (!readSound()) return
  const clips = clipsFor(beat, answer)
  if (clips.length === 0) return
  if (clips.every((clip) => VOICE[clip])) playVoice(clips)
  else if (answer !== undefined && CHIMES[beat]) playClip(CHIMES[beat]) // no voice for this line yet: a chime
}

const stillPlease = () => {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

export default function Welcome({ onDone }) {
  const [at, setAt] = useState(0)
  const [answers, setAnswers] = useState({})
  const [aim, setAim] = useState(0) // which thing Gary's eye is on
  const next = useRef(null)
  const beat = BEATS[at]
  const answer = answers[beat]
  const answered = answer !== undefined

  // once you have answered, Next is where the keyboard is
  useEffect(() => {
    if (answered || beat === 'go') next.current?.focus()
  }, [answered, beat])

  // Gary says each line as it appears
  useEffect(() => {
    speak(beat, answer)
  }, [beat, answer])

  // his eye wanders over the scene until you press the button
  useEffect(() => {
    if (beat !== 'sniff' || answered || stillPlease()) return undefined
    const timer = setInterval(() => setAim((i) => (i + 1) % TARGETS.length), PAN_MS)
    return () => clearInterval(timer)
  }, [beat, answered])

  function finish() {
    writeMet(true)
    onDone()
  }

  function give(value) {
    unlockSound() // this tap lets the browser play Gary's voice
    setAnswers((had) => ({ ...had, [beat]: value }))
  }

  const adventure = (answers.sniff ? 1 : 0) + (answers.quest ? 1 : 0)
  const health = (answers.quest ? 1 : 0) + (answers.feel ? 1 : 0)
  const outside = at > 0 || answered

  return (
    <section className="welcome" aria-label="Meet Gary">
      <header className="welcome-top">
        <Meter name="Adventure" filled={adventure} kind="adventure" />
        <Meter name="Health" filled={health} kind="health" />
        <button type="button" className="welcome-skip" onClick={finish}>
          Skip
        </button>
      </header>

      <div className={`welcome-stage beat-${beat}${outside ? ' outside' : ' inside'}${answered ? ' answered' : ''}`}>
        {beat === 'sniff' && <Eye aim={aim} found={answer} />}
        {beat === 'quest' && <Trails walk={WALKS.find((w) => w.minutes === answer)} />}
        {beat !== 'sniff' && beat !== 'quest' && (
          <>
            {outside && <Outdoors />}
            <Gary stage="kid" napping={!outside} grew={beat === 'go'} size={128} />
          </>
        )}
        {beat === 'sniff' && answered && <span className="welcome-pop chip chip-xp">+10 XP</span>}
        {beat === 'quest' && answered && <span className="welcome-pop chip chip-trail">Fog lifted</span>}
        {beat === 'feel' && answered && <span className="welcome-pop chip chip-herd">Private</span>}
      </div>

      <p className="welcome-says" aria-live="polite">
        {garySays(beat, answer)}
      </p>

      <div className="welcome-try">
        {beat === 'wake' && !answered && (
          <button type="button" className="welcome-press" onClick={() => give(true)} autoFocus>
            Press to wake him
          </button>
        )}
        {beat === 'sniff' && !answered && (
          <button type="button" className="welcome-press" onClick={() => give(TARGETS[aim].name)}>
            Sniff!
          </button>
        )}
        {beat === 'quest' && !answered && (
          <div className="welcome-things" role="group" aria-label="Pick a walk">
            {WALKS.map((walk) => (
              <button key={walk.minutes} type="button" className="welcome-thing" onClick={() => give(walk.minutes)}>
                <strong>{walk.minutes} min</strong>
                <span>{walk.place}</span>
              </button>
            ))}
          </div>
        )}
        {beat === 'feel' && !answered && (
          <div className="scale" role="group" aria-label="How are you feeling, from 1 to 5">
            {[1, 2, 3, 4, 5].map((value) => (
              <button key={value} type="button" className="scale-button" onClick={() => give(value)}
                      aria-label={`${value}: ${MOOD_WORDS[value]}`}>
                <span className="scale-number">{value}</span>
                <span className="scale-word">{MOOD_WORDS[value]}</span>
              </button>
            ))}
          </div>
        )}
        {beat === 'feel' && !answered && (
          <p className="small">Gary asks before and after each walk, so you can see whether getting outside lifts your mood. Only you see it.</p>
        )}
        {beat === 'feel' && answered && (
          <p className="small">Just practice: nothing was saved. Your real check-ins and how they change after walks are in Settings, under Wellness.</p>
        )}
        {answered && beat !== 'go' && (
          <button ref={next} type="button" className="button primary" onClick={() => setAt(at + 1)}>
            Next
          </button>
        )}
        {beat === 'go' && (
          <button ref={next} type="button" className="button primary" onClick={finish}>
            Let's go
          </button>
        )}
      </div>

      <ol className="welcome-steps" aria-label={`Step ${at + 1} of ${BEATS.length}`}>
        {BEATS.map((name, i) => (
          <li key={name} className={i < at ? 'done' : i === at ? 'here' : ''} />
        ))}
      </ol>
    </section>
  )
}

function Meter({ name, filled, kind }) {
  return (
    <p className={`welcome-meter meter-${kind}`} aria-label={`${name}: ${filled} of 2`}>
      <span className="welcome-meter-name">{name}</span>
      <span className={`welcome-pip${filled > 0 ? ' on' : ''}`} />
      <span className={`welcome-pip${filled > 1 ? ' on' : ''}`} />
    </p>
  )
}

/** Where Gary wants to be: sun, hills and a trail going off into them. */
function Outdoors({ pond = false }) {
  return (
    <svg className="welcome-scene" viewBox="0 0 120 80" preserveAspectRatio="none" aria-hidden="true" shapeRendering="crispEdges">
      <rect width="120" height="80" fill="#c8f56b" />
      <rect x="66" y="7" width="11" height="11" fill="#ff9f43" stroke="#14202b" strokeWidth="1.5" />
      <path d="M0 44 h10 v-6 h10 v-6 h14 v6 h10 v6 h12 v-8 h10 v-8 h16 v8 h10 v8 h18 v6 H0 z" fill="#a6de57" />
      <rect y="50" width="120" height="30" fill="#b6e960" />
      <path d="M50 80 h20 l-4 -10 h-8 l2 -10 h-4 l1 -10 h-2 l-1 10 h-4 l-2 10 h-6 z" fill="#fff4da" />
      {pond && <path d="M8 62 h26 v4 h4 v8 h-4 v4 H8 v-4 H4 v-8 h4 z" fill="#9ad8e6" stroke="#14202b" strokeWidth="1" />}
    </svg>
  )
}

/** Gary's eye: a viewfinder that wanders over the scene. Pressing the button sniffs what it is on. */
function Eye({ aim, found }) {
  const on = found ? TARGETS.find((t) => t.name === found) : TARGETS[aim]
  return (
    <div className="welcome-eye">
      <Outdoors pond />
      {TARGETS.map((thing) => (
        <span key={thing.name} className="welcome-target" style={{ left: `${thing.x}%`, top: `${thing.y}%` }}>
          <ThingIcon name={thing.name} />
        </span>
      ))}
      <span className={`welcome-reticle${found ? ' locked' : ''}`} style={{ left: `${on.x}%`, top: `${on.y}%` }}>
        {found && <b>{found}</b>}
      </span>
      <span className="welcome-eye-tag">Gary's eye</span>
      {found && <span className="welcome-flash" />}
    </div>
  )
}

/** A foggy map with two trails. Picking a walk sends Gary along it and lifts the fog he passes. */
function Trails({ walk }) {
  const cells = []
  for (let row = 0; row < FOG_ROWS; row += 1) {
    for (let col = 2; col < FOG_COLS; col += 1) {
      const lifting = walk?.clears.includes(col)
      cells.push(
        <span
          key={`${row}-${col}`}
          className={`welcome-fog${lifting ? ' lifting' : ''}`}
          style={{
            left: `${(col * 100) / FOG_COLS}%`,
            top: `${(row * 100) / FOG_ROWS}%`,
            width: `${100 / FOG_COLS + 0.5}%`,
            height: `${100 / FOG_ROWS + 0.5}%`,
            animationDelay: `${(col - 2) * 180 + row * 40}ms`,
          }}
        />,
      )
    }
  }
  const at = walk ? { x: walk.x - 9, y: walk.y + 14 } : { x: 12, y: 72 } // beside the pin, not on it
  return (
    <div className="welcome-trails">
      <svg className="welcome-scene" viewBox="0 0 120 80" preserveAspectRatio="none" aria-hidden="true" shapeRendering="crispEdges">
        <rect width="120" height="80" fill="#c8f56b" />
        <path d="M0 80 V60 h14 v-8 h12 v8 h20 v20 z" fill="#b6e960" />
        <path d="M60 0 h26 v10 h-8 v8 h-18 z M92 60 h28 v20 h-36 v-10 h8 z" fill="#a6de57" />
        {/* the two trails, as dots */}
        <path d="M14 58 L26 50 L38 40 L50 27" fill="none" stroke="#14202b" strokeWidth="2" strokeDasharray="2 4" />
        <path d="M14 58 L40 62 L64 56 L86 46 L100 38" fill="none" stroke="#14202b" strokeWidth="2" strokeDasharray="2 4" />
      </svg>
      {WALKS.map((w) => (
        <span key={w.minutes} className="welcome-pin" style={{ left: `${w.x}%`, top: `${w.y}%` }}>
          <i aria-hidden="true">{w.pin}</i>
          <b>{w.minutes} min</b>
        </span>
      ))}
      {cells}
      <img
        className={`welcome-walker${walk ? ' walking' : ''}`}
        src={garySrc('kid', false)}
        alt=""
        width="44"
        height="44"
        style={{ left: `${at.x}%`, top: `${at.y}%` }}
      />
    </div>
  )
}

// Meet Gary: the first thing a new person sees. Gary wakes up, says who he
// is and why, and lets you try his three moves once each: sniff a thing, pick
// a quest, say how you feel. Five short beats, one tap each, well under half
// a minute. Nothing here talks to the backend and nothing is saved, except
// that this device remembers it has met Gary.
//
// Two small meters fill as you go, one for each side of Gary: Adventure
// (sniffs and quests) and Health (the walk a quest is, and the check-in).
import { useEffect, useRef, useState } from 'react'
import Gary from './Gary.jsx'
import ThingIcon from './ThingIcon.jsx'
import { playClip, readSound, unlockSound } from '../sound.js'
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

const THINGS = ['duck', 'tree', 'bench']
const BEATS = ['wake', 'sniff', 'quest', 'feel', 'go']

/** What Gary says at a beat, before and after you answer. `answer` is what you picked. */
export function garySays(beat, answer) {
  const answered = answer !== undefined && answer !== null
  switch (beat) {
    case 'wake':
      return answered
        ? "Baa! I'm Gary, your pocket goat. Let's get outside together: move more, explore more."
        : 'Zzz…'
    case 'sniff':
      return answered
        ? `A ${answer}! New find, +10 XP.`
        : 'Point me at something outside and press my button. Try it.'
    case 'quest':
      return answered
        ? `${answer} minutes it is. We walk there, and fog lifts off our map. Friends welcome.`
        : 'I have quests at real places nearby. How long have you got?'
    case 'feel':
      return answered
        ? `${MOOD_WORDS[answer]}. I ask before and after a walk. Only you see it.`
        : 'One thing just for you. How do you feel right now?'
    default:
      return "That's me. No streaks, no guilt: a break is just a nap. Ready when you are."
  }
}

export default function Welcome({ onDone }) {
  const [at, setAt] = useState(0)
  const [answers, setAnswers] = useState({})
  const next = useRef(null)
  const beat = BEATS[at]
  const answer = answers[beat]
  const answered = answer !== undefined

  // once you have answered, Next is where the keyboard is
  useEffect(() => {
    if (answered || beat === 'go') next.current?.focus()
  }, [answered, beat])

  function finish() {
    writeMet(true)
    onDone()
  }

  function give(value, clip) {
    setAnswers((had) => ({ ...had, [beat]: value }))
    if (clip && readSound()) {
      unlockSound() // this tap is the one that lets the browser play sound
      playClip(clip)
    }
  }

  const adventure = (answers.sniff ? 1 : 0) + (answers.quest ? 1 : 0)
  const health = (answers.quest ? 1 : 0) + (answers.feel ? 1 : 0)

  return (
    <section className="welcome" aria-label="Meet Gary">
      <header className="welcome-top">
        <Meter name="Adventure" filled={adventure} kind="adventure" />
        <Meter name="Health" filled={health} kind="health" />
        <button type="button" className="welcome-skip" onClick={finish}>
          Skip
        </button>
      </header>

      <div className={`welcome-stage beat-${beat}`}>
        <Gary stage="kid" napping={beat === 'wake' && !answered} grew={beat === 'go'} size={144} />
        {beat === 'sniff' && answered && <span className="welcome-pop chip chip-xp">+10 XP</span>}
        {beat === 'quest' && answered && <span className="welcome-pop chip chip-trail">Fog lifted</span>}
        {beat === 'feel' && answered && <span className="welcome-pop chip chip-herd">Private</span>}
      </div>

      <p className="welcome-says" aria-live="polite">
        {garySays(beat, answer)}
      </p>

      <div className="welcome-try">
        {beat === 'wake' && !answered && (
          <button type="button" className="welcome-press" onClick={() => give(true, 'hello')} autoFocus>
            Press to wake him
          </button>
        )}
        {beat === 'sniff' && !answered && (
          <div className="welcome-things" role="group" aria-label="Something for Gary to sniff">
            {THINGS.map((thing) => (
              <button key={thing} type="button" className="welcome-thing" onClick={() => give(thing, 'new')}>
                <ThingIcon name={thing} />
                <span>{thing}</span>
              </button>
            ))}
          </div>
        )}
        {beat === 'quest' && !answered && (
          <div className="welcome-things" role="group" aria-label="How long have you got">
            <button type="button" className="welcome-thing" onClick={() => give(15, 'quest')}>
              <strong>15 min</strong>
              <span>a short one</span>
            </button>
            <button type="button" className="welcome-thing" onClick={() => give(40, 'quest')}>
              <strong>40 min</strong>
              <span>a long one</span>
            </button>
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
        {beat === 'feel' && answered && <p className="small">Just practice: nothing was saved.</p>}
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

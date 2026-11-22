// The check-in that greets you on the home screen, once per visit.
// Skipping sends nothing. Turn it off in Settings. Mood never leaves the
// private side: it goes to POST /api/mood and nowhere else.
//
// When the server locks the private side with a passphrase and this device
// does not have it, the sheet does not appear at all: a visitor is never
// asked how they feel on someone else's Gary. The owner opens the private
// side once, in Settings. The sheet says "Private" only when it is locked.
import { useEffect, useState } from 'react'
import { isToday } from '../format.js'
import { MOOD_WORDS } from '../words.js'

/** A "before" with no "after" yet today suggests the next check-in is an "after". */
export function suggestPhase(checkins = [], now = new Date()) {
  const today = checkins.filter((c) => isToday(c.ts, now))
  const last = today[today.length - 1]
  return last?.phase === 'before' ? 'after' : 'before'
}

const ASK_KEY = 'gary.askCheckIn'

/** Whether to ask on open. On unless turned off; browser storage may be missing. */
export function readAsk() {
  try {
    return window.localStorage.getItem(ASK_KEY) !== 'no'
  } catch {
    return true
  }
}

export function writeAsk(on) {
  try {
    window.localStorage.setItem(ASK_KEY, on ? 'yes' : 'no')
  } catch {
    // no storage: the choice lasts for this visit only
  }
}

export default function CheckIn({ service, onClose, phase: fixed = null }) {
  const [phase, setPhase] = useState(null) // null until the private side has answered
  const [locked, setLocked] = useState(false) // behind a passphrase, which this device has
  const [sent, setSent] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    service.getWellness().then(
      (w) => {
        if (!alive) return
        setLocked(Boolean(w.locked))
        setPhase(fixed ?? suggestPhase(w.checkins, service.now()))
      },
      (err) => {
        if (!alive) return
        if (err.locked) onClose() // locked, and no passphrase here: do not ask
        else setPhase(fixed ?? 'before')
      },
    )
    const onKey = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      alive = false
      window.removeEventListener('keydown', onKey)
    }
  }, [service, onClose, fixed])

  async function send(value) {
    try {
      await service.postMood(phase, value)
      setSent(value)
    } catch (err) {
      setError(String(err.message || err))
    }
  }

  if (!phase) return null
  return (
    <div className="modal-backdrop">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="checkin-modal-title">
        <p className="modal-top">{locked ? 'Private · skip anytime' : 'Skip anytime'}</p>
        {sent ? (
          <>
            <h2 id="checkin-modal-title">Noted</h2>
            <p>
              You're feeling <strong>{MOOD_WORDS[sent].toLowerCase()}</strong> ({sent} of 5).{' '}
              {phase === 'before'
                ? "Gary will ask again when you're back, so you can see what the walk did."
                : 'See how it compares with before you left in Settings, under Wellness.'}
            </p>
            <button type="button" className="button primary" onClick={onClose} autoFocus>
              {phase === 'before' ? 'Off we go' : 'Done'}
            </button>
          </>
        ) : (
          <>
            <h2 id="checkin-modal-title">{phase === 'before' ? 'Before you head out' : 'Now that you are back'}</h2>
            <p className="small">
              {phase === 'before'
                ? 'How do you feel right now? Gary asks again when you are back, so you can see whether the walk helped. Only you see this.'
                : 'How do you feel now? Compare it with before you left, in Settings, under Wellness. Only you see this.'}
            </p>
            <div className="scale" role="group" aria-label="How are you feeling, from 1 to 5">
              {[1, 2, 3, 4, 5].map((value) => (
                <button key={value} type="button" className="scale-button" onClick={() => send(value)}
                        aria-label={`${value}: ${MOOD_WORDS[value]}`}>
                  <span className="scale-number">{value}</span>
                  <span className="scale-word">{MOOD_WORDS[value]}</span>
                </button>
              ))}
            </div>
            {error && <p className="small">Not saved ({error}).</p>}
            <div className="detail-buttons">
              <button type="button" className="button" onClick={onClose} autoFocus>
                Skip
              </button>
              <button type="button" className="link" onClick={() => setPhase(phase === 'before' ? 'after' : 'before')}>
                {phase === 'before' ? 'Already back' : 'Heading out'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

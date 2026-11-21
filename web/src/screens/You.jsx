// The private side (issue #30): a before and an after check-in, and the
// wellness view. It comes from GET /api/wellness, which is never part of
// Gary's shared state. Every question here can be skipped.
//
// The page says only what is true about who can see it. When the server sets a
// passphrase the page is locked, and it says "private". When it does not,
// anyone who has the address can open it, and the page says that instead.
import { useCallback, useEffect, useState } from 'react'
import { dayName, isToday, plural } from '../format.js'
import { SAMPLE_WELLNESS } from '../services/sample_wellness.js'
import { MOOD_WORDS } from '../words.js'

/** A "before" with no "after" yet today suggests the next check-in is an "after". */
export function suggestPhase(checkins = [], now = new Date()) {
  const today = checkins.filter((c) => isToday(c.ts, now))
  const last = today[today.length - 1]
  return last?.phase === 'before' ? 'after' : 'before'
}

export default function You({ service, stamp }) {
  const [wellness, setWellness] = useState(null)
  const [error, setError] = useState(null)
  const [phase, setPhase] = useState(null) // null: use the suggestion
  const [sent, setSent] = useState(null)
  const [skipped, setSkipped] = useState(false)
  const [sample, setSample] = useState(false)
  const [locked, setLocked] = useState(false) // the server wants a passphrase this device does not have
  const [passphrase, setPassphrase] = useState('')
  const [wrong, setWrong] = useState(false)

  const failed = useCallback((err) => {
    if (err.locked) {
      setLocked(true)
      setWellness(null)
      setError(null)
    } else {
      setError(String(err.message || err))
    }
  }, [])

  const load = useCallback(
    () =>
      service.getWellness().then((next) => {
        setWellness(next)
        setLocked(false)
        setError(null)
      }, failed),
    [service, failed],
  )
  useEffect(() => {
    load()
  }, [load, stamp])

  const active = phase ?? suggestPhase(wellness?.checkins, service.now())
  const other = active === 'before' ? 'after' : 'before'

  async function send(value) {
    try {
      await service.postMood(active, value)
      setSent({ phase: active, value })
      setPhase(null)
      await load()
    } catch (err) {
      failed(err)
    }
  }

  async function open(event) {
    event.preventDefault()
    try {
      const next = await service.unlock(passphrase)
      setWellness(next)
      setLocked(false)
      setWrong(false)
      setPassphrase('')
    } catch (err) {
      if (err.locked) setWrong(true)
      else setError(String(err.message || err))
    }
  }

  function lockAgain() {
    service.forgetKey()
    setSent(null)
    setWellness(null)
    setLocked(true)
  }

  if (locked) {
    return (
      <div className="screen you">
        <h2>You</h2>
        <p className="private">This page is locked. It holds private check-ins, and it opens with a passphrase.</p>
        <form className="checkin unlock" onSubmit={open}>
          <label htmlFor="passphrase">Passphrase</label>
          <input id="passphrase" type="password" autoComplete="current-password" value={passphrase}
                 onChange={(event) => setPassphrase(event.target.value)} />
          <button type="submit" className="choice-button" disabled={!passphrase}>
            Open this page
          </button>
          {wrong && <p role="alert">That passphrase did not open it. Check it and try again.</p>}
          {error && <p role="alert">Could not reach the backend ({error}).</p>}
        </form>
        <p className="small">Gary's world needs no passphrase. Nothing on this page ever appears there.</p>
      </div>
    )
  }

  const shown = sample ? SAMPLE_WELLNESS : wellness
  const thin = wellness && wellness.pairs.length < 2 && !wellness.demo

  return (
    <div className="screen you">
      <h2>You</h2>
      {wellness?.demo ? (
        <p className="private">
          The private page. None of it appears in Gary's world, on the Herd screen or in the Herd Cup.
        </p>
      ) : wellness?.locked ? (
        <p className="private">
          Private. This page opens only with your passphrase. None of it appears in Gary's world, on the Herd screen
          or in the Herd Cup.{' '}
          <button type="button" className="link" onClick={lockAgain}>
            Lock it on this device
          </button>
        </p>
      ) : (
        <p className="private">
          Kept apart: none of this appears in Gary's world, on the Herd screen or in the Herd Cup.
          {wellness && ' This page is not locked, so anyone who has its address can open it. Setting GARY_PRIVATE_KEY on the server locks it.'}
        </p>
      )}

      <section className="checkin" aria-labelledby="checkin-title">
        {sent ? (
          <>
            <h3 id="checkin-title">Noted</h3>
            <p>
              {MOOD_WORDS[sent.value]} ({sent.value} of 5), {sent.phase === 'before' ? 'before heading out' : 'after coming back'}.
              It stays on this page.
            </p>
            <button type="button" className="link" onClick={() => setSent(null)}>
              Check in again
            </button>
          </>
        ) : skipped ? (
          <>
            <h3 id="checkin-title">Skipped</h3>
            <p>Nothing was recorded. Check-ins are always optional.</p>
            <button type="button" className="link" onClick={() => setSkipped(false)}>
              Check in after all
            </button>
          </>
        ) : (
          <>
            <h3 id="checkin-title">{active === 'before' ? 'Before you head out' : 'Now that you are back'}</h3>
            <p>How are you feeling right now?</p>
            <div className="scale" role="group" aria-label="How are you feeling, from 1 to 5">
              {[1, 2, 3, 4, 5].map((value) => (
                <button key={value} type="button" className="scale-button" onClick={() => send(value)}
                        aria-label={`${value}: ${MOOD_WORDS[value]}`}>
                  <span className="scale-number">{value}</span>
                  <span className="scale-word">{MOOD_WORDS[value]}</span>
                </button>
              ))}
            </div>
            <div className="checkin-row">
              <button type="button" className="link" onClick={() => setPhase(other)}>
                {other === 'before' ? 'I am about to head out instead' : 'I am already back'}
              </button>
              <button type="button" className="link" onClick={() => setSkipped(true)}>
                Skip
              </button>
            </div>
          </>
        )}
      </section>

      {error && <p className="empty">Could not load your wellness view ({error}).</p>}
      {!shown && !error && <p className="empty">Loading.</p>}
      {shown && (
        <section className="wellness" aria-label="Your wellness view">
          {shown.demo && (
            <p className="demo-note">
              {sample ? 'A sample week. Demo data, not yours.' : 'Demo data from the demo story. Not yours.'}
            </p>
          )}
          <p className="summary">{shown.summary}</p>

          <h3 className="section-title">Before and after</h3>
          {shown.pairs.length === 0 ? (
            <p className="empty">No pairs yet. Check in before you head out and again when you are back.</p>
          ) : (
            <ul className="pairs">
              {shown.pairs.map((pair, n) => (
                <li key={n}>
                  <span className="pair-day">{dayName(pair.day)}</span>
                  <span className="pair-values">
                    {pair.before} to {pair.after}
                  </span>
                  <span className="pair-words">
                    {MOOD_WORDS[pair.before]} before, {MOOD_WORDS[pair.after]} after
                    {pair.minutes ? `, ${pair.minutes} minutes apart` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h3 className="section-title">Time outdoors</h3>
          {shown.outdoor.length === 0 ? (
            <p className="empty">No outdoor finds yet.</p>
          ) : (
            <>
              <ul className="bars">
                {shown.outdoor.map((day) => (
                  <li key={day.day}>
                    <span className="bar-day">{dayName(day.day)}</span>
                    <span className="bar-track">
                      <span className="bar-fill"
                            style={{ width: `${Math.round((day.minutes / Math.max(...shown.outdoor.map((d) => d.minutes))) * 100)}%` }} />
                    </span>
                    <span className="bar-value">{day.minutes} min</span>
                  </li>
                ))}
              </ul>
              <p className="small">About {shown.outdoor_minutes} minutes in all. {shown.outdoor_note}</p>
            </>
          )}

          <h3 className="section-title">Alone and together</h3>
          <p>
            {plural(shown.solo, 'find')} alone, {shown.shared} with a friend in the frame.
          </p>
        </section>
      )}

      {(thin || sample) && (
        <button type="button" className="link" onClick={() => setSample(!sample)}>
          {sample ? 'Back to my own view' : 'Show a sample week (demo data)'}
        </button>
      )}
    </div>
  )
}

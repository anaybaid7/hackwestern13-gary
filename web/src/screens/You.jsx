// The private side (issue #30): the wellness view, and a button for a
// check-in. It comes from GET /api/wellness, which is never part of Gary's
// shared state. Every check-in can be skipped.
//
// The view says only what is true about who can see it. When the server sets
// a passphrase (GARY_PRIVATE_KEY) the view is locked: it asks for the
// passphrase once per device, shows nothing until it is right, and only then
// wears the "Private" chip. With no passphrase on the server, anyone who has
// the page's address can open this view, and it says so.
import { useCallback, useEffect, useState } from 'react'
import CheckIn, { suggestPhase } from '../components/CheckIn.jsx'
import { dayName } from '../format.js'
import { SAMPLE_WELLNESS } from '../services/sample_wellness.js'
import { MOOD_WORDS } from '../words.js'

export { suggestPhase }

export default function You({ service, stamp }) {
  const [wellness, setWellness] = useState(null)
  const [error, setError] = useState(null)
  const [checking, setChecking] = useState(false)
  const [sample, setSample] = useState(false)
  const [locked, setLocked] = useState(false) // the server wants a passphrase this device does not have
  const [passphrase, setPassphrase] = useState('')
  const [wrong, setWrong] = useState(false)

  const load = useCallback(
    () =>
      service.getWellness().then(
        (next) => {
          setWellness(next)
          setLocked(false)
          setError(null)
        },
        (err) => {
          if (err.locked) {
            setLocked(true)
            setWellness(null)
            setError(null)
          } else {
            setError(String(err.message || err))
          }
        },
      ),
    [service],
  )
  useEffect(() => {
    load()
  }, [load, stamp])

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
    setWellness(null)
    setSample(false)
    setLocked(true)
  }

  if (locked) {
    return (
      <div className="you">
        <div className="you-head">
          <h3 className="section-title">Wellness</h3>
          <span className="chip chip-herd">🔒 Locked</span>
        </div>
        <form className="unlock" onSubmit={open}>
          <p>Check-ins and this view are private. They open with a passphrase.</p>
          <label htmlFor="passphrase">Passphrase</label>
          <input id="passphrase" type="password" autoComplete="current-password" value={passphrase}
                 onChange={(event) => setPassphrase(event.target.value)} />
          <button type="submit" className="button primary" disabled={!passphrase}>
            Open
          </button>
          {wrong && <p role="alert">That passphrase did not open it.</p>}
          {error && <p role="alert">Could not reach the backend ({error}).</p>}
        </form>
      </div>
    )
  }

  const shown = sample ? SAMPLE_WELLNESS : wellness
  const thin = wellness && wellness.pairs.length < 2 && !wellness.demo
  const most = shown ? Math.max(1, ...shown.outdoor.map((d) => d.minutes)) : 1

  return (
    <div className="you">
      <div className="you-head">
        <h3 className="section-title">Wellness</h3>
        {wellness?.locked ? (
          <span className="chip chip-herd">🔒 Private</span>
        ) : wellness && !wellness.demo ? (
          <span className="chip chip-open">Not locked</span>
        ) : null /* the demo story says "Demo story data" just below, and nothing about locks */}
      </div>
      {wellness && !wellness.locked && !wellness.demo && (
        <p className="small">
          Kept out of Gary's world and the herd. But this view has no lock yet: anyone who has this page's address can
          open it. Setting GARY_PRIVATE_KEY on the server locks it.
        </p>
      )}

      {error && <p className="empty">Could not load ({error}).</p>}
      {!shown && !error && <p className="empty">Loading.</p>}
      {shown && (
        <section className="wellness" aria-label="Your wellness view">
          {shown.demo && <p className="demo-note">{sample ? 'Sample week · demo data' : 'Demo story data'}</p>}
          <p className="summary">{shown.summary}</p>

          <div className="stats">
            <Stat value={shown.pairs.length} label="outings" />
            <Stat value={shown.outdoor_minutes} label="min outside" title={shown.outdoor_note} />
            <Stat value={shown.shared} label="with a friend" />
          </div>

          {shown.pairs.length > 0 && (
            <ul className="pairs" aria-label="Before and after">
              {shown.pairs.map((pair, n) => (
                <li key={n}>
                  <span className="pair-day">{dayName(pair.day)}</span>
                  <Mood value={pair.before} />
                  <span className="pair-arrow" aria-hidden="true">→</span>
                  <Mood value={pair.after} />
                </li>
              ))}
            </ul>
          )}

          {shown.outdoor.length > 0 && (
            <ul className="bars" aria-label="Minutes outside">
              {shown.outdoor.map((day) => (
                <li key={day.day}>
                  <span className="bar-day">{dayName(day.day)}</span>
                  <span className="bar-track">
                    <span className="bar-fill" style={{ width: `${Math.round((day.minutes / most) * 100)}%` }} />
                  </span>
                  <span className="bar-value">{day.minutes} min</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <div className="detail-buttons">
        <button type="button" className="button primary" onClick={() => setChecking(true)}>
          Check in
        </button>
        {(thin || sample) && (
          <button type="button" className="link" onClick={() => setSample(!sample)}>
            {sample ? 'My own view' : 'Sample week'}
          </button>
        )}
        {wellness?.locked && (
          <button type="button" className="link" onClick={lockAgain}>
            Lock on this device
          </button>
        )}
      </div>

      {checking && (
        <CheckIn
          service={service}
          onClose={() => {
            setChecking(false)
            load()
          }}
        />
      )}
    </div>
  )
}

function Stat({ value, label, title }) {
  return (
    <div className="stat" title={title}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

function Mood({ value }) {
  return (
    <span className={`mood mood-${value}`} title={MOOD_WORDS[value]}>
      {value} <span className="mood-word">{MOOD_WORDS[value]}</span>
    </span>
  )
}

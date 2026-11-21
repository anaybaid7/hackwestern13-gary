// The private side (issue #30): the wellness view, and a button for a
// check-in. Private: it comes from GET /api/wellness, which is never part of
// Gary's shared state. Every check-in can be skipped.
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

  const load = useCallback(
    () =>
      service.getWellness().then(
        (next) => {
          setWellness(next)
          setError(null)
        },
        (err) => setError(String(err.message || err)),
      ),
    [service],
  )
  useEffect(() => {
    load()
  }, [load, stamp])

  const shown = sample ? SAMPLE_WELLNESS : wellness
  const thin = wellness && wellness.pairs.length < 2 && !wellness.demo
  const most = shown ? Math.max(1, ...shown.outdoor.map((d) => d.minutes)) : 1

  return (
    <div className="you">
      <div className="you-head">
        <h3 className="section-title">Wellness</h3>
        <span className="chip chip-herd">🔒 Private</span>
      </div>

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

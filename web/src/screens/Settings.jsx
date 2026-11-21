// Settings: the check-in pop-up, the private wellness view, where the page
// gets Gary's state from, a reset for testing, and the promises Gary keeps.
import { useState } from 'react'
import { readAsk, writeAsk } from '../components/CheckIn.jsx'
import { playClip, readSound, writeSound } from '../sound.js'
import You from './You.jsx'

const STATUS_WORDS = { live: 'Live', mock: 'Demo story', stale: 'Offline · last state' }

// Start over, for testing: Gary back to 0 XP, no finds, no check-ins. The
// quests stay and are all open again. It asks first, and a server that has an
// admin key asks for it; the key is sent with the reset and never kept.
function ResetGary({ service, onReset }) {
  const [phase, setPhase] = useState('idle') // idle | sure | busy | done
  const [needsKey, setNeedsKey] = useState(false)
  const [adminKey, setAdminKey] = useState('')
  const [problem, setProblem] = useState('')

  async function reset(event) {
    event.preventDefault()
    setPhase('busy')
    setProblem('')
    try {
      await service.resetGary(adminKey)
      setAdminKey('')
      setNeedsKey(false)
      setPhase('done')
      if (onReset) onReset()
    } catch (err) {
      if (err.needsKey) {
        setProblem(needsKey ? 'That admin key was not accepted.' : '')
        setNeedsKey(true)
      } else {
        setProblem(`Gary could not be reset (${err.message || err}).`)
      }
      setPhase('sure')
    }
  }

  return (
    <div className="reset">
      <h3 className="section-title">Testing</h3>
      <p>
        Start over: Gary goes back to 0 XP, with no finds and no check-ins. The quests stay, and every one is open
        again.
      </p>
      {phase === 'idle' || phase === 'done' ? (
        <button type="button" className="button" onClick={() => setPhase('sure')}>
          Reset Gary
        </button>
      ) : (
        <form className="reset-sure" onSubmit={reset}>
          <p>Forget every sniff and check-in?</p>
          {needsKey && (
            <>
              <label htmlFor="admin-key">This server wants its admin key</label>
              <input
                id="admin-key"
                type="password"
                autoComplete="off"
                value={adminKey}
                onChange={(event) => setAdminKey(event.target.value)}
              />
            </>
          )}
          <div className="reset-buttons">
            <button type="submit" className="button primary" disabled={phase === 'busy' || (needsKey && !adminKey)}>
              Yes, reset
            </button>
            <button type="button" className="button" onClick={() => setPhase('idle')} disabled={phase === 'busy'}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {problem && <p role="alert">{problem}</p>}
      {phase === 'done' && (
        <>
          <p role="status">Gary is reset.</p>
          <p className="small">
            Gary on the Pi keeps his own list of finished quests. To hear the quest sounds there again, restart him
            with: sh start_gary.sh --fresh
          </p>
        </>
      )}
    </div>
  )
}

export default function Settings({ service, stamp, status, onReset }) {
  const [ask, setAsk] = useState(readAsk)
  const [sound, setSound] = useState(readSound)

  function toggle() {
    writeAsk(!ask)
    setAsk(!ask)
  }

  function toggleSound() {
    writeSound(!sound)
    setSound(!sound)
    if (!sound) playClip('hello') // a hello, so you hear that it works
  }

  return (
    <div className="screen settings">
      <h2>Settings</h2>

      <section className="panel">
        <h3 className="section-title">Check-in</h3>
        <label className="switch">
          <input type="checkbox" checked={ask} onChange={toggle} />
          <span>Ask how I feel when I open Gary</span>
        </label>
      </section>

      <section className="panel">
        <h3 className="section-title">Sound</h3>
        <label className="switch">
          <input type="checkbox" checked={sound} onChange={toggleSound} />
          <span>Play Gary's sounds on this device</span>
        </label>
        <p className="small">
          A sound for each new find and each finished quest. Browsers stay quiet until you have tapped the page once.
        </p>
      </section>

      <section className="panel">
        <You service={service} stamp={stamp} />
      </section>

      <section className="panel">
        <h3 className="section-title">Connection</h3>
        <p>{STATUS_WORDS[status]}</p>
        {service.mode === 'live' && <p className="small">Backend: {service.api || 'this address'}</p>}
        <p className="small">
          {service.mode === 'mock' ? (
            <a href="?">Leave the demo story</a>
          ) : (
            <a href="?mock">Open the demo story</a>
          )}
        </p>
      </section>

      <section className="panel">
        <ResetGary service={service} onReset={onReset} />
      </section>

      <section className="panel">
        <h3 className="section-title">Gary's promises</h3>
        <ul className="promises">
          <li>No streaks. Breaks are naps.</li>
          <li>No photos kept. Only names of things.</li>
          <li>Friends are never identified.</li>
          <li>Herds are ranked. People never are.</li>
          <li>Check-ins never show in Gary's world or the herd.</li>
        </ul>
      </section>
    </div>
  )
}

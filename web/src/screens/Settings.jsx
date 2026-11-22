// Settings: the check-in pop-up, the private wellness view, where the page
// gets Gary's state from, a reset for testing, and the promises Gary keeps.
import { useEffect, useState } from 'react'
import { goatName } from '../auth.js'
import { readAsk, writeAsk } from '../components/CheckIn.jsx'
import { playClip, readSound, writeSound } from '../sound.js'
import { leaveNearby, readNearby, writeNearby } from '../nearby.js'
import You from './You.jsx'

const STATUS_WORDS = { live: 'Live', mock: 'Demo story', stale: 'Offline · last state' }

// Your account, with Auth0. Shown only when the server has a tenant set up.
// Signed in, your check-ins are kept as yours. Gary stores a fingerprint of
// your Auth0 id and nothing else, so here you are a goat name, not a person.
function Account({ service, onChange }) {
  const [account, setAccount] = useState(null)
  const [me, setMe] = useState(null)

  useEffect(() => {
    let alive = true
    if (!service.account) return undefined // a service with no accounts
    service.account().then(async (found) => {
      if (!alive) return
      setAccount(found)
      if (found.enabled && found.signedIn) {
        try {
          const who = await service.getMe()
          if (alive) setMe(who)
        } catch {
          // the page still works; it just cannot say who you are
        }
        if (alive && onChange) onChange()
      }
    })
    return () => {
      alive = false
    }
  }, [service]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!account || (!account.enabled && account.reason !== 'needs-https')) return null
  if (!account.enabled) {
    return (
      <section className="panel">
        <h3 className="section-title">Account</h3>
        <p className="small">Signing in works on the https address of this page, not on this one.</p>
      </section>
    )
  }
  return (
    <section className="panel account">
      <div className="you-head">
        <h3 className="section-title">Account</h3>
        {account.signedIn && <span className="chip chip-herd">Signed in</span>}
      </div>
      {account.signedIn ? (
        <>
          <p className="goat-id">
            <strong>{goatName(me?.fingerprint)}</strong>
            {me?.fingerprint && <span className="small"> · herder #{me.fingerprint.slice(0, 4)}</span>}
          </p>
          <p className="small">
            That is all Gary knows about you: no name, no e-mail address. Your check-ins are kept under this goat
            and shown to nobody else.
          </p>
          <p>
            {me?.paired
              ? 'A Gary is paired with you: his sniffs arrive signed as yours.'
              : 'No Gary is paired with you yet. On the Pi, run python3 pair.py and enter the code it shows.'}
          </p>
          <button type="button" className="button" onClick={() => account.signOut()}>
            Sign out
          </button>
        </>
      ) : (
        <>
          <p>Sign in to keep your check-ins as yours, and to pair a Gary with you.</p>
          <button type="button" className="button primary" onClick={() => account.signIn()}>
            Sign in
          </button>
        </>
      )}
    </section>
  )
}

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

const MAKERS = [
  ['Anay Baid', 'anaybaid7'],
  ['Ashmita Haldar', 'ashmitahaldar'],
  ['Mohammed Owda', 'mowda2'],
  ['Tristan Beley', 'tristanbeley92'],
]

export default function Settings({ service, stamp, status, onReset, onMeet }) {
  const [ask, setAsk] = useState(readAsk)
  const [sound, setSound] = useState(readSound)
  const [nearby, setNearby] = useState(readNearby)
  const [signedInAt, setSignedInAt] = useState(0) // bumps the wellness view once a sign-in is known

  function toggle() {
    writeAsk(!ask)
    setAsk(!ask)
  }

  function toggleNearby() {
    writeNearby(!nearby)
    if (nearby) leaveNearby(service) // off: your dot leaves everyone's map now, not in a minute
    setNearby(!nearby)
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
        <h3 className="section-title">Explorers nearby</h3>
        <label className="switch">
          <input type="checkbox" checked={nearby} onChange={toggleNearby} />
          <span>Show me to explorers nearby, and show them to me</span>
        </label>
        <p className="small">
          Off unless you turn it on. While it is on, the map shows a moving dot for each explorer near you or on your
          quest, and they see one for you. Where you are is sent rounded to about 100 m, with no name, and is never
          kept (a showcase server may show exact positions; the map says so when it does): your dot is gone within a minute of closing the page, and at once when you switch this off.
        </p>
      </section>

      <Account service={service} onChange={() => setSignedInAt((n) => n + 1)} />

      <section className="panel">
        <You service={service} stamp={`${stamp}-${signedInAt}`} />
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

      {onMeet && (
        <section className="panel">
          <h3 className="section-title">Meet Gary</h3>
          <p className="small">Gary says who he is and shows you his three moves. Half a minute.</p>
          <button type="button" className="button" onClick={onMeet}>
            Meet Gary again
          </button>
        </section>
      )}

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

      <section className="panel">
        <details className="credits">
          <summary>About G.A.R.Y</summary>
          <p>Built at Hack Western 13 (November 2026) by:</p>
          <ul>
            {MAKERS.map(([name, login]) => (
              <li key={login}>
                <a href={`https://github.com/${login}`} target="_blank" rel="noreferrer">{name}</a>
              </li>
            ))}
          </ul>
          <p className="small">
            <a href="https://github.com/anaybaid7/hackwestern13-gary" target="_blank" rel="noreferrer">The code on GitHub</a>
          </p>
        </details>
      </section>
    </div>
  )
}

// The front door: Gary, his name, and one button. "Log in" when this server has
// Auth0 set up (an account is still optional: "Just look around" goes in
// without one), "Start" when it does not. Signed in already: straight in.
// Shown once a visit (a browser tab), before Gary's hello.
import { useEffect, useState } from 'react'
import { garySrc } from '../sprites.js'

const STARTED_KEY = 'gary.started'

export function readStarted() {
  try {
    return window.sessionStorage.getItem(STARTED_KEY) === 'yes'
  } catch {
    return false
  }
}

function writeStarted() {
  try {
    window.sessionStorage.setItem(STARTED_KEY, 'yes')
  } catch {
    // this page load only
  }
}

export default function Landing({ service, onStart }) {
  const [account, setAccount] = useState(service.account ? null : { enabled: false })

  useEffect(() => {
    if (!service.account) return undefined
    let alive = true
    service.account().then(
      (found) => alive && setAccount(found),
      () => alive && setAccount({ enabled: false }),
    )
    return () => {
      alive = false
    }
  }, [service])

  const start = () => {
    writeStarted()
    onStart()
  }

  useEffect(() => {
    if (account?.signedIn) start()
  }, [account])

  const login = account?.enabled && !account.signedIn
  return (
    <div className="landing">
      <p className="landing-kicker">Pocket</p>
      <h1 className="landing-title">G.A.R.Y.</h1>
      <p className="landing-tagline">Go Anywhere, Rediscover Yourself</p>
      <img className="landing-gary" src={garySrc('kid', false)} alt="Gary the goat" width="176" height="176" />
      <p className="landing-pitch">A goat who only grows when you go outside.</p>
      <div className="landing-actions">
        {!account ? (
          <button type="button" className="button primary landing-go" disabled>…</button>
        ) : login ? (
          <>
            <button type="button" className="button primary landing-go" onClick={() => account.signIn()}>Log in</button>
            <button type="button" className="landing-skip" onClick={start}>Just look around</button>
          </>
        ) : (
          <button type="button" className="button primary landing-go" onClick={start}>Start</button>
        )}
      </div>
    </div>
  )
}

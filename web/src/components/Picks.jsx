// Picks for you: a TinyFish agent reads live London pages with what Gary
// knows about you, and chooses places. Every pick is a place the agent read
// on a page; the page here only shows them. Where you are stays here: only
// the name of the nearest known place is sent.
import { useCallback, useEffect, useRef, useState } from 'react'
import { clock } from '../format.js'
import { nearestPlace } from '../places.js'

const POLL_MS = 3000
const SHOWN = 3

/** Your position once, or null: no prompt is ever repeated, and nothing is kept. */
function whereNow(geo = navigator.geolocation, ms = 6000) {
  return new Promise((done) => {
    if (!geo) return done(null)
    const timer = setTimeout(() => done(null), ms + 500)
    geo.getCurrentPosition(
      (pos) => {
        clearTimeout(timer)
        done([pos.coords.latitude, pos.coords.longitude])
      },
      () => {
        clearTimeout(timer)
        done(null)
      },
      { maximumAge: 60000, timeout: ms },
    )
  })
}

function host(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}

export default function Picks({ service, tiles = [], onTaken, pollMs = POLL_MS, locate = whereNow }) {
  const [view, setView] = useState(null)
  const [problem, setProblem] = useState(null)
  const [busy, setBusy] = useState(false)
  const alive = useRef(true)

  const offered = typeof service.getPicks === 'function'
  const load = useCallback(async () => {
    if (!offered) return null
    try {
      const next = await service.getPicks()
      if (alive.current) setView(next)
      return next
    } catch (error) {
      // an older backend without /api/picks, or picks switched off: show nothing
      if (alive.current) setView({ ready: false })
      return null
    }
  }, [service, offered])

  useEffect(() => {
    alive.current = true
    load()
    return () => {
      alive.current = false
    }
  }, [load])

  const running = view?.job?.status === 'running'
  useEffect(() => {
    if (!running) return undefined
    const timer = setInterval(load, pollMs)
    return () => clearInterval(timer)
  }, [running, load, pollMs])

  async function ask() {
    setBusy(true)
    setProblem(null)
    try {
      const near = nearestPlace(await locate(), tiles)
      await service.askPicks(near)
      await load()
    } catch (error) {
      setProblem(error.status === 503 ? 'TinyFish is not set up on this server.' : 'Could not start the scout. Try again.')
    } finally {
      setBusy(false)
    }
  }

  async function take(id) {
    setBusy(true)
    try {
      const out = await service.takePick(id)
      onTaken?.(out.state)
    } catch {
      setProblem('Could not take that pick. Try again.')
    } finally {
      setBusy(false)
    }
  }

  // Nothing to offer: no picks on this service, or no TinyFish key on the server.
  if (!offered || (!view && !problem) || (view && !view.ready)) return null
  const picks = view?.picks ?? []
  return (
    <section className="picks" aria-labelledby="picks-title">
      <div className="picks-head">
        <h3 id="picks-title">Picked for you</h3>
        {view?.ready && (
          <button type="button" className="button" onClick={ask} disabled={busy || running}>
            {running ? 'Scouting…' : picks.length ? 'New picks' : 'Find places for me'}
          </button>
        )}
      </div>
      {running && (
        <p className="small" role="status">
          The scout is reading live London pages for you. This takes a minute or two.
        </p>
      )}
      {problem && <p className="small" role="alert">{problem}</p>}
      {view?.error && !running && (
        <p className="small" role="status">
          The last request did not work: {view.error}
          {picks.length > 0 && ' Showing the last good picks.'}
        </p>
      )}
      {picks.length > 0 && (
        <>
          <ol className="pick-list">
            {picks.slice(0, SHOWN).map((pick) => (
              <li key={pick.quest.id} className="pick">
                <p className="pick-title">{pick.quest.title}</p>
                {pick.why && (
                  <p className="pick-why">
                    “{pick.why}”{' '}
                    {host(pick.quest.source_url) && (
                      <a className="link" href={pick.quest.source_url} target="_blank" rel="noreferrer">
                        {host(pick.quest.source_url)}
                      </a>
                    )}
                  </p>
                )}
                <p className="chips">
                  {pick.reasons.map((reason) => (
                    <span key={reason} className="chip chip-plain">{reason}</span>
                  ))}
                </p>
                <button type="button" className="button primary" onClick={() => take(pick.quest.id)} disabled={busy}>
                  Take it
                </button>
              </li>
            ))}
          </ol>
          <p className="small">
            Found by a TinyFish agent on live pages{view.picked_at ? `, ${clock(view.picked_at)}` : ''}.
          </p>
        </>
      )}
    </section>
  )
}

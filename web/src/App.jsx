// Gary's world. The page draws what the service says and asks again every two
// seconds. It decides nothing: every number comes from the backend (or, in
// mock mode, from the demo story the backend produced).
import { useCallback, useEffect, useRef, useState } from 'react'
import napping from './art/gary-kid-nap.svg'
import { ordinal } from './format.js'
import StoryBar from './components/StoryBar.jsx'
import Tabs, { TABS } from './components/Tabs.jsx'
import Guide from './screens/Guide.jsx'
import Herd from './screens/Herd.jsx'
import Home from './screens/Home.jsx'
import MapScreen from './screens/MapScreen.jsx'
import You from './screens/You.jsx'
import { createService } from './services/index.js'
import { STAGE_NAMES } from './words.js'

const POLL_MS = 2000
const FLASH_MS = 6000
const NO_FLASH = { find: null, stageUp: false, cleared: [], rankUp: null, messages: [] }
const STATUS = {
  live: 'Live',
  mock: 'Demo story',
  stale: 'Offline. Showing the last state',
}

export default function App({ service: given }) {
  const [service, setService] = useState(given ?? null)
  useEffect(() => {
    if (given) return undefined
    let alive = true
    createService().then((made) => alive && setService(made))
    return () => {
      alive = false
    }
  }, [given])
  if (!service) return <Splash>Waking Gary.</Splash>
  return <Shell service={service} />
}

/** What is new in `next` compared with `prev`: the things worth a small celebration. */
export function whatChanged(prev, next) {
  if (!prev) return null
  const out = { find: null, stageUp: false, cleared: [], rankUp: null, messages: [] }
  const top = next.journal[0]
  if (top && top.id !== prev.journal[0]?.id && next.gary.xp > prev.gary.xp) {
    out.find = top
    out.messages.push(`New find: ${top.label}. +${top.xp} XP.`)
  }
  if (next.gary.stage_index > prev.gary.stage_index) {
    const name = STAGE_NAMES[next.gary.stage] ?? next.gary.stage
    out.stageUp = true
    out.messages.push(`Gary grew. He is ${/^[aeiou]/i.test(name) ? 'an' : 'a'} ${name} now.`)
  }
  const before = new Set(prev.map.filter((tile) => tile.cleared).map((tile) => tile.place))
  out.cleared = next.map.filter((tile) => tile.cleared && !before.has(tile.place)).map((tile) => tile.place)
  for (const place of out.cleared) out.messages.push(`The fog lifted over ${place}.`)
  const was = prev.herd.cup
  const now = next.herd.cup
  if (was.week === now.week && now.rank < was.rank) {
    out.rankUp = { from: was.rank, to: now.rank }
    out.messages.push(`Your herd moved up to ${ordinal(now.rank)} in the Herd Cup.`)
  }
  return out.messages.length > 0 ? out : null
}

function readTab() {
  const id = window.location.hash.replace('#', '')
  return TABS.some((tab) => tab.id === id) ? id : 'gary'
}

export function Shell({ service, pollMs = POLL_MS }) {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState(readTab)
  const [side, setSide] = useState(() => (readTab() === 'gary' ? 'guide' : readTab()))
  const [flash, setFlash] = useState(NO_FLASH)
  const [busy, setBusy] = useState(false)
  const last = useRef(null)
  const flashTimer = useRef(null)

  const take = useCallback((next) => {
    const changes = whatChanged(last.current, next)
    last.current = next
    setState(next)
    setError(null)
    if (changes) {
      setFlash(changes)
      clearTimeout(flashTimer.current)
      flashTimer.current = setTimeout(() => setFlash(NO_FLASH), FLASH_MS)
    }
  }, [])

  const refresh = useCallback(
    () => service.getState().then(take, (err) => setError(String(err.message || err))),
    [service, take],
  )

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, pollMs)
    return () => {
      clearInterval(timer)
      clearTimeout(flashTimer.current)
    }
  }, [refresh, pollMs])

  function pick(id) {
    setTab(id)
    if (id !== 'gary') setSide(id)
    window.history.replaceState(null, '', `#${id}`)
  }

  async function choose(time) {
    setBusy(true)
    try {
      const out = await service.chooseQuest(time)
      if (out?.state) take(out.state)
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  if (!state) {
    return (
      <Splash>
        {error ? (
          <>
            Cannot reach Gary's backend at {service.api || 'this address'} ({error}). Is it running?{' '}
            <a href="?mock">Open the demo story instead.</a>
          </>
        ) : (
          'Waking Gary.'
        )}
      </Splash>
    )
  }

  const now = service.now()
  const status = service.mode === 'mock' ? 'mock' : error ? 'stale' : 'live'
  const dots = { map: flash.cleared.length > 0, guide: Boolean(flash.find), herd: Boolean(flash.rankUp) }
  // The wellness view is fetched again whenever something that feeds it changes.
  const stamp = `${state.journal[0]?.id ?? ''}:${service.story?.index ?? ''}`

  return (
    <div className="app" data-tab={tab} data-mode={service.mode}>
      <header className="topbar">
        <h1>Gary the Goat</h1>
        <span className={`status status-${status}`}>{STATUS[status]}</span>
      </header>

      {flash.messages.length > 0 && (
        <div className="toast" role="status">
          {flash.messages.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}

      <main className="panes">
        <section className="pane pane-gary" aria-label="Gary">
          <Home state={state} flash={flash} now={now} onChoose={choose} busy={busy} onSeeAll={() => pick('guide')} />
        </section>
        <section className="pane pane-side" aria-label={TABS.find((t) => t.id === side)?.name}>
          {side === 'map' && <MapScreen map={state.map} flash={flash} questPlace={state.quest?.place} />}
          {side === 'guide' && <Guide guide={state.guide} journal={state.journal} now={now} flash={flash} />}
          {side === 'herd' && <Herd herd={state.herd} journal={state.journal} flash={flash} />}
          {side === 'you' && <You service={service} stamp={stamp} />}
        </section>
      </main>

      <footer className="dock">
        {service.story && (
          <StoryBar
            story={service.story}
            onMove={(move) => {
              move()
              refresh()
            }}
          />
        )}
        <Tabs tab={tab} side={side} onPick={pick} dots={dots} />
      </footer>
    </div>
  )
}

function Splash({ children }) {
  return (
    <div className="splash">
      <img src={napping} alt="" width="160" height="160" />
      <p>{children}</p>
    </div>
  )
}

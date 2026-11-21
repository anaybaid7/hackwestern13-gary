// Gary's world. The page draws what the service says and asks again every two
// seconds. It decides nothing: every number comes from the backend (or, in
// mock mode, from the demo story the backend produced).
import { useCallback, useEffect, useRef, useState } from 'react'
import CheckIn, { readAsk } from './components/CheckIn.jsx'
import QuestComplete from './components/QuestComplete.jsx'
import Nav, { SCREENS } from './components/Nav.jsx'
import StoryBar from './components/StoryBar.jsx'
import { ordinal } from './format.js'
import Guide from './screens/Guide.jsx'
import Herd from './screens/Herd.jsx'
import Home from './screens/Home.jsx'
import MapScreen from './screens/MapScreen.jsx'
import Settings from './screens/Settings.jsx'
import { pickClip, playClip, playVoice, readSound, unlockSound, voiceFor } from './sound.js'
import { away, isNear, realSpot } from './places.js'
import { createService } from './services/index.js'
import { garySrc } from './sprites.js'
import { useWhereAmI } from './whereAmI.js'
import { STAGE_NAMES } from './words.js'

const POLL_MS = 2000
const FLASH_MS = 6000
const NO_FLASH = { find: null, quest: null, stageUp: false, cleared: [], rankUp: null, messages: [] }
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
  const out = { find: null, quest: null, stageUp: false, cleared: [], rankUp: null, miss: false, messages: [] }
  if (next.last_miss && next.last_miss.id !== prev.last_miss?.id) {
    out.miss = true
    out.messages.push('Gary could not name that one. Try a little closer.')
  }
  const top = next.journal[0]
  if (top && top.id !== prev.journal[0]?.id && next.gary.xp > prev.gary.xp) {
    out.find = top
    out.messages.push(`New find: ${top.label}. +${top.xp} XP.`)
    if (top.quest_id) {
      // the sniff finished a quest: find its title in what the page was showing
      const known = [prev.quest, prev.quest_options?.short, prev.quest_options?.long, prev.herd?.quest]
      out.quest = known.find((q) => q?.id === top.quest_id) ?? { id: top.quest_id, title: null }
    }
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

// Old addresses keep working.
const OLD_TABS = { gary: 'home', guide: 'journal', herd: 'cup', you: 'settings' }

function readTab() {
  const raw = window.location.hash.replace('#', '')
  const id = OLD_TABS[raw] ?? raw
  return SCREENS.some((screen) => screen.id === id) ? id : 'home'
}

export function Shell({ service, pollMs = POLL_MS, askCheckIn = readAsk() }) {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState(readTab)
  const [flash, setFlash] = useState(NO_FLASH)
  const [busy, setBusy] = useState(false)
  const [asking, setAsking] = useState(askCheckIn) // once per visit
  const [mapFocus, setMapFocus] = useState(null) // a place "See on map" asked for
  const [reward, setReward] = useState(null) // a finished quest, until it is dismissed
  const [afterCheckIn, setAfterCheckIn] = useState(false) // the check-in that follows it
  const last = useRef(null)
  const flashTimer = useRef(null)
  const visited = useRef(new Set()) // quests this page has said you were at, this visit

  // Are you at the quest's place? Worked out here, in the browser, only while
  // the quest has a real position. The backend hears "visited quest X" only.
  const spot = realSpot(state?.quest)
  const me = useWhereAmI(Boolean(spot) && service.mode === 'live')
  const near = isNear(me.at, me.accuracy, spot)
  const questId = state?.quest?.id
  useEffect(() => {
    if (!near || !questId || visited.current.has(questId) || !service.postVisit) return
    visited.current.add(questId)
    service.postVisit(questId).catch(() => visited.current.delete(questId)) // try again on the next fix
  }, [near, questId, service])

  const take = useCallback((next) => {
    const prev = last.current
    const changes = whatChanged(prev, next)
    last.current = next
    setState(next)
    setError(null)
    if (changes) {
      if (readSound()) {
        const voice = voiceFor(changes, prev, next) // Gary's own voice, else a chime
        const clip = voice ? null : pickClip(changes)
        if (voice) playVoice(voice)
        else if (clip) playClip(clip)
      }
      if (changes.quest) setReward({ ...changes, gary: next.gary })
      setFlash(changes)
      clearTimeout(flashTimer.current)
      flashTimer.current = setTimeout(() => setFlash(NO_FLASH), FLASH_MS)
    }
  }, [])

  const refresh = useCallback(
    () => service.getState().then(take, (err) => setError(String(err.message || err))),
    [service, take],
  )

  // the first tap or key press lets the browser play Gary's voice (Safari needs it)
  useEffect(() => {
    const unlock = () => unlockSound()
    window.addEventListener('pointerdown', unlock, { once: true })
    window.addEventListener('keydown', unlock, { once: true })
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, pollMs)
    return () => {
      clearInterval(timer)
      clearTimeout(flashTimer.current)
    }
  }, [refresh, pollMs])

  const closeCheckIn = useCallback(() => {
    setAsking(false)
    setAfterCheckIn(false)
  }, [])

  function closeReward() {
    setReward(null)
    if (askCheckIn && readAsk()) setAfterCheckIn(true) // "how do you feel now?", unless turned off
  }

  function pick(id, focus = null) {
    setMapFocus(focus)
    setTab(id)
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
  const dots = { map: flash.cleared.length > 0, journal: Boolean(flash.find), cup: Boolean(flash.rankUp) }
  // The wellness view is fetched again whenever something that feeds it changes.
  const stamp = `${state.journal[0]?.id ?? ''}:${service.story?.index ?? ''}`

  return (
    <Handheld onPick={pick}>
      <div className="app" data-tab={tab} data-mode={service.mode}>
        <header className="topbar">
          <h1>Gary</h1>
          <span className={`status status-${status}`}>{STATUS[status]}</span>
        </header>

        {flash.messages.length > 0 && !reward && (
          <div className="toast" role="status">
            {flash.messages.map((message) => (
              <p key={message}>{message}</p>
            ))}
          </div>
        )}

        <main className="view">
          {tab === 'home' && <Home state={state} flash={flash} now={now} onChoose={choose} busy={busy} onShowMap={(place) => pick('map', place)} where={{ near, away: me.at && spot ? away(me.at, spot) : null }} />}
          {tab === 'map' && <MapScreen map={state.map} flash={flash} quest={state.quest} focusPlace={mapFocus} />}
          {tab === 'journal' && <Guide guide={state.guide} journal={state.journal} now={now} flash={flash} />}
          {tab === 'cup' && <Herd herd={state.herd} journal={state.journal} flash={flash} />}
          {tab === 'settings' && <Settings service={service} stamp={stamp} status={status} onReset={refresh} />}
        </main>

        {service.story && (
          <StoryBar
            story={service.story}
            onMove={(move) => {
              move()
              refresh()
            }}
          />
        )}
        <Nav tab={tab} onPick={pick} dots={dots} />
        {reward && (
          <QuestComplete
            reward={reward}
            onClose={closeReward}
            onShowMap={(place) => {
              closeReward()
              pick('map', place)
            }}
          />
        )}
        {!reward && afterCheckIn && <CheckIn service={service} phase="after" onClose={closeCheckIn} />}
        {!reward && !afterCheckIn && asking && tab === 'home' && <CheckIn service={service} onClose={closeCheckIn} />}
      </div>
    </Handheld>
  )
}

/** On a wide screen the page is a little handheld; on a phone, the phone is the handheld. */
function Handheld({ children, onPick }) {
  return (
    <div className="desk">
      <div className="handheld">
        <div className="handheld-screen">{children}</div>
        {/* Shortcuts that copy the bar at the bottom of the screen, so screen readers skip them. */}
        <div className="handheld-buttons" aria-hidden="true">
          <button type="button" tabIndex={-1} onClick={() => onPick('home')}>R</button>
          <button type="button" tabIndex={-1} onClick={() => onPick('map')}>O</button>
          <button type="button" tabIndex={-1} onClick={() => onPick('cup')}>G</button>
        </div>
        <p className="handheld-name" aria-hidden="true">Pocket Gary</p>
      </div>
    </div>
  )
}

function Splash({ children }) {
  return (
    <div className="splash">
      <img src={garySrc('kid', true)} alt="" width="160" height="160" />
      <p>{children}</p>
    </div>
  )
}

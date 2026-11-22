// Gary's world. The page draws what the service says and asks again every two
// seconds. It decides nothing: every number comes from the backend (or, in
// mock mode, from the demo story the backend produced).
import { useCallback, useEffect, useRef, useState } from 'react'
import CheckIn, { readAsk } from './components/CheckIn.jsx'
import GaryEars from './components/GaryEars.jsx'
import QuestComplete from './components/QuestComplete.jsx'
import Nav, { SCREENS } from './components/Nav.jsx'
import StoryBar from './components/StoryBar.jsx'
import Welcome, { readMet } from './components/Welcome.jsx'
import { ordinal } from './format.js'
import Guide from './screens/Guide.jsx'
import Herd from './screens/Herd.jsx'
import Home from './screens/Home.jsx'
import MapScreen from './screens/MapScreen.jsx'
import Settings from './screens/Settings.jsx'
import { effectsFor, playSfx, unlockSfx } from './sfx.js'
import { pickClip, playClip, playVoice, readSound, unlockSound, voiceFor } from './sound.js'
import { away, isNear, nearby, nextNearby, realSpot } from './places.js'
import { createService } from './services/index.js'
import { garySrc } from './sprites.js'
import { useWhereAmI } from './whereAmI.js'
import Picks from './components/Picks.jsx'
import { STAGE_NAMES } from './words.js'

const POLL_MS = 2000
const FLASH_MS = 6000
const SAY_AFTER_MS = 450 // Gary speaks once the chime has rung
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
  return <Shell service={service} welcome={!readMet()} />
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

export function Shell({ service, pollMs = POLL_MS, askCheckIn = readAsk(), welcome = false }) {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState(readTab)
  const [flash, setFlash] = useState(NO_FLASH)
  const [busy, setBusy] = useState(false)
  const [asking, setAsking] = useState(askCheckIn) // once per visit
  const [meeting, setMeeting] = useState(welcome) // a new person: Gary introduces himself first

  // Back from signing in (Auth0 sends you here with ?code=...&state=...): finish the sign-in now,
  // and show Settings, where it says who you are. Without this it waited until Settings was opened,
  // and the code in the address could run out first.
  useEffect(() => {
    const query = new URLSearchParams(window.location.search)
    if (!query.has('state') || !(query.has('code') || query.has('error')) || !service.account) return
    service.account().then(() => setTab('settings'), () => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the page opens
  }, [])
  const [mapFocus, setMapFocus] = useState(null) // a place "See on map" asked for
  const [reward, setReward] = useState(null) // a finished quest, until it is dismissed
  const [afterCheckIn, setAfterCheckIn] = useState(false) // the check-in that follows it
  const last = useRef(null)
  const flashTimer = useRef(null)
  const visited = useRef(new Set()) // quests this page has said you were at, this visit
  const titleTaps = useRef([]) // five quick taps on the title send the scout out (a hidden demo control)

  // Are you at the quest's place? Worked out here, in the browser, only while
  // the quest has a real position. The backend hears "visited quest X" only.
  const spot = realSpot(state?.quest)
  const me = useWhereAmI(service.mode === 'live')
  const near = isNear(me.at, spot)

  // Short means near you: the nearest open quest within 5.2 km, picked here
  // from your position, which stays in the browser. Only the quest id is sent.
  const [openQuests, setOpenQuests] = useState(null)
  const questsStamp = `${state?.quests_open}:${state?.quest?.id}`
  useEffect(() => {
    if (!service.getQuests) return // the map lists them too, so they are fetched with or without a position
    service.getQuests().then(setOpenQuests, () => setOpenQuests(null))
  }, [questsStamp, service])
  const close = me.at && openQuests ? nearby(me.at, openQuests) : null
  const activeShort = close && state?.quest_choice === 'short' ? close.find((q) => q.id === state.quest?.id) : null
  const shown = close && state ? { ...state, quest_options: { ...state.quest_options, short: activeShort ?? close[0] ?? null } } : state
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
        // the effect first (a chime, a fanfare, the fog), then Gary says it
        const effects = playSfx(effectsFor(changes))
        const voice = voiceFor(changes, prev, next)
        const clip = voice || effects ? null : pickClip(changes) // no voice and no effects: the old chime
        if (voice) setTimeout(() => playVoice(voice), effects ? SAY_AFTER_MS : 0)
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
    const unlock = () => {
      unlockSound()
      unlockSfx()
    }
    // and a soft tick on every button
    const tick = (event) => event.target.closest?.('button') && readSound() && playSfx(['tap'])
    window.addEventListener('pointerdown', unlock, { once: true })
    window.addEventListener('keydown', unlock, { once: true })
    window.addEventListener('click', tick)
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
      window.removeEventListener('click', tick)
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

  function say(message) {
    setFlash({ ...NO_FLASH, messages: [message] })
    clearTimeout(flashTimer.current)
    flashTimer.current = setTimeout(() => setFlash(NO_FLASH), FLASH_MS)
  }

  function tapTitle() {
    if (!service.runScout) return
    const now = Date.now()
    titleTaps.current = [...titleTaps.current.filter((t) => now - t < 2000), now]
    if (titleTaps.current.length < 5) return
    titleTaps.current = []
    service.runScout().then(
      (out) => say(out.sent ? 'The scout is out looking for quests. New ones show up in a few minutes.' : 'The scout is already out looking.'),
      (err) => say(`The scout could not go out (${err.message || err}).`),
    )
  }

  async function choose(time, questId) {
    // "another short one": the next nearest, when the page knows where you are
    const pick = questId ?? (time === 'short' && close ? nextNearby(close, state.quest?.id)?.id : undefined)
    setBusy(true)
    try {
      const out = await service.chooseQuest(time, pick)
      if (out?.state) take(out.state)
    } catch (err) {
      setError(String(err.message || err))
    } finally {
      setBusy(false)
    }
  }

  // Gary's hello needs nothing from the backend, so it does not wait for it.
  if (meeting) {
    return (
      <Handheld onPick={pick}>
        <Welcome
          onDone={() => {
            setMeeting(false)
            setAsking(false) // he has just asked how you feel: not twice in one visit
          }}
        />
      </Handheld>
    )
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
          <h1 title="Go Anywhere, Rediscover Yourself" onClick={tapTitle}>G.A.R.Y</h1>
          <GaryEars service={service} />
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
          {tab === 'home' && <Home state={shown} flash={flash} now={now} onChoose={choose} busy={busy} onShowMap={(place) => pick('map', place)} where={{ near, away: me.at && spot ? away(me.at, spot) : null }}>{service.mode === 'live' && <Picks service={service} tiles={state.map} onTaken={take} />}</Home>}
          {tab === 'map' && <MapScreen service={service} map={state.map} flash={flash} quest={state.quest} quests={openQuests ?? []} busy={busy} onPickQuest={(q) => choose(q.time, q.id)} focusPlace={mapFocus} />}
          {tab === 'journal' && <Guide guide={state.guide} journal={state.journal} now={now} flash={flash} />}
          {tab === 'cup' && <Herd herd={state.herd} journal={state.journal} flash={flash} />}
          {tab === 'settings' && <Settings service={service} stamp={stamp} status={status} onReset={refresh} onMeet={() => setMeeting(true)} />}
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

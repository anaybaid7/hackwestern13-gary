// The bare-bones page (Phase 1). It draws whatever GET /api/state returns and
// asks again every two seconds. Every number on it comes from the backend; the
// page decides nothing. Phase 4 turns this into Gary's world.
import { useEffect, useState } from 'react'
import { API, MOCK, getState } from './api.js'
import Gary from './Gary.jsx'

const STAGE_NAMES = { kid: 'Kid', scrambler: 'Scrambler', ibex: 'Ibex', 'summit-elder': 'Summit Elder' }
const POLL_MS = 2000
const MAP_TILES = 25

export default function App() {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    const tick = () =>
      getState()
        .then((next) => {
          if (!alive) return
          setState(next)
          setError(null)
        })
        .catch((err) => alive && setError(String(err.message || err)))
    tick()
    const timer = setInterval(tick, POLL_MS)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  if (!state) {
    return (
      <main className="page">
        <p className="note">
          {error ? `Cannot reach the backend at ${API || 'this address'} (${error}). Is it running?` : 'Waking Gary…'}
        </p>
      </main>
    )
  }
  return <View state={state} status={MOCK ? 'mock' : error ? 'stale' : 'live'} />
}

const STATUS_TEXT = {
  mock: 'Mock data. No backend connected',
  live: 'Live',
  stale: 'Backend unreachable. Showing the last state',
}

export function View({ state, status }) {
  const { gary, quest, journal, guide, map, herd } = state
  return (
    <main className="page">
      <header className="top">
        <h1>Gary the Goat</h1>
        <span className={`pill pill-${status}`}>{STATUS_TEXT[status]}</span>
      </header>

      <section className="card hero">
        <Gary stageIndex={gary.stage_index} napping={gary.napping} />
        <div className="hero-text">
          <h2>{STAGE_NAMES[gary.stage] ?? gary.stage}</h2>
          <p className="line">{garyLine(gary)}</p>
          <XpBar gary={gary} />
        </div>
      </section>

      <section className="card">
        <h3>Today's quest</h3>
        <Quest quest={quest} open={state.quests_open} />
      </section>

      <section className="card">
        <h3>Field guide</h3>
        <p className="big">
          {guide.found.length} of {guide.total} found
        </p>
        <div className="chips">
          {guide.found.map((name) => (
            <span className="chip" key={name}>
              {name}
            </span>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>Journal</h3>
        {journal.length === 0 ? (
          <p className="note">Nothing yet. Point Gary at something and press the button.</p>
        ) : (
          <ul className="journal">
            {journal.map((entry) => (
              <li key={entry.id}>
                <span className="what">{entry.label}</span>
                {entry.quest_id && <span className="tag tag-quest">quest</span>}
                {entry.new && <span className="tag tag-new">new</span>}
                {entry.friend && <span className="tag tag-herd">herd</span>}
                <span className="xp">+{entry.xp} XP</span>
                <span className="small">
                  {clock(entry.ts)}
                  {entry.latency_ms != null && ` · named on the device in ${Math.round(entry.latency_ms)} ms`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h3>Map</h3>
        <MapGrid tiles={map} />
      </section>

      <section className="card">
        <h3>Herd Cup</h3>
        <p className="small">
          Week {herd.cup.week}. Herds compete; people are never ranked.
          {herd.cup.demo && ' Rival herds are demo data.'}
        </p>
        <ol className="cup">
          {herd.cup.table.map((row) => (
            <li key={row.herd} className={row.you ? 'you' : ''}>
              <span>{row.herd}</span>
              <span>{row.score}</span>
            </li>
          ))}
        </ol>
        <p className="small">
          Finds with a friend in frame: {herd.shared}
          {herd.badges.length > 0 && ` · badges: ${herd.badges.join(', ')}`}
        </p>
      </section>
    </main>
  )
}

function garyLine(gary) {
  if (gary.napping) return 'Zzz. Gary is napping. No guilt, he was tired anyway.'
  if (gary.welcome_back) return "Oh, you're back. Good. Gary saved you a rock."
  return 'Gary is awake and nosy.'
}

function XpBar({ gary }) {
  const top = gary.next_stage_xp
  const span = top == null ? 1 : top - gary.stage_xp
  const done = top == null ? 1 : Math.min(1, (gary.xp - gary.stage_xp) / span)
  return (
    <div>
      <div className="bar" role="progressbar" aria-valuenow={gary.xp} aria-valuemin={gary.stage_xp} aria-valuemax={top ?? gary.xp}>
        <div className="fill" style={{ width: `${Math.round(done * 100)}%` }} />
      </div>
      <p className="small">
        {gary.xp} XP{top == null ? ' · top of the mountain' : ` · ${top - gary.xp} to the next stage`}
      </p>
    </div>
  )
}

function Quest({ quest, open }) {
  if (!quest) return <p className="note">Every quest is done. The scout brings more tomorrow.</p>
  return (
    <div>
      <p className="big">{quest.title}</p>
      <p className="small">
        {quest.place} · {quest.time}
        {quest.minutes ? `, about ${quest.minutes} min` : ''} · sniff a {quest.target}
        {quest.herd ? ' · needs a friend in frame' : ''} · {quest.xp} XP
      </p>
      <p className="small">
        {quest.source_url ? (
          <>
            Found by the scout on <a href={quest.source_url}>{host(quest.source_url)}</a>
          </>
        ) : (
          `Source: ${quest.source}`
        )}
        {open > 1 && ` · ${open - 1} more open`}
      </p>
    </div>
  )
}

function MapGrid({ tiles }) {
  const cells = [...tiles]
  while (cells.length < MAP_TILES) cells.push(null)
  return (
    <div className="map">
      {cells.slice(0, MAP_TILES).map((tile, i) => (
        <div key={i} className={`tile ${tile ? (tile.cleared ? 'cleared' : 'fog named') : 'fog'}`}>
          {tile ? tile.place : ''}
        </div>
      ))}
    </div>
  )
}

function clock(ts) {
  const when = new Date(ts)
  return Number.isNaN(when.getTime()) ? '' : when.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function host(url) {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

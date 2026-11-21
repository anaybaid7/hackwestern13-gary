// The home screen: Gary on his little LCD, what he says, his XP, and
// today's quest. Everything else has its own screen.
import Climb from '../components/Climb.jsx'
import Gary from '../components/Gary.jsx'
import QuestCard from '../components/QuestCard.jsx'
import { garyLine } from '../voice.js'
import { STAGE_NAMES } from '../words.js'

// Where the device serves what Gary sees (device/qnx/live.sh), if anywhere.
const LIVE_URL = import.meta.env.VITE_LIVE_URL

export default function Home({ state, flash, onChoose, onShowMap, busy, liveUrl = LIVE_URL }) {
  const { gary, journal } = state
  const celebrating = Boolean(flash.find)
  return (
    <div className="home">
      <section className={`lcd${gary.napping ? ' napping' : ''}`} aria-label="Gary">
        <div className="lcd-top">
          <h2>{STAGE_NAMES[gary.stage] ?? gary.stage}</h2>
          <span>Stage {gary.stage_index + 1}</span>
        </div>
        <div className="lcd-gary">
          <Gary stage={gary.stage} napping={gary.napping} grew={flash.stageUp} />
          {celebrating && (
            <div className="burst" aria-hidden="true">
              {Array.from({ length: 12 }, (_, i) => (
                <i key={i} style={{ '--i': i }} />
              ))}
            </div>
          )}
        </div>
        <p className={`speech${celebrating ? ' fresh' : ''}`} aria-live="polite">
          {garyLine(gary, journal[0])}
        </p>
        <Climb gary={gary} />
        {liveUrl && (
          <a className="link live-link" href={liveUrl} target="_blank" rel="noreferrer">
            What Gary sees ↗
          </a>
        )}
      </section>

      <QuestCard
        quest={state.quest}
        choice={state.quest_choice}
        options={state.quest_options}
        onChoose={onChoose}
        onShowMap={onShowMap}
        busy={busy}
      />
    </div>
  )
}

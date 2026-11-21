// The first screen: Gary, what he says, today's recap, the quest, the latest finds.
import Climb from '../components/Climb.jsx'
import FindRow from '../components/FindRow.jsx'
import Gary from '../components/Gary.jsx'
import QuestCard from '../components/QuestCard.jsx'
import { garyLine, recap } from '../voice.js'
import { STAGE_NAMES } from '../words.js'

export default function Home({ state, flash, now, onChoose, busy, onSeeAll }) {
  const { gary, journal } = state
  const celebrating = Boolean(flash.find)
  return (
    <div className="home">
      <section className={`hero${gary.napping ? ' napping' : ''}`} aria-label="Gary">
        <div className="hero-top">
          <Gary stage={gary.stage} napping={gary.napping} grew={flash.stageUp} />
          <div className="hero-words">
            <h2>{STAGE_NAMES[gary.stage] ?? gary.stage}</h2>
            <p className={`speech${celebrating ? ' fresh' : ''}`} aria-live="polite">
              {garyLine(gary, journal[0])}
            </p>
          </div>
        </div>
        <Climb gary={gary} />
        {celebrating && (
          <div className="burst" aria-hidden="true">
            {Array.from({ length: 9 }, (_, i) => (
              <i key={i} style={{ '--i': i }} />
            ))}
          </div>
        )}
      </section>

      <p className="recap">{recap(journal, now)}</p>

      <QuestCard
        quest={state.quest}
        choice={state.quest_choice}
        options={state.quest_options}
        open={state.quests_open}
        onChoose={onChoose}
        busy={busy}
      />

      <section className="latest" aria-labelledby="latest-title">
        <h3 id="latest-title">Latest finds</h3>
        {journal.length === 0 ? (
          <p className="empty">Nothing yet. Point Gary at something and press his button.</p>
        ) : (
          <ul className="finds">
            {journal.slice(0, 3).map((entry) => (
              <FindRow key={entry.id} entry={entry} fresh={flash.find?.id === entry.id} />
            ))}
          </ul>
        )}
        {journal.length > 3 && (
          <button type="button" className="link" onClick={onSeeAll}>
            See all {journal.length} finds
          </button>
        )}
      </section>
    </div>
  )
}

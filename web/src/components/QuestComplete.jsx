// The reward screen when a sniff finishes a quest: what was found, the XP,
// the fog that lifted, Gary growing, the herd moving up. Every number comes
// from the state; this only celebrates it.
import { useEffect } from 'react'
import { ordinal } from '../format.js'
import { STAGE_NAMES } from '../words.js'
import Gary from './Gary.jsx'
import ThingIcon from './ThingIcon.jsx'

export default function QuestComplete({ reward, onClose, onShowMap }) {
  const { find, quest, cleared, stageUp, rankUp, gary } = reward
  const place = cleared[0] ?? find.place

  useEffect(() => {
    const onKey = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-backdrop">
      <div className="modal reward" role="dialog" aria-modal="true" aria-labelledby="reward-title">
        <div className="reward-burst" aria-hidden="true">
          {Array.from({ length: 12 }, (_, i) => (
            <i key={i} style={{ '--i': i }} />
          ))}
        </div>
        <h2 id="reward-title">Quest complete!</h2>
        {quest.title && <p className="reward-quest">{quest.title}</p>}

        <div className="reward-gary">
          <Gary stage={gary.stage} grew={stageUp} size={120} />
        </div>

        <div className="reward-find">
          <ThingIcon name={find.label} />
          <span className="reward-label">{find.label}</span>
          {find.friend && <span className="mark mark-herd">Herd</span>}
        </div>
        <p className="reward-xp">+{find.xp} XP</p>

        <ul className="reward-list">
          {cleared.map((name) => (
            <li key={name}>☁ Fog lifted over {name}</li>
          ))}
          {stageUp && <li>★ Gary grew: {STAGE_NAMES[gary.stage] ?? gary.stage}</li>}
          {rankUp && (
            <li>
              ▲ Herd up to {ordinal(rankUp.to)} in the cup
            </li>
          )}
        </ul>

        <div className="detail-buttons">
          <button type="button" className="button primary" onClick={onClose} autoFocus>
            Nice!
          </button>
          {place && (
            <button type="button" className="button" onClick={() => onShowMap(place)}>
              See on map
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

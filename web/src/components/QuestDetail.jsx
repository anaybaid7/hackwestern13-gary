// Everything about one quest, opened from the quest card or from Short/Long.
// Starting a quest, or skipping to another of the same length, asks the
// backend (POST /api/quest/choose); this sheet decides nothing itself.
import { useEffect } from 'react'
import { host, webAddress } from '../format.js'
import ThingIcon from './ThingIcon.jsx'

const MINUTES = { short: 15, long: 40 }

export default function QuestDetail({ quest, active, busy, onStart, onAnother, onShowMap, onClose }) {
  useEffect(() => {
    const onKey = (event) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const trail = quest.time === 'long'
  return (
    <div className="modal-backdrop" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal quest-detail" role="dialog" aria-modal="true" aria-labelledby="quest-detail-title">
        <p className="modal-top">
          {trail ? 'Long quest · trail walk' : 'Short quest'}
          {active && ' · active'}
        </p>
        <h2 id="quest-detail-title">{quest.title}</h2>

        <div className="detail-target">
          <ThingIcon name={quest.target} />
          <span>
            Sniff <strong>{quest.target}</strong>
          </span>
        </div>

        <ul className="detail-facts">
          <li>📍 {quest.place}</li>
          <li>⏱ About {quest.minutes ?? MINUTES[quest.time] ?? 15} min{trail ? ' on the trail' : ''}</li>
          <li>⭐ +{quest.xp} XP{quest.herd ? '' : ' · x2 with a friend in frame'}</li>
          {quest.herd && <li>👥 Needs a friend in frame</li>}
        </ul>

        {quest.note && <p className="detail-note">{quest.note}</p>}

        <p className="small">
          {quest.source === 'tinyfish' ? (
            webAddress(quest.source_url) ? (
              <>
                Found by the scout on <a href={quest.source_url}>{host(quest.source_url)}</a>
              </>
            ) : (
              'Found by the scout'
            )
          ) : quest.source === 'sample' ? (
            'Sample quest'
          ) : (
            'Starter quest'
          )}
        </p>

        <div className="detail-buttons">
          {active ? (
            <button type="button" className="button" onClick={onAnother} disabled={busy}>
              Another {quest.time}
            </button>
          ) : (
            <button type="button" className="button primary" onClick={onStart} disabled={busy} autoFocus>
              Start quest
            </button>
          )}
          <button type="button" className="button" onClick={onShowMap}>
            See on map
          </button>
          <button type="button" className="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

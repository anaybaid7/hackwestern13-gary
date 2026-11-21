// Today's quest card, with Short and Long under it (issue #28). Tap the card
// or either button for the quest's details; start it from there. A long quest
// is a trail walk: the scout takes those from trail and natural-area pages.
// Where a quest came from is one chip: "Scout" only for a live agent run,
// "Sample" or "Starter" otherwise.
import { useState } from 'react'
import { host, webAddress } from '../format.js'
import QuestDetail from './QuestDetail.jsx'

const MINUTES = { short: 15, long: 40 }

export default function QuestCard({ quest, choice, options = {}, onChoose, onShowMap, busy = false, where = null }) {
  const [open, setOpen] = useState(null) // the quest whose details are showing

  async function start(time) {
    await onChoose?.(time)
    setOpen(null)
  }

  return (
    <section className="quest" aria-labelledby="quest-title">
      {quest ? (
        <div className={`sign${quest.herd ? ' sign-herd' : ''}`}>
          <p className="sign-top">{choice ? `Your ${choice} quest` : "Today's quest"}</p>
          <h3 id="quest-title">
            <button type="button" className="sign-open" onClick={() => setOpen(quest)}>
              {quest.title}
            </button>
          </h3>
          <p className="sign-facts">📍 {quest.place}</p>
          {where?.near ? (
            <p className="sign-here" role="status">You're here. Sniff it now for a Been there bonus.</p>
          ) : (
            where?.away && <p className="sign-away">{where.away}</p>
          )}
          <p className="chips">
            <span className="chip chip-xp">+{quest.xp} XP</span>
            {quest.time === 'long' && <span className="chip chip-trail">Trail</span>}
            <span className="chip chip-herd">{quest.herd ? 'Needs a friend' : 'Herd x2'}</span>
            <Source quest={quest} />
          </p>
        </div>
      ) : (
        <div className="sign sign-done">
          <h3 id="quest-title">All quests done</h3>
          <p className="sign-facts">More tomorrow.</p>
        </div>
      )}

      <div className="choice" role="group" aria-label="Short or long quests">
        {['short', 'long'].map((time) => (
          <button
            key={time}
            type="button"
            className="choice-button"
            aria-pressed={choice === time}
            disabled={!options?.[time]}
            onClick={() => setOpen(options[time])}
          >
            <span className="choice-name">{time === 'short' ? 'Short' : 'Long'}</span>
            <span className="choice-detail">
              {options?.[time] ? `${options[time].minutes ?? MINUTES[time]} min${time === 'long' ? ' trail' : ''}` : 'none open'}
            </span>
          </button>
        ))}
      </div>

      {open && (
        <QuestDetail
          quest={open}
          active={Boolean(quest && open.id === quest.id && choice === open.time)}
          busy={busy}
          onStart={() => start(open.time)}
          onAnother={() => start(open.time)}
          onShowMap={() => {
            setOpen(null)
            onShowMap?.(open.place)
          }}
          onClose={() => setOpen(null)}
        />
      )}
    </section>
  )
}

function Source({ quest }) {
  if (quest.source === 'tinyfish') {
    return webAddress(quest.source_url) ? (
      <a className="chip chip-source" href={quest.source_url} title={`Found by the scout on ${host(quest.source_url)}`}>
        Scout · {host(quest.source_url)}
      </a>
    ) : (
      <span className="chip chip-source">Scout</span>
    )
  }
  return <span className="chip chip-plain">{quest.source === 'sample' ? 'Sample' : 'Starter'}</span>
}

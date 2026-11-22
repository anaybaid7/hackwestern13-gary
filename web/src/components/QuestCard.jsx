// Today's quest card, with Short and Long under it (issue #28). Tap the card
// or either button for the quest's details; start it from there. A long quest
// is a trail walk: the scout takes those from trail and natural-area pages.
// Where a quest came from is one chip: "Scout" only for a live agent run,
// "Sample" or "Starter" otherwise.
import { useState } from 'react'
import { host, webAddress } from '../format.js'
import { tidbitFor } from '../voice.js'
import QuestDetail from './QuestDetail.jsx'

const MINUTES = { short: 15, long: 40 }

export default function QuestCard({ quest, choice, options = {}, onChoose, onShowMap, busy = false, where = null }) {
  const [open, setOpen] = useState(null) // {quest, time}: the quest whose details are showing, and which button

  async function start(time, questId) {
    await onChoose?.(time, questId)
    setOpen(null)
  }

  return (
    <section className="quest" aria-labelledby="quest-title">
      {quest ? (
        <div className={`sign${quest.herd ? ' sign-herd' : ''}`}>
          <p className="sign-top">{choice ? `Your ${choice} quest` : "Today's quest"}</p>
          <h3 id="quest-title">
            <button type="button" className="sign-open" onClick={() => setOpen({ quest, time: choice ?? quest.time })}>
              {quest.title}
            </button>
          </h3>
          <p className="sign-facts">📍 {quest.place}</p>
          {where?.near ? (
            <>
              <p className="sign-here" role="status">You're in range. Sniff it now to finish the quest.</p>
              {tidbitFor(quest) && <p className="sign-tidbit">Gary: {tidbitFor(quest)}</p>}
            </>
          ) : (
            where?.away && <p className="sign-away">{where.away} Get within 1 km to finish it.</p>
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
            onClick={() => setOpen({ quest: options[time], time })}
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
          quest={open.quest}
          active={Boolean(quest && open.quest.id === quest.id && choice === open.time)}
          busy={busy}
          onStart={() => start(open.time, open.quest.id)}
          onAnother={() => start(open.time)}
          onShowMap={() => {
            setOpen(null)
            onShowMap?.(open.quest.place)
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

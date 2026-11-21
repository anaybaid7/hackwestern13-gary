// One find in the journal: what, when, Gary's line, and the marks.
import { clock } from '../format.js'
import { lineFor } from '../voice.js'
import ThingIcon from './ThingIcon.jsx'

export default function FindRow({ entry, fresh = false }) {
  return (
    <li className={`find${fresh ? ' fresh' : ''}`}>
      <ThingIcon name={entry.label} />
      <div className="find-body">
        <p className="find-what">
          <span className="find-label">{entry.label}</span>
          {entry.new && <span className="mark mark-new">new</span>}
          {entry.friend && <span className="mark mark-herd">Herd</span>}
          {entry.quest_id && <span className="mark mark-quest">quest</span>}
        </p>
        <p className="find-line">{lineFor(entry)}</p>
        <p className="find-small">
          {clock(entry.ts)}
          {entry.place ? ` at ${entry.place}` : ''}
          {entry.latency_ms != null && `, named on the device in ${Math.round(entry.latency_ms)} ms`}
        </p>
      </div>
      <span className="find-xp">+{entry.xp} XP</span>
    </li>
  )
}

// One find in the journal: what, the marks, when and where.
import { clock } from '../format.js'
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
        <p className="find-small">
          {clock(entry.ts)}
          {entry.place ? ` · ${entry.place}` : ''}
          {entry.latency_ms != null && <span title="Time the device took to name it"> · {Math.round(entry.latency_ms)} ms</span>}
        </p>
      </div>
      <span className="find-xp">+{entry.xp} XP</span>
    </li>
  )
}

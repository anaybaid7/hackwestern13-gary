// Gary's progress, drawn as the mountain he is climbing. Each stage is a camp
// on the ridge; the yellow marker is where his XP puts him between two camps.
// Every number comes from the state. This file only decides where to draw.
import { STAGES, STAGE_NAMES } from '../words.js'

// Where each camp sits on the drawing (x, y), base camp to summit.
const CAMPS = [
  [18, 74],
  [112, 58],
  [208, 40],
  [300, 22],
]

export default function Climb({ gary }) {
  const at = Math.min(gary.stage_index, CAMPS.length - 1)
  const top = gary.next_stage_xp
  const share = top == null ? 0 : Math.min(1, Math.max(0, (gary.xp - gary.stage_xp) / (top - gary.stage_xp)))
  const [x0, y0] = CAMPS[at]
  const [x1, y1] = CAMPS[Math.min(at + 1, CAMPS.length - 1)]
  const x = x0 + (x1 - x0) * share
  const y = y0 + (y1 - y0) * share
  const ridge = CAMPS.map(([cx, cy]) => `${cx},${cy}`).join(' ')
  const next = STAGE_NAMES[STAGES[at + 1]]
  const label = top == null
    ? `${gary.xp} XP. Gary is at the summit.`
    : `${gary.xp} XP. ${top - gary.xp} more to ${next ?? 'the next stage'}.`

  return (
    <div className="climb">
      <svg viewBox="0 0 320 104" role="img" aria-label={label}>
        <polygon className="rock" points={`0,104 0,78 ${ridge} 320,18 320,104`} />
        <polyline className="trail" points={ridge} />
        <polyline className="trail walked" points={`${CAMPS.slice(0, at + 1).map(([cx, cy]) => `${cx},${cy}`).join(' ')} ${x},${y}`} />
        {CAMPS.map(([cx, cy], i) => (
          <g key={i} className={`camp${i <= at ? ' reached' : ''}`}>
            <path d={`M${cx} ${cy} v-13 l9 4 l-9 4`} />
            <circle cx={cx} cy={cy} r="3" />
            <text x={i === CAMPS.length - 1 ? cx + 14 : cx} y={cy + 21} textAnchor={i === 0 ? 'start' : i === CAMPS.length - 1 ? 'end' : 'middle'}>
              {STAGE_NAMES[STAGES[i]]}
            </text>
          </g>
        ))}
        <circle className="marker" cx={x} cy={y} r="6.5" />
      </svg>
      <p className="xp">{label}</p>
    </div>
  )
}

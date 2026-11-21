// Gary's progress to his next stage, as a pixel bar of ten blocks. Every
// number comes from the state. This file only decides how full to draw it.
import { STAGES, STAGE_NAMES } from '../words.js'

const BLOCKS = 10

export default function Climb({ gary }) {
  const top = gary.next_stage_xp
  const share = top == null ? 1 : Math.min(1, Math.max(0, (gary.xp - gary.stage_xp) / (top - gary.stage_xp)))
  const filled = Math.round(share * BLOCKS)
  const next = STAGE_NAMES[STAGES[gary.stage_index + 1]]
  const label = top == null
    ? `${gary.xp} XP · summit`
    : `${gary.xp} XP · ${top - gary.xp} to ${next ?? 'next stage'}`

  return (
    <div className="climb">
      <div className="xpbar" aria-hidden="true">
        {Array.from({ length: BLOCKS }, (_, i) => (
          <span key={i} className={i < filled ? 'on' : ''} />
        ))}
      </div>
      <p className="xp">{label}</p>
    </div>
  )
}

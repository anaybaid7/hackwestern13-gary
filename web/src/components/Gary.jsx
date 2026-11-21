// Gary himself: a 32 x 32 pixel sprite, one drawing per stage plus a napping
// pose (issue #25). The drawings are in src/sprites.js.
import { garySrc } from '../sprites.js'
import { STAGE_NAMES } from '../words.js'

export default function Gary({ stage, napping = false, grew = false, size = 192 }) {
  const name = STAGE_NAMES[stage] ?? stage
  return (
    <img
      className={`gary${grew ? ' grew' : ''}${napping ? ' asleep' : ''}`}
      src={garySrc(stage, napping)}
      alt={napping ? `Gary the goat, ${name}, napping` : `Gary the goat, ${name}`}
      width={size}
      height={size}
    />
  )
}

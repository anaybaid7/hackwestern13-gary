// Gary himself. One image per stage, plus a napping one: image swaps only
// (issue #25). To change the art, replace the SVG files in src/art/ and keep
// their names.
import ibexNap from '../art/gary-ibex-nap.svg'
import ibex from '../art/gary-ibex.svg'
import kidNap from '../art/gary-kid-nap.svg'
import kid from '../art/gary-kid.svg'
import scramblerNap from '../art/gary-scrambler-nap.svg'
import scrambler from '../art/gary-scrambler.svg'
import elderNap from '../art/gary-summit-elder-nap.svg'
import elder from '../art/gary-summit-elder.svg'
import { STAGE_NAMES } from '../words.js'

const ART = {
  kid: [kid, kidNap],
  scrambler: [scrambler, scramblerNap],
  ibex: [ibex, ibexNap],
  'summit-elder': [elder, elderNap],
}

export default function Gary({ stage, napping = false, grew = false }) {
  const [awake, asleep] = ART[stage] ?? ART.kid
  const name = STAGE_NAMES[stage] ?? stage
  return (
    <img
      className={`gary${grew ? ' grew' : ''}`}
      src={napping ? asleep : awake}
      alt={napping ? `Gary the goat, ${name}, napping` : `Gary the goat, ${name}`}
      width="240"
      height="240"
    />
  )
}

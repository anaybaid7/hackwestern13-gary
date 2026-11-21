// Gary as a 32 x 32 sprite. One base drawing (the kid); each later stage is a
// few edits on top: longer horns, a scarf, a beard. Napping closes his eyes
// and adds a "z". To redraw him, edit BASE and the patches below.
import { CORAL, CREAM, INK, ORANGE, patch, svgDataUri } from './pixel.js'

const PALETTE = {
  k: INK,
  c: CREAM,
  o: ORANGE,
  r: CORAL,
  R: '#C73E30', // the scarf's shadow
  p: '#F4A3A8', // ears and cheeks
  m: '#E8D3AE', // muzzle
  w: '#FFFFFF', // the glint in his eyes
}

const EMPTY = '.'.repeat(32)

const BASE = [
  EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
  '...........kk......kk...........', // 6: horn nubs
  '..........kook....kook..........',
  '..........kkkkkkkkkkkk..........', // 8: top of the head
  '.........kcccccccccccck.........',
  '....kkkkkcccccccccccccckkkkk....', // 10: ears
  '...kcppccccccccccccccccccppck...',
  '...kcppccccwkccccccwkccccppck...', // 12: eyes
  '....kkkkkcckkcccccckkcckkkkk....', // 13: eyes, bottom of the ears
  '........kppccmmmmmmccppk........', // 14: cheeks, muzzle
  '........kcccmmkmmkmmccck........', // 15: nose
  '........kcccmmmkkmmmccck........', // 16: mouth
  '.........kccmmmmmmmmcck.........',
  '..........kkkkkkkkkkkk..........', // 18: chin
  '.........kcccccccccccck.........', // 19: body
  '........kcccccccccccccck........',
  '........kcccccccccccccck........',
  '........kcccccccccccccck........',
  '........kcccccccccccccck........',
  '........kcccccccccccccck........',
  '........kcccccccccccccck........',
  '........kcccccccccccccck........',
  '........kccckkkkkkkkccck........', // 27: legs
  '........kkkkk......kkkkk........', // 28: hooves
  EMPTY, EMPTY, EMPTY,
]

const HORNS_MID = [
  [4, 11, 'kk......kk'],
  [5, 10, 'kook....kook'],
  [6, 10, 'kook....kook'],
]

const HORNS_BIG = [
  [1, 8, 'kk............kk'],
  [2, 8, 'kok..........kok'],
  [3, 9, 'kok........kok'],
  [4, 9, 'kook......kook'],
  [5, 10, 'kook....kook'],
  [6, 10, 'kook....kook'],
]

const SCARF = [
  [19, 9, 'krrrrrrrrrrrrk'],
  [20, 8, 'krrrrrrrrrrrrrrk'],
  [21, 19, 'rR'],
  [22, 19, 'rR'],
  [23, 19, 'rR'],
]

const BEARD = [
  [18, 13, 'cccccc'],
  [19, 13, 'cccccc'],
  [20, 13, 'kcccck'],
  [21, 14, 'kcck'],
  [22, 15, 'kk'],
  [21, 19, 'cc'], // the beard hides the scarf's tail
  [22, 19, 'cc'],
  [23, 19, 'cc'],
]

const ASLEEP = [
  [12, 11, 'cc      cc'], // eyes shut: only the lower line stays (spaces are left as they are)
  [1, 25, 'kkkk'],
  [2, 27, 'k'],
  [3, 26, 'k'],
  [4, 25, 'kkkk'],
]

const STAGE_PATCHES = {
  kid: [],
  scrambler: [...HORNS_MID, ...SCARF],
  ibex: [...HORNS_BIG, ...SCARF],
  'summit-elder': [...HORNS_BIG, ...SCARF, ...BEARD],
}

/** The drawing for a stage, as rows of text. An unknown stage draws as the kid. */
export function garyRows(stage, napping = false) {
  const rows = [...BASE]
  for (const [row, col, text] of STAGE_PATCHES[stage] ?? []) patch(rows, row, col, text)
  if (napping) for (const [row, col, text] of ASLEEP) patch(rows, row, col, text)
  return rows
}

const cache = new Map()

/** The sprite as an image address, for <img src>. */
export function garySrc(stage, napping = false) {
  const key = `${stage}:${napping}`
  if (!cache.has(key)) cache.set(key, svgDataUri(garyRows(stage, napping), PALETTE))
  return cache.get(key)
}

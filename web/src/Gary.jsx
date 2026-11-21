// A placeholder Gary, drawn in SVG. The horns grow with the stage, the beard
// arrives at the last one, and his eyes close when he naps.
// Phase 4 replaces this with the real stage images (issue #25).
const HORN = [10, 20, 34, 44] // horn length per stage

export default function Gary({ stageIndex = 0, napping = false }) {
  const horn = HORN[Math.min(stageIndex, HORN.length - 1)]
  const curl = stageIndex >= 2 ? 16 : 6
  return (
    <svg className="gary" viewBox="0 0 200 180" role="img" aria-label={napping ? 'Gary, napping' : 'Gary the goat'}>
      <path d={`M72 62 q-${curl} -${horn / 2} -${curl / 2} -${horn}`} className="horn" />
      <path d={`M128 62 q${curl} -${horn / 2} ${curl / 2} -${horn}`} className="horn" />
      <ellipse cx="46" cy="84" rx="20" ry="9" transform="rotate(-18 46 84)" className="ear" />
      <ellipse cx="154" cy="84" rx="20" ry="9" transform="rotate(18 154 84)" className="ear" />
      <ellipse cx="100" cy="102" rx="50" ry="56" className="head" />
      <ellipse cx="100" cy="132" rx="26" ry="20" className="muzzle" />
      {napping ? (
        <>
          <path d="M72 96 q8 6 16 0" className="shut" />
          <path d="M112 96 q8 6 16 0" className="shut" />
          <text x="150" y="44" className="zzz">z z z</text>
        </>
      ) : (
        <>
          <ellipse cx="80" cy="94" rx="7" ry="8" className="eye" />
          <ellipse cx="120" cy="94" rx="7" ry="8" className="eye" />
          <rect x="76" y="92" width="8" height="3" rx="1.5" className="pupil" />
          <rect x="116" y="92" width="8" height="3" rx="1.5" className="pupil" />
        </>
      )}
      <path d="M92 126 h16 l-8 8 z" className="nose" />
      <path d="M100 134 v6 M100 140 q-8 6 -14 1 M100 140 q8 6 14 1" className="mouth" />
      {stageIndex >= 3 && <path d="M88 152 q12 30 24 0" className="beard" />}
      {stageIndex >= 1 && <rect x="64" y="160" width="72" height="12" rx="6" className="scarf" />}
    </svg>
  )
}

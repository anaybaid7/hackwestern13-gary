// The Herd Cup and Herd Mode (issue #29). Herds compete; people are never
// ranked. The rival herds are seeded demo data and are labelled as such.
import { clock, ordinal, plural } from '../format.js'
import { BADGES } from '../words.js'

export default function Herd({ herd, journal, flash }) {
  const { cup } = herd
  const latest = journal[0]
  const known = new Set(BADGES.map((badge) => badge.id))
  const badges = [...BADGES, ...herd.badges.filter((id) => !known.has(id)).map((id) => ({ id, name: id, how: '' }))]
  const week = String(cup.week).split('-W')[1]
  const ranked = cup.table.map((row, i) => ({ ...row, rank: row.you ? cup.rank : i + 1 }))

  return (
    <div className="screen">
      <h2>Herd Cup{week ? `, week ${Number(week)}` : ''}</h2>
      <div className="podium" aria-hidden="true">
        {[1, 0, 2].map((i) => ranked[i] && ranked[i].rank <= 3 && (
          <div key={ranked[i].herd} className={`podium-step step-${ranked[i].rank}${ranked[i].you ? ' you' : ''}`}>
            <span className="podium-herd">{ranked[i].herd}</span>
            <span className="podium-block">{ranked[i].rank}</span>
          </div>
        ))}
      </div>
      <ol className="cup">
        {ranked.map((row) => (
          <li key={row.herd} className={`cup-row${row.you ? ' you' : ''}${row.you && flash.rankUp ? ' moved' : ''}`}>
            <span className="cup-rank">{row.rank}</span>
            <span className="cup-herd">
              {row.herd}
              {row.you && (
                <span className="cup-detail">
                  {plural(row.quests ?? 0, 'quest')} together, {plural(row.places ?? 0, 'place')} uncovered
                </span>
              )}
            </span>
            <span className="cup-score">{row.score}</span>
          </li>
        ))}
      </ol>
      <p className="cup-next">
        {flash.rankUp && `Up from ${ordinal(flash.rankUp.from)} to ${ordinal(flash.rankUp.to)}! `}
        {cup.ahead ? `${plural(cup.ahead.gap, 'point')} to pass ${cup.ahead.herd}` : 'Your herd leads this week'}
      </p>
      <p className="small">
        {ordinal(cup.rank)} of {cup.herds} · resets Monday{cup.demo && ' · rival herds are demo data'}
      </p>

      <h3 className="section-title">Herd Mode</h3>
      <p className={`confirm${latest?.friend ? ' yes' : ''}`}>
        {latest?.friend
          ? `Friend in frame · ${latest.label} · ${clock(latest.ts)}`
          : 'Get a friend in frame for double XP.'}
      </p>
      {herd.quest && (
        <div className="sign sign-herd">
          <p className="sign-top">Quest for two</p>
          <h4>{herd.quest.title}</h4>
          <p className="sign-facts">📍 {herd.quest.place}</p>
        </div>
      )}

      <h3 className="section-title">Badges</h3>
      <ul className="badges">
        {badges.map((badge) => {
          const earned = herd.badges.includes(badge.id)
          return (
            <li key={badge.id} className={`badge${earned ? ' earned' : ''}`} title={badge.how}>
              <span className="badge-name">{badge.name}</span>
              {!earned && badge.how && <span className="badge-how">{badge.how}</span>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

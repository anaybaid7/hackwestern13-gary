// Herd Mode and the Herd Cup (issue #29). Herds compete; people are never
// ranked. The rival herds are seeded demo data and are labelled as such.
import { clock, ordinal, plural } from '../format.js'
import { BADGES } from '../words.js'

export default function Herd({ herd, journal, flash }) {
  const { cup } = herd
  const latest = journal[0]
  const known = new Set(BADGES.map((badge) => badge.id))
  const badges = [...BADGES, ...herd.badges.filter((id) => !known.has(id)).map((id) => ({ id, name: id, how: '' }))]
  const week = String(cup.week).split('-W')[1]

  return (
    <div className="screen">
      <h2>Herd</h2>
      <p className="lead">A friend in Gary's frame turns any sniff into Herd Mode. It counts double.</p>

      <p className={`confirm${latest?.friend ? ' yes' : ''}`}>
        {latest?.friend
          ? `Friend in the frame: confirmed by Gary's camera at ${clock(latest.ts)}, on the ${latest.label}.`
          : 'No friend in the last sniff. Stand in Gary\'s view together and press his button.'}
      </p>

      <h3 className="section-title">A quest for two</h3>
      {herd.quest ? (
        <div className="sign sign-herd">
          <h4>{herd.quest.title}</h4>
          <p className="sign-facts">
            At {herd.quest.place}. It only completes with a friend in the frame.
          </p>
        </div>
      ) : (
        <p className="empty">No co-op quest is open right now.</p>
      )}

      <h3 className="section-title">Badges you earned together</h3>
      <ul className="badges">
        {badges.map((badge) => {
          const earned = herd.badges.includes(badge.id)
          return (
            <li key={badge.id} className={`badge${earned ? ' earned' : ''}`}>
              <span className="badge-name">{badge.name}</span>
              <span className="badge-how">{earned ? 'Earned' : badge.how}</span>
            </li>
          )
        })}
      </ul>
      <p className="small">{plural(herd.shared, 'find')} with a friend in the frame so far.</p>

      <h3 className="section-title">Herd Cup{week ? `, week ${Number(week)}` : ''}</h3>
      <ol className="cup">
        {cup.table.map((row, i) => (
          <li key={row.herd} className={`cup-row${row.you ? ' you' : ''}${row.you && flash.rankUp ? ' moved' : ''}`}>
            <span className="cup-rank">{row.you ? cup.rank : i + 1}</span>
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
        {flash.rankUp && `Up from ${ordinal(flash.rankUp.from)} to ${ordinal(flash.rankUp.to)}. `}
        {cup.ahead
          ? `${plural(cup.ahead.gap, 'more point')} to pass ${cup.ahead.herd}.`
          : 'Your herd leads this week.'}
      </p>
      <p className="small">
        Your herd is {ordinal(cup.rank)} of {cup.herds} this week. A point is a quest finished together or a place
        uncovered together. The cup starts again every Monday.
      </p>
      <p className="small">
        Herds compete. People are never ranked.{cup.demo && ' The rival herds are demo data.'}
      </p>
      <p className="small">Gary never identifies anyone. A friend is a person in the frame, and nothing more.</p>
    </div>
  )
}

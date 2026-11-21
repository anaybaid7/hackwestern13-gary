// The field guide and the journal (issue #27). Every thing Gary can
// recognise: found ones in colour, the rest as silhouettes. Then today's finds.
import FindRow from '../components/FindRow.jsx'
import ThingIcon from '../components/ThingIcon.jsx'
import { isToday } from '../format.js'
import { INDOOR, OUTDOOR } from '../things.js'

export default function Guide({ guide, journal, now, flash }) {
  const found = new Set(guide.found)
  const today = journal.filter((entry) => isToday(entry.ts, now))
  const earlier = journal.filter((entry) => !isToday(entry.ts, now))
  const justFound = flash.find?.new ? flash.find.label : null

  return (
    <div className="screen">
      <h2>Field guide</h2>
      <p className="count">
        {guide.found.length} of {guide.total} found
      </p>
      <Group title="Outdoors" things={OUTDOOR} found={found} fresh={justFound}
             note="First finds out here earn the most." />
      <Group title="Indoors" things={INDOOR} found={found} fresh={justFound} />

      <h3 className="section-title">Today's finds</h3>
      {today.length === 0 ? (
        <p className="empty">Nothing yet today. Point Gary at something and press his button.</p>
      ) : (
        <ul className="finds">
          {today.map((entry) => (
            <FindRow key={entry.id} entry={entry} fresh={flash.find?.id === entry.id} />
          ))}
        </ul>
      )}
      {earlier.length > 0 && (
        <>
          <h3 className="section-title">Earlier</h3>
          <ul className="finds">
            {earlier.map((entry) => (
              <FindRow key={entry.id} entry={entry} />
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function Group({ title, things, found, fresh, note }) {
  const got = things.filter((thing) => found.has(thing.name)).length
  return (
    <section className="group">
      <h3 className="section-title">
        {title} <span className="group-count">{got} of {things.length}</span>
      </h3>
      {note && <p className="small">{note}</p>}
      <ul className="specimens">
        {things.map((thing) => {
          const has = found.has(thing.name)
          return (
            <li
              key={thing.name}
              className={`specimen ${has ? 'got' : 'locked'}${fresh === thing.name ? ' fresh' : ''}`}
              aria-label={has ? thing.name : 'Not found yet'}
            >
              <ThingIcon name={thing.name} locked={!has} />
              {has && <span className="specimen-name">{thing.name}</span>}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

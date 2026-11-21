// The journal (issue #27), in two tabs: the finds, newest first, and the
// field guide of every thing Gary can recognise, found ones in colour and the
// rest as silhouettes.
import { useState } from 'react'
import FindRow from '../components/FindRow.jsx'
import ThingIcon from '../components/ThingIcon.jsx'
import { isToday } from '../format.js'
import { INDOOR, OUTDOOR } from '../things.js'

export default function Guide({ guide, journal, now, flash, view: start = 'finds' }) {
  const [view, setView] = useState(start)
  const found = new Set(guide.found)
  const today = journal.filter((entry) => isToday(entry.ts, now))
  const earlier = journal.filter((entry) => !isToday(entry.ts, now))
  const justFound = flash.find?.new ? flash.find.label : null

  return (
    <div className="screen">
      <h2>Journal</h2>
      <span className="chip chip-count">
        {guide.found.length} of {guide.total} found
      </span>
      <div className="segmented" role="group" aria-label="Journal view">
        {[['finds', 'Finds'], ['guide', 'Field guide']].map(([id, name]) => (
          <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}>
            {name}
          </button>
        ))}
      </div>

      {view === 'guide' && (
        <>
          <Group title="Outdoors" things={OUTDOOR} found={found} fresh={justFound} />
          <Group title="Indoors" things={INDOOR} found={found} fresh={justFound} />
        </>
      )}

      {view === 'finds' && <Finds today={today} earlier={earlier} flash={flash} />}
    </div>
  )
}

function Finds({ today, earlier, flash }) {
  return (
    <>
      <h3 className="section-title">Today's finds</h3>
      {today.length === 0 ? (
        <p className="empty">Nothing yet today.</p>
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
    </>
  )
}

function Group({ title, things, found, fresh }) {
  const got = things.filter((thing) => found.has(thing.name)).length
  return (
    <section className="group">
      <h3 className="section-title">
        {title} <span className="group-count">{got} of {things.length}</span>
      </h3>
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

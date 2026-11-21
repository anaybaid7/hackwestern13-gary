// Settings: the check-in pop-up, the private wellness view, where the page
// gets Gary's state from, and the promises Gary keeps.
import { useState } from 'react'
import { readAsk, writeAsk } from '../components/CheckIn.jsx'
import You from './You.jsx'

const STATUS_WORDS = { live: 'Live', mock: 'Demo story', stale: 'Offline · last state' }

export default function Settings({ service, stamp, status }) {
  const [ask, setAsk] = useState(readAsk)

  function toggle() {
    writeAsk(!ask)
    setAsk(!ask)
  }

  return (
    <div className="screen settings">
      <h2>Settings</h2>

      <section className="panel">
        <h3 className="section-title">Check-in</h3>
        <label className="switch">
          <input type="checkbox" checked={ask} onChange={toggle} />
          <span>Ask how I feel when I open Gary</span>
        </label>
      </section>

      <section className="panel">
        <You service={service} stamp={stamp} />
      </section>

      <section className="panel">
        <h3 className="section-title">Connection</h3>
        <p>{STATUS_WORDS[status]}</p>
        {service.mode === 'live' && <p className="small">Backend: {service.api || 'this address'}</p>}
        <p className="small">
          {service.mode === 'mock' ? (
            <a href="?">Leave the demo story</a>
          ) : (
            <a href="?mock">Open the demo story</a>
          )}
        </p>
      </section>

      <section className="panel">
        <h3 className="section-title">Gary's promises</h3>
        <ul className="promises">
          <li>No streaks. Breaks are naps.</li>
          <li>No photos kept. Only names of things.</li>
          <li>Friends are never identified.</li>
          <li>Herds are ranked. People never are.</li>
          <li>Check-ins never show in Gary's world or the herd.</li>
        </ul>
      </section>
    </div>
  )
}

// The fog-of-war map (issue #26). Each tile is a real place the scout found.
// A fogged tile shows fog; a cleared tile shows its name. Tap a cleared tile
// to see what was found there and when.
import { useState } from 'react'
import { clock, dayName, dayKey, plural } from '../format.js'

const TILES = 25

export default function MapScreen({ map, flash, questPlace }) {
  const [picked, setPicked] = useState(null)
  const cells = [...map.slice(0, TILES)]
  while (cells.length < TILES) cells.push(null)
  const cleared = map.filter((tile) => tile.cleared).length
  const chosen = picked != null ? cells[picked] : null

  return (
    <div className="screen">
      <h2>Map</h2>
      <p className="lead">
        {cleared} of {plural(map.length, 'place')} uncovered. Finish a quest at a place and its fog lifts.
      </p>
      <div className="map">
        {cells.map((tile, i) => {
          if (!tile) return <div key={i} className="tile empty" aria-hidden="true" />
          const here = !tile.cleared && questPlace === tile.place
          const fresh = flash.cleared.includes(tile.place)
          return (
            <button
              key={i}
              type="button"
              className={`tile ${tile.cleared ? 'cleared' : 'fog'}${fresh ? ' fresh' : ''}${here ? ' here' : ''}`}
              aria-pressed={picked === i}
              aria-label={tile.cleared ? `${tile.place}, uncovered` : here ? 'Fog. Your quest is here' : 'Fog'}
              onClick={() => setPicked(picked === i ? null : i)}
            >
              {tile.cleared && <span className="tile-name">{tile.place}</span>}
            </button>
          )
        })}
      </div>

      <div className="tile-detail" aria-live="polite">
        {!chosen && <p className="empty">Tap an uncovered place to see what was found there.</p>}
        {chosen && !chosen.cleared && (
          <p>
            {questPlace === chosen.place
              ? 'Fog. The quest on your card is here.'
              : 'Fog. Something is out here. Finish a quest at this place to see what.'}
          </p>
        )}
        {chosen?.cleared && (
          <>
            <h3>{chosen.place}</h3>
            {chosen.cleared_at && (
              <p className="small">
                Uncovered on {dayName(dayKey(chosen.cleared_at))} at {clock(chosen.cleared_at)}.
              </p>
            )}
            <ul className="tile-finds">
              {(chosen.finds ?? []).map((find, n) => (
                <li key={n}>
                  A {find.label}, at {clock(find.ts)}
                  {find.friend ? ', with a friend in the frame' : ''}.
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}

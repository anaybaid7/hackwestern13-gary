// The fog-of-war map (issue #26), on OpenStreetMap: real streets and park
// names, dimmed by fog everywhere except round the places you have cleared.
// Each place from a quest is a pin. Your own position is a dot, read from
// the browser and kept there. It is sent nowhere, unless you switch on
// "Explorers nearby" in Settings: then it is shared, rounded, with the others
// who have it on, and their dots are drawn here (see nearby.js).
//
// Two ways to draw it, the same state on both: a 3D London (World3D, with
// MapLibre) wherever the browser can draw WebGL, and the flat map
// (FlatWorld, with Leaflet) everywhere else, or when you ask for it. The 3D
// map is loaded only when it is used.
//
// Everything here only draws what the state says. Which places are cleared,
// and when, comes from the backend; the trail, the frontier and the reveal
// are pictures of that.
import { Component, Suspense, lazy, useEffect, useRef, useState } from 'react'
import { useWhereAmI } from '../whereAmI.js'
import { clock, dayName, dayKey } from '../format.js'
import { LONDON, away, layout, realSpot, realSpots } from '../places.js'
import { can3d, savedLook, saveLook } from '../map/look.js'
import { goatName } from '../auth.js'
import { nearbyLine, readNearby, useNearby } from '../nearby.js'
import FlatWorld from './FlatWorld.jsx'

const World3D = lazy(() => import('./World3D.jsx'))

/** The 3D map's code did not arrive (offline, an old cached page): fall back to the flat one. */
class Fallback extends Component {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  componentDidCatch(error) {
    this.props.onFail(error)
  }
  render() {
    return this.state.failed ? null : this.props.children
  }
}

export default function MapScreen({ map, flash, quest = null, focusPlace = null, quests = [], onPickQuest = null, busy = false, service = null, sharing = readNearby() }) {
  const [picked, setPicked] = useState(focusPlace)
  const [streets, setStreets] = useState('loading') // 'loading' | 'on' | 'off': whether street tiles arrive
  const [broken, setBroken] = useState(false) // the 3D map would not start here
  const [look, setLook] = useState(() => (can3d() ? savedLook() : 'flat'))
  const view = useRef(null)
  const me = useWhereAmI()
  const explorers = useNearby(service, me, quest?.id, sharing)
  const spots = layout(map.map((tile) => tile.place), realSpots(map))
  const cleared = map.filter((tile) => tile.cleared)
  const chosen = map.find((tile) => tile.place === picked) ?? null
  const questPlace = quest?.place
  const questAt = questPlace ? spots.get(questPlace) : null
  const first = spots.get(focusPlace) ?? questAt ?? spots.get(cleared[0]?.place) ?? LONDON
  const three = look === '3d' && !broken

  function failed(error) {
    console.warn('The 3D map could not start; showing the flat map.', error)
    setBroken(true)
  }

  function switchLook() {
    const next = three ? 'flat' : '3d'
    saveLook(next)
    setBroken(false)
    setStreets('loading')
    setLook(next)
  }

  const world = {
    ref: view,
    tiles: map,
    spots,
    questPlace,
    picked,
    fresh: flash.cleared,
    onPick: (place) => setPicked((p) => (p === place ? null : place)),
    me,
    others: explorers.others.map((o) => ({ ...o, name: goatName(o.tag) })),
    first: spots.get(picked) ?? first,
    onStreets: setStreets,
  }

  // a place that has just cleared: bring it into view so its reveal is seen
  const freshPlace = flash.cleared.find((place) => spots.has(place)) ?? null
  useEffect(() => {
    if (!freshPlace || focusPlace) return
    view.current?.goTo(spots.get(freshPlace))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when a new place clears
  }, [freshPlace])

  // "See on map" from a quest: fly there
  useEffect(() => {
    if (!focusPlace) return
    setPicked(focusPlace)
    const at = spots.get(focusPlace)
    if (at) view.current?.goTo(at, 15)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when asked to look somewhere new
  }, [focusPlace])

  function findMe() {
    if (me.at) view.current?.goTo(me.at, 15)
  }

  function goToQuest() {
    if (!questAt) return
    setPicked(questPlace)
    view.current?.goTo(questAt, 15)
  }

  function showAll() {
    const all = [...spots.values()]
    if (me.at) all.push(me.at)
    view.current?.fit(all)
  }

  const chosenAway = chosen && me.at ? away(me.at, spots.get(chosen.place)) : null
  // walking directions to a real place, in the phone's own maps app. Only the
  // place is in the link: the maps app finds where you are itself, so Gary
  // still never sends your position anywhere.
  const chosenSpot = chosen ? realSpot(chosen) : null
  const directions = chosenSpot
    ? `https://www.google.com/maps/dir/?api=1&destination=${chosenSpot[0]},${chosenSpot[1]}&travelmode=walking`
    : null
  // an open quest at the tapped place, other than the one you are on: you can switch to it from here
  const waiting = chosen && !chosen.cleared ? quests.find((q) => q.id === chosen.quest_id && q.id !== quest?.id) ?? null : null

  return (
    <div className="screen map-screen">
      <div className="map-head">
        <h2>Map</h2>
        <span className="chip chip-count">
          {cleared.length}/{map.length} uncovered
        </span>
      </div>
      {map.length > 0 && (
        <div className="explored" aria-hidden="true">
          {map.map((_, n) => (
            <span key={n} className={`explored-cell${n < cleared.length ? ' on' : ''}${n < cleared.length && n >= cleared.length - flash.cleared.length ? ' fresh' : ''}`} />
          ))}
        </div>
      )}

      <div className="world">
        {three ? (
          <Fallback key="3d" onFail={failed}>
            <Suspense fallback={<p className="map-note map-loading" role="status">Building London…</p>}>
              <World3D {...world} onFail={failed} />
            </Suspense>
          </Fallback>
        ) : (
          <FlatWorld key="flat" {...world} />
        )}
        <div className="map-tools">
          <button type="button" onClick={goToQuest} disabled={!questAt}>Quest</button>
          <button type="button" onClick={showAll} disabled={map.length === 0 && !me.at}>All places</button>
          {can3d() && (
            <button type="button" className="look" onClick={switchLook} aria-pressed={three}
                    aria-label={three ? 'Show the flat map' : 'Show the map in 3D'}>
              {three ? '2D' : '3D'}
            </button>
          )}
        </div>
        <button type="button" className="locate" onClick={findMe} disabled={!me.at}
                aria-label={me.at ? 'Show where I am' : me.state === 'denied' ? 'Location is off' : 'Finding you'}>
          ◎
        </button>
        {streets === 'off' && <p className="map-note" role="status">No street map right now. The fog and the pins still work.</p>}
      </div>
      {me.state === 'denied' && <p className="small">Location is off. Allow it to see yourself on the map.</p>}
      {explorers.state !== 'off' && (
        <p className="nearby-line" role="status">
          <span className="nearby-dot" aria-hidden="true" />
          {explorers.state === 'waiting' && 'Explorers nearby is on. Finding where you are…'}
          {explorers.state === 'offline' && 'Explorers nearby: no connection right now.'}
          {explorers.state === 'on' && nearbyLine(explorers.others)}
        </p>
      )}

      <ul className="map-key">
        <li><span className="key-mark key-fog">?</span>Fog</li>
        <li><span className="key-mark key-quest">!</span>Your quest</li>
        <li><span className="key-mark key-flag" />Uncovered</li>
        <li><span className="key-mark key-trail" />Your trail</li>
      </ul>

      <div className="sheet" aria-live="polite">
        {!chosen && <p className="empty">Tap a pin.</p>}
        {chosen && !chosen.cleared && (questPlace === chosen.place || !waiting) && (
          <>
            <h3>{questPlace === chosen.place ? chosen.place : 'Still in fog'}</h3>
            {questPlace === chosen.place && <p className="small">Your quest is here.{quest.note ? ` ${quest.note}` : ''}</p>}
          </>
        )}
        {waiting && questPlace !== chosen.place && (
          <>
            <h3>{waiting.place}</h3>
            <p className="small">
              {waiting.title} · {waiting.time === 'long' ? 'Long' : 'Short'} · +{waiting.xp} XP
            </p>
            {onPickQuest && (
              <button type="button" className="button primary" disabled={busy} onClick={() => onPickQuest(waiting)}>
                Make this my quest
              </button>
            )}
          </>
        )}
        {chosen?.cleared && (
          <>
            <h3>{chosen.place}</h3>
            {chosen.cleared_at && (
              <p className="small">
                Uncovered {dayName(dayKey(chosen.cleared_at))}, {clock(chosen.cleared_at)}
              </p>
            )}
            <ul className="tile-finds">
              {(chosen.finds ?? []).map((find, n) => (
                <li key={n}>
                  {find.label} · {clock(find.ts)}
                  {find.friend ? ' · Herd' : ''}
                </li>
              ))}
            </ul>
          </>
        )}
        {chosenAway && <p className="small away">{chosenAway}</p>}
        {directions && (
          <a className="button walk" href={directions} target="_blank" rel="noreferrer">
            Walk there ↗
          </a>
        )}
      </div>
    </div>
  )
}

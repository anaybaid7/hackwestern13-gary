// The browser's own location. It stays in the browser: the map draws it, and
// the page works out from it whether you are at your quest's place. Only that
// yes (a "visit" to a quest) is ever sent, never where you are.
import { useEffect, useState } from 'react'

const OFF = { state: 'off', at: null, accuracy: null }

/** Follows the browser's location while `on`. */
export function useWhereAmI(on = true) {
  const [me, setMe] = useState(OFF)
  useEffect(() => {
    const geo = navigator.geolocation
    if (!on || !geo) return undefined
    setMe((m) => ({ ...m, state: 'asking' }))
    const id = geo.watchPosition(
      (pos) => setMe({ state: 'on', at: [pos.coords.latitude, pos.coords.longitude], accuracy: pos.coords.accuracy }),
      () => setMe({ ...OFF, state: 'denied' }),
      { enableHighAccuracy: true, maximumAge: 10000 },
    )
    return () => geo.clearWatch(id)
  }, [on])
  return me
}

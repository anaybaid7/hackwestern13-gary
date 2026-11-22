// Explorers nearby: other people out with a Gary, near you or on your quest,
// as moving dots on the map. Off unless you switch it on in Settings.
//
// While it is on, this page sends where you are every few seconds and gets
// back the others who have it on too. The backend keeps none of it: a dot
// that is not refreshed is gone within a minute, positions are rounded to
// about 100 m, and nobody is named. See backend/nearby.py.
import { useEffect, useRef, useState } from 'react'

const ON_KEY = 'gary.nearby'
const ID_KEY = 'gary.nearby.id'
export const EVERY_MS = 6000

export function readNearby() {
  try {
    return window.localStorage.getItem(ON_KEY) === 'on' // off unless you have said yes
  } catch {
    return false
  }
}

export function writeNearby(on) {
  try {
    window.localStorage.setItem(ON_KEY, on ? 'on' : 'off')
  } catch {
    // no storage: it stays off
  }
}

/** A random id made on this device. It names nobody; it only lets this page move or remove its own dot. */
export function deviceId() {
  try {
    const saved = window.localStorage.getItem(ID_KEY)
    if (saved && /^[0-9a-f]{32}$/.test(saved)) return saved
    const bytes = new Uint8Array(16)
    window.crypto.getRandomValues(bytes)
    const id = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('')
    window.localStorage.setItem(ID_KEY, id)
    return id
  } catch {
    return null
  }
}

/** Take this device's dot off everyone's map at once (the switch was turned off). */
export function leaveNearby(service) {
  const id = deviceId()
  if (id && service?.leaveNearby) service.leaveNearby(id).catch(() => {})
}

/**
 * While `on` and the browser knows where you are: tell the backend, and keep
 * the explorers it sends back. -> {others, state}: 'off' | 'waiting' (no
 * position yet) | 'on' | 'offline'.
 */
export function useNearby(service, me, questId, on) {
  const [seen, setSeen] = useState({ others: [], state: 'off' })
  const latest = useRef({ me, questId })
  latest.current = { me, questId }
  const located = Boolean(me.at)

  useEffect(() => {
    if (!on || !service?.shareSpot) {
      setSeen({ others: [], state: 'off' })
      return undefined
    }
    if (!located) {
      setSeen({ others: [], state: 'waiting' })
      return undefined
    }
    const id = deviceId()
    if (!id) return undefined
    let alive = true
    const tell = async () => {
      const { me: now, questId: quest } = latest.current
      if (!now.at) return
      try {
        const out = await service.shareSpot({ id, lat: now.at[0], lon: now.at[1], quest_id: quest || undefined })
        if (alive) setSeen({ others: out.nearby ?? [], state: 'on' })
      } catch {
        if (alive) setSeen((had) => ({ others: had.others, state: 'offline' }))
      }
    }
    tell()
    const timer = setInterval(tell, EVERY_MS)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [on, located, service])

  return seen
}

/** "2 explorers nearby, 1 on your quest": the line under the map. */
export function nearbyLine(others) {
  if (others.length === 0) return 'No other explorers nearby right now.'
  const same = others.filter((o) => o.same_quest).length
  const count = `${others.length} explorer${others.length === 1 ? '' : 's'} nearby`
  return same ? `${count}, ${same} on your quest.` : `${count}.`
}

// Where the page gets Gary's state from.
//
//   npm run dev                                       mock mode: contract/examples/state.json, no backend
//   VITE_API_URL=http://localhost:8000 npm run dev    the real backend
//   npm run build                                     the address the page is served from
//                                                     (the backend serves web/dist itself)
//
// At run time, add ?api=http://host:8000 or ?mock to the page address to override.
//
// This file is the only place that talks to the backend. Phase 4 swaps the
// prototype's mock services for calls like getState() here (issue #24).
import exampleState from '../../contract/examples/state.json'

const params = new URLSearchParams(window.location.search)
const fromQuery = params.get('api')
const fromEnv = import.meta.env.VITE_API_URL

export const MOCK = params.has('mock') || (!fromQuery && fromEnv === undefined && import.meta.env.DEV)
export const API = (fromQuery ?? fromEnv ?? '').replace(/\/$/, '')

async function call(path, options) {
  const reply = await fetch(`${API}${path}`, options)
  if (!reply.ok) throw new Error(`HTTP ${reply.status}`)
  return reply.json()
}

/** Everything the page draws. The shape is contract/examples/state.json. */
export function getState() {
  return MOCK ? Promise.resolve(exampleState) : call('/api/state')
}

/** A private mood check-in: phase is "before" or "after", value is 1 to 5. */
export function postMood(phase, value) {
  if (MOCK) return Promise.resolve({ ok: true })
  return call('/api/mood', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phase, value }),
  })
}

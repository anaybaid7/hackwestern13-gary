// One setting decides where Gary's state comes from. Every screen uses the
// same calls, whichever service is behind them (issue #24):
//
//   getState()  chooseQuest(time)  postMood(phase, value)  getWellness()  now()
//
//   npm run dev                                       mock: the demo story, no backend
//   VITE_API_URL=http://localhost:8000 npm run dev    live: the real backend
//   npm run build                                     live: the address the page is served from
//
// At run time, ?mock in the page address plays the story. With `npm run dev`,
// ?api=http://host:8000 points the page at a backend somewhere else. The
// built page ignores ?api: a link must never be able to send someone's
// private check-ins to another server.
import { createLive } from './live.js'

/** -> {mode: 'mock'} or {mode: 'live', api}. */
export function pickMode(search = '', env = {}) {
  const params = new URLSearchParams(search)
  if (params.has('mock')) return { mode: 'mock', step: Number(params.get('step')) || 0 }
  const fromQuery = params.get('api')
  if (fromQuery && env.DEV) return { mode: 'live', api: fromQuery }
  if (env.VITE_API_URL !== undefined) return { mode: 'live', api: env.VITE_API_URL }
  if (env.DEV) return { mode: 'mock', step: 0 }
  return { mode: 'live', api: '' } // the built page: the backend that serves it
}

export async function createService(search = window.location.search, env = import.meta.env) {
  const picked = pickMode(search, env)
  if (picked.mode === 'mock') {
    // Loaded only when needed, so the live page does not carry the story.
    const { createMock } = await import('./mock.js')
    return createMock({ step: picked.step })
  }
  return createLive(picked.api)
}

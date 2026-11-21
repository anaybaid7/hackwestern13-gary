// The real backend. The shapes are in contract/README.md.
export function createLive(api = '', fetchFn = (...args) => fetch(...args)) {
  const base = api.replace(/\/$/, '')

  async function call(path, body) {
    const options = body === undefined
      ? undefined
      : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
    const reply = await fetchFn(`${base}${path}`, options)
    if (!reply.ok) throw new Error(`HTTP ${reply.status}`)
    return reply.json()
  }

  return {
    mode: 'live',
    api: base,
    /** The clock that "today" is read from. */
    now: () => new Date(),
    /** Everything the page draws. */
    getState: () => call('/api/state'),
    /** "short" or "long" -> {quest, state}. */
    chooseQuest: (time) => call('/api/quest/choose', { time }),
    /** A private check-in: phase "before" or "after", value 1 to 5. */
    postMood: (phase, value) => call('/api/mood', { phase, value }),
    /** The private wellness view. */
    getWellness: () => call('/api/wellness'),
  }
}

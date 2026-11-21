// The real backend. The shapes are in contract/README.md.

// The passphrase of the private page, kept on this device once it has been
// typed. Storage can be missing or refuse (private browsing): then it is kept
// for this visit only.
const KEY_NAME = 'gary-private-key'
let rememberedHere = ''

function readKey() {
  try {
    return window.localStorage.getItem(KEY_NAME) || rememberedHere
  } catch {
    return rememberedHere
  }
}

function saveKey(value) {
  rememberedHere = value
  try {
    if (value) window.localStorage.setItem(KEY_NAME, value)
    else window.localStorage.removeItem(KEY_NAME)
  } catch {
    // kept for this visit only
  }
}

export function createLive(api = '', fetchFn = (...args) => fetch(...args)) {
  const base = api.replace(/\/$/, '')

  // `secret`: a call to the private side. It carries the passphrase, if this
  // device has one, and a 401 means the page is locked.
  async function call(path, body, secret = false) {
    const headers = {}
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const key = secret ? readKey() : ''
    if (key) headers['X-Private-Key'] = key
    const options = body === undefined && !key
      ? undefined
      : { method: body === undefined ? 'GET' : 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body) }
    const reply = await fetchFn(`${base}${path}`, options)
    if (!reply.ok) {
      const error = new Error(`HTTP ${reply.status}`)
      error.locked = secret && reply.status === 401
      throw error
    }
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
    postMood: (phase, value) => call('/api/mood', { phase, value }, true),
    /** The private wellness view. Throws an error with `locked` when the page needs its passphrase. */
    getWellness: () => call('/api/wellness', undefined, true),
    /** Try a passphrase. It is kept on this device only if it opens the page. */
    unlock: async (passphrase) => {
      const before = readKey()
      saveKey(String(passphrase))
      try {
        return await call('/api/wellness', undefined, true)
      } catch (error) {
        saveKey(before)
        throw error
      }
    },
    /** Forget the passphrase on this device. */
    forgetKey: () => saveKey(''),
  }
}

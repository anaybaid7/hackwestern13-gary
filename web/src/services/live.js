// The real backend. The shapes are in contract/README.md.
import { createAuth } from '../auth.js'

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

export function createLive(api = '', fetchFn = (...args) => fetch(...args), makeAuth = createAuth) {
  const base = api.replace(/\/$/, '')

  // Signing in (Auth0), started the first time someone asks for it.
  let account = null
  const getAccount = () => {
    if (!account) account = makeAuth({ api: base, fetchFn }).catch(() => ({ enabled: false, reason: 'no-config', signedIn: false, token: async () => '' }))
    return account
  }
  // The token of a signed-in person, or ''. Never asks anyone to sign in.
  const bearer = async () => (account ? (await account).token() : '')

  // `secret`: a call to the private side. It carries the passphrase, if this
  // device has one, and a 401 means the page is locked.
  async function call(path, body, secret = false) {
    const headers = {}
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const key = secret ? readKey() : ''
    if (key) headers['X-Private-Key'] = key
    const token = secret ? await bearer() : ''
    if (token) headers.Authorization = `Bearer ${token}`
    const options = body === undefined && !key && !token
      ? undefined
      : { method: body === undefined ? 'GET' : 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body) }
    const reply = await fetchFn(`${base}${path}`, options)
    if (!reply.ok) {
      const error = new Error(`HTTP ${reply.status}`)
      error.locked = secret && reply.status === 401
      error.status = reply.status
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
    /** "short" or "long" -> {quest, state}. With a quest id: that quest. */
    chooseQuest: (time, questId) => call('/api/quest/choose', questId ? { time, quest_id: questId } : { time }),
    /** Every open quest, with its position: the page picks the nearest short one itself. */
    getQuests: () => call('/api/quests').then((out) => out.quests),
    /** A private check-in: phase "before" or "after", value 1 to 5. */
    postMood: (phase, value) => call('/api/mood', { phase, value }, true),
    /** The page is at this quest's place. Only the id is sent, never a position. */
    postVisit: (questId) => call('/api/visit', { quest_id: questId }),
    /** {enabled}: whether this server can talk (gary_talk.py and both keys). */
    talkConfig: () => call('/api/talk'),
    /** The question after "Go Gary": {audio: base64 WAV, history} -> Gary's reply. */
    talk: (body) => call('/api/talk', body),
    /** Send the scout out now: {sent, running, ...}. A run takes minutes; its quests arrive on their own. */
    runScout: () => call('/api/scout/run', {}),
    /** Picks for you: the last good picks, the request running now, and the last few requests. */
    getPicks: () => call('/api/picks'),
    /** Start a picks request. `near` is the name of a known place, or null: never a position. */
    askPicks: (near = null) => call('/api/picks', { near }),
    /** Make a pick today's quest -> {quest, state}. */
    takePick: (questId) => call('/api/picks/take', { id: questId }),
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
    /**
     * For testing: forget every sniff and check-in. The quests stay and are all
     * open again. A server with an admin key wants it; it is sent, never kept.
     * Throws an error with `needsKey` when the key is missing or wrong.
     */
    /** Signing in: {enabled, reason?, signedIn, signIn(), signOut()}. */
    account: getAccount,
    /** Who Gary thinks you are: {signed_in, fingerprint, paired, permissions}. */
    getMe: async () => {
      await getAccount()
      return call('/api/me', undefined, true)
    },
    resetGary: async (adminKey = '') => {
      const headers = { 'Content-Type': 'application/json' }
      if (adminKey) headers['X-Admin-Key'] = adminKey
      const token = await bearer()
      if (token) headers.Authorization = `Bearer ${token}`
      const reply = await fetchFn(`${base}/api/dev/reset`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ keep_quests: true }),
      })
      if (!reply.ok) {
        const error = new Error(`HTTP ${reply.status}`)
        error.needsKey = reply.status === 401
        throw error
      }
      return reply.json()
    },
  }
}

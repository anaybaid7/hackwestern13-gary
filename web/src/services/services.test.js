// The two services behind one interface (issue #24). Run with: npm test
import { describe, expect, test, vi } from 'vitest'
import story from '../../../contract/examples/story.json'
import { pickMode } from './index.js'
import { createLive } from './live.js'
import { createMock } from './mock.js'

describe('one setting switches between mock and live', () => {
  test('the page address wins, then the build setting, then the kind of build', () => {
    expect(pickMode('?mock', { VITE_API_URL: 'http://x' })).toEqual({ mode: 'mock', step: 0 })
    expect(pickMode('?mock&step=4', {})).toEqual({ mode: 'mock', step: 4 })
    expect(pickMode('?api=http://pi.local:8000', { DEV: true })).toEqual({ mode: 'live', api: 'http://pi.local:8000' })
    // The built page ignores ?api. Otherwise a link could send someone's private check-ins to another server.
    expect(pickMode('?api=http://elsewhere.example', { DEV: false })).toEqual({ mode: 'live', api: '' })
    expect(pickMode('?api=http://elsewhere.example', {})).toEqual({ mode: 'live', api: '' })
    expect(pickMode('?api=http://elsewhere.example', { VITE_API_URL: 'http://ours' })).toEqual({ mode: 'live', api: 'http://ours' })
    expect(pickMode('', { VITE_API_URL: 'http://localhost:8000' })).toEqual({ mode: 'live', api: 'http://localhost:8000' })
    expect(pickMode('', { DEV: true })).toEqual({ mode: 'mock', step: 0 }) // npm run dev with nothing set
    expect(pickMode('', { DEV: false })).toEqual({ mode: 'live', api: '' }) // the built page: same address
  })

  test('both services offer the same calls', () => {
    const calls = ['getState', 'chooseQuest', 'postMood', 'getWellness', 'now', 'unlock', 'forgetKey', 'resetGary']
    const live = createLive('http://x')
    const mock = createMock()
    for (const name of calls) {
      expect(typeof live[name], `live.${name}`).toBe('function')
      expect(typeof mock[name], `mock.${name}`).toBe('function')
    }
  })
})

describe('live', () => {
  function fakeFetch(reply = { ok: true }) {
    return vi.fn(async () => ({ ok: true, status: 200, json: async () => reply }))
  }

  test('each call goes to the endpoint in the contract', async () => {
    const fetchFn = fakeFetch()
    const live = createLive('http://gary.example/', fetchFn)
    await live.getState()
    await live.chooseQuest('long')
    await live.postMood('after', 4)
    await live.getWellness()
    const seen = fetchFn.mock.calls.map(([url, options]) => [url, options?.method ?? 'GET', options?.body])
    expect(seen).toEqual([
      ['http://gary.example/api/state', 'GET', undefined],
      ['http://gary.example/api/quest/choose', 'POST', '{"time":"long"}'],
      ['http://gary.example/api/mood', 'POST', '{"phase":"after","value":4}'],
      ['http://gary.example/api/wellness', 'GET', undefined],
    ])
  })

  test('a refused call is an error, and the same address works with no prefix', async () => {
    const live = createLive('', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })))
    await expect(live.getState()).rejects.toThrow('HTTP 503')
    const fetchFn = fakeFetch()
    await createLive('', fetchFn).getState()
    expect(fetchFn.mock.calls[0][0]).toBe('/api/state')
  })
})

describe('live: the passphrase of the private page', () => {
  // A stand-in backend whose private side opens with one passphrase.
  function lockedBackend(passphrase = 'goats climb at dawn') {
    return vi.fn(async (url, options) => {
      const secret = url.endsWith('/api/wellness') || url.endsWith('/api/mood')
      if (secret && options?.headers?.['X-Private-Key'] !== passphrase) {
        return { ok: false, status: 401, json: async () => ({ detail: 'locked' }) }
      }
      return { ok: true, status: 200, json: async () => ({ locked: secret, ok: true }) }
    })
  }

  test('a locked page is told apart from a broken one, and the passphrase is kept only if it works', async () => {
    window.localStorage.clear()
    const fetchFn = lockedBackend()
    const live = createLive('http://gary.example', fetchFn)
    live.forgetKey()
    await expect(live.getWellness()).rejects.toMatchObject({ message: 'HTTP 401', locked: true })
    await expect(live.postMood('before', 3)).rejects.toMatchObject({ locked: true })

    await expect(live.unlock('a guess')).rejects.toMatchObject({ locked: true })
    expect(window.localStorage.getItem('gary-private-key')).toBeNull() // a wrong guess is not remembered
    await expect(live.getWellness()).rejects.toMatchObject({ locked: true })

    expect(await live.unlock('goats climb at dawn')).toEqual({ locked: true, ok: true })
    expect(window.localStorage.getItem('gary-private-key')).toBe('goats climb at dawn')
    expect(await live.getWellness()).toEqual({ locked: true, ok: true })
    expect(await live.postMood('after', 4)).toEqual({ locked: true, ok: true })

    // a page loaded later on this device still has it
    expect(await createLive('http://gary.example', fetchFn).getWellness()).toEqual({ locked: true, ok: true })

    live.forgetKey()
    expect(window.localStorage.getItem('gary-private-key')).toBeNull()
    await expect(live.getWellness()).rejects.toMatchObject({ locked: true })
  })

  test("the passphrase goes only to the private side, never with Gary's shared calls", async () => {
    window.localStorage.clear()
    const fetchFn = lockedBackend()
    const live = createLive('http://gary.example', fetchFn)
    await live.unlock('goats climb at dawn')
    fetchFn.mockClear()
    await live.getState()
    await live.chooseQuest('short')
    await live.getWellness()
    const sent = fetchFn.mock.calls.map(([url, options]) => [url.replace('http://gary.example', ''), options?.headers?.['X-Private-Key']])
    expect(sent).toEqual([
      ['/api/state', undefined],
      ['/api/quest/choose', undefined],
      ['/api/wellness', 'goats climb at dawn'],
    ])
    live.forgetKey()
  })

  test('a 401 anywhere else is an ordinary error, not a locked page', async () => {
    const live = createLive('', vi.fn(async () => ({ ok: false, status: 401, json: async () => ({}) })))
    await expect(live.getState()).rejects.toMatchObject({ message: 'HTTP 401', locked: false })
  })
})

describe('the reset for testing', () => {
  test('live: asks the backend to forget the sniffs and keep the quests; an admin key is sent only when given', async () => {
    const seen = []
    const fetchFn = vi.fn(async (url, options) => {
      seen.push({ url, options })
      return { ok: true, status: 200, json: async () => ({ ok: true, quests_kept: true }) }
    })
    const live = createLive('http://x', fetchFn)
    expect(await live.resetGary()).toEqual({ ok: true, quests_kept: true })
    expect(seen[0].url).toBe('http://x/api/dev/reset')
    expect(seen[0].options.method).toBe('POST')
    expect(JSON.parse(seen[0].options.body)).toEqual({ keep_quests: true })
    expect(seen[0].options.headers['X-Admin-Key']).toBeUndefined()
    await live.resetGary('open-sesame')
    expect(seen[1].options.headers['X-Admin-Key']).toBe('open-sesame')
  })

  test('live: a server that wants its admin key says so, and any other failure is an ordinary error', async () => {
    const refuse = (status) => createLive('http://x', async () => ({ ok: false, status, json: async () => ({}) }))
    await expect(refuse(401).resetGary()).rejects.toMatchObject({ needsKey: true })
    await expect(refuse(500).resetGary()).rejects.toMatchObject({ needsKey: false, message: 'HTTP 500' })
  })

  test('mock: starting over goes back to the first step of the story', async () => {
    const mock = createMock({ step: 5 })
    await mock.postMood('before', 4)
    await mock.resetGary()
    expect(mock.story.index).toBe(0)
    expect((await mock.getWellness()).checkins).toEqual(story.steps[0].wellness.checkins)
  })
})

describe('mock: the demo story', () => {
  test('it plays the states the real backend produced, in order', async () => {
    const mock = createMock()
    expect(mock.story.total).toBe(story.steps.length)
    expect(await mock.getState()).toEqual(story.steps[0].state)
    expect(mock.now().toISOString()).toBe('2026-11-21T15:00:00.000Z')
    mock.story.next()
    mock.story.next()
    mock.story.next()
    expect(mock.story.index).toBe(3)
    expect(await mock.getState()).toEqual(story.steps[3].state)
    expect(mock.story.title).toBe(story.steps[3].title)
    mock.story.back()
    expect(mock.story.index).toBe(2)
    for (let i = 0; i < 50; i += 1) mock.story.next()
    expect(mock.story.index).toBe(story.steps.length - 1) // it stops at the end
    mock.story.restart()
    expect(mock.story.index).toBe(0)
    mock.story.back()
    expect(mock.story.index).toBe(0)
    expect(createMock({ step: 5 }).story.index).toBe(5)
    expect(createMock({ step: 999 }).story.index).toBe(story.steps.length - 1)
  })

  test('short or long picks one of the two offered quests, until the story moves on', async () => {
    const mock = createMock()
    const before = await mock.getState()
    expect(before.quest_choice).toBeNull()
    const out = await mock.chooseQuest('long')
    expect(out.quest).toEqual(before.quest_options.long)
    expect(out.state.quest).toEqual(before.quest_options.long)
    expect(out.state.quest_choice).toBe('long')
    expect((await mock.getState()).quest_choice).toBe('long')
    mock.story.next()
    expect(await mock.getState()).toEqual(story.steps[1].state)
  })

  test('a check-in is kept for this visit and the view is marked as demo data', async () => {
    const mock = createMock({ step: 1 })
    expect((await mock.postMood('after', 5)).ok).toBe(true)
    const wellness = await mock.getWellness()
    expect(wellness.demo).toBe(true)
    expect(wellness.private).toBe(true)
    expect(wellness.checkins.at(-1)).toMatchObject({ phase: 'after', value: 5, source: 'web' })
    expect(wellness.summary).toBe(story.steps[1].wellness.summary)
  })
})

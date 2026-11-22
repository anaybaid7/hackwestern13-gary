// Mock mode: no backend, no device. It plays contract/examples/story.json, ten
// states that the real backend produced, one step per press of "Next". So the
// page can be shown, and built, with nothing else running.
//
// Choosing a quest and checking in work here too, in a small way: they change
// what this browser shows and are forgotten on reload.
import story from '../../../contract/examples/story.json'

export function createMock({ step = 0, steps = story.steps } = {}) {
  let index = Math.min(Math.max(0, step), steps.length - 1)
  let patch = null // a quest chosen by hand, until the story moves on
  const moods = [] // check-ins made in this browser

  const current = () => (patch ? { ...steps[index].state, ...patch } : steps[index].state)
  const go = (to) => {
    index = Math.min(Math.max(0, to), steps.length - 1)
    patch = null
  }

  return {
    mode: 'mock',
    now: () => new Date(steps[index].now),
    getState: async () => current(),
    chooseQuest: async (time) => {
      const state = current()
      const quest = state.quest_options?.[time] ?? null
      if (quest) patch = { ...patch, quest, quest_choice: time }
      return { quest, state: current() }
    },
    postVisit: async () => ({ ok: true }), // the story is not anywhere
    // Picks come only from a live TinyFish run, so the story has none to show.
    getPicks: async () => ({ ready: false, demo: true, job: null, picks: [], previous: [] }),
    askPicks: async () => {
      throw new Error('Picks need the live backend and TinyFish')
    },
    takePick: async () => {
      throw new Error('Picks need the live backend and TinyFish')
    },
    postMood: async (phase, value) => {
      moods.push({ ts: steps[index].now, phase, value, source: 'web' })
      return { ok: true }
    },
    getWellness: async () => {
      const wellness = steps[index].wellness
      return { ...wellness, checkins: [...wellness.checkins, ...moods], demo: true }
    },
    // The story has no lock: nothing in it is anyone's own.
    unlock: async () => steps[index].wellness,
    forgetKey: () => {},
    // The demo story's explorers: three made-up walkers circling near you, so the map can be shown moving.
    shareSpot: async ({ lat, lon, quest_id: quest }) => {
      const t = Date.now() / 1000
      const walkers = [
        { tag: '3a9f01c2', r: 0.0022, speed: 0.05, phase: 0.4, same: true },
        { tag: 'b71e44d0', r: 0.0041, speed: -0.03, phase: 2.1, same: false },
        { tag: '5c0d9e17', r: 0.0063, speed: 0.02, phase: 4.0, same: false },
      ]
      return {
        demo: true,
        range_m: 2000,
        nearby: walkers.map((w) => {
          const a = w.phase + t * w.speed
          const dLat = Math.sin(a) * w.r
          const dLon = Math.cos(a) * w.r * 1.36
          return {
            tag: w.tag,
            lat: Math.round((lat + dLat) * 1000) / 1000,
            lon: Math.round((lon + dLon) * 1000) / 1000,
            same_quest: Boolean(quest) && w.same,
            metres: Math.round(Math.hypot(dLat * 111000, dLon * 81000) / 10) * 10,
            seconds_ago: 2,
          }
        }),
      }
    },
    leaveNearby: async () => ({ ok: true }),
    // The demo story has no accounts.
    account: async () => ({ enabled: false, reason: 'demo', signedIn: false }),
    getMe: async () => ({ signed_in: false }),
    // In the story, starting over is going back to its first step.
    resetGary: async () => {
      go(0)
      moods.length = 0
      return { ok: true }
    },
    /** The story's controls. Only the mock service has these. */
    story: {
      get index() {
        return index
      },
      total: steps.length,
      get title() {
        return steps[index].title
      },
      get note() {
        return steps[index].note
      },
      next: () => go(index + 1),
      back: () => go(index - 1),
      restart: () => go(0),
    },
  }
}

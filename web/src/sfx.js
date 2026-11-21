// Gary's sound effects: little retro tones made in the browser with WebAudio,
// so there are no files to load. They play under his voice: a chime for a
// find, a fanfare for a quest, a whoosh when fog lifts, a rising run when he
// grows, a bloop when he names nothing, and a soft tick on buttons.
//
// Browsers start audio only after a tap, so unlockSfx() runs on the first one.

let ctx = null

/** Call from a tap or key press: makes the effects playable from then on. */
export function unlockSfx() {
  const Context = typeof window === 'undefined' ? null : window.AudioContext || window.webkitAudioContext
  if (!Context) return false
  if (!ctx) ctx = new Context()
  if (ctx.state === 'suspended') ctx.resume?.()
  return true
}

/** One note: a square or triangle wave with a quick fade, optionally sliding to `to` Hz. */
function tone(freq, at, length, { type = 'square', volume = 0.06, to = null } = {}) {
  const start = ctx.currentTime + at
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, start)
  if (to) osc.frequency.exponentialRampToValueAtTime(to, start + length)
  gain.gain.setValueAtTime(0.0001, start)
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.01)
  gain.gain.exponentialRampToValueAtTime(0.0001, start + length)
  osc.connect(gain).connect(ctx.destination)
  osc.start(start)
  osc.stop(start + length + 0.02)
}

/** A breath of wind: noise through a band-pass filter that sweeps up. */
function whoosh(at, length, volume = 0.08) {
  const start = ctx.currentTime + at
  const samples = Math.floor(ctx.sampleRate * length)
  const buffer = ctx.createBuffer(1, samples, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < samples; i += 1) data[i] = Math.random() * 2 - 1
  const noise = ctx.createBufferSource()
  noise.buffer = buffer
  const filter = ctx.createBiquadFilter()
  filter.type = 'bandpass'
  filter.frequency.setValueAtTime(300, start)
  filter.frequency.exponentialRampToValueAtTime(2400, start + length)
  const gain = ctx.createGain()
  gain.gain.setValueAtTime(0.0001, start)
  gain.gain.exponentialRampToValueAtTime(volume, start + length * 0.3)
  gain.gain.exponentialRampToValueAtTime(0.0001, start + length)
  noise.connect(filter).connect(gain).connect(ctx.destination)
  noise.start(start)
}

const run = (notes, step, length, options) => notes.forEach((f, i) => tone(f, i * step, length, options))

const EFFECTS = {
  find: () => run([660, 990], 0.08, 0.12),
  again: () => tone(520, 0, 0.1, { type: 'triangle' }),
  quest: () => {
    run([523, 659, 784], 0.09, 0.12)
    tone(1047, 0.27, 0.35)
  },
  herd: () => {
    run([587, 740], 0.07, 0.1)
    run([880, 1175], 0.07, 0.12, { volume: 0.05 })
  },
  miss: () => tone(392, 0, 0.3, { type: 'triangle', to: 196, volume: 0.08 }),
  fog: () => whoosh(0, 0.7),
  grow: () => {
    run([392, 494, 587, 784, 988, 1175], 0.07, 0.1)
    tone(1568, 0.45, 0.4, { type: 'triangle', volume: 0.05 })
  },
  rank: () => {
    run([523, 523, 784], 0.12, 0.1)
    tone(1047, 0.36, 0.3)
  },
  tap: () => tone(1400, 0, 0.03, { volume: 0.02 }),
}

/** The effects a change deserves, in order. `changes` is what whatChanged() gives. */
export function effectsFor(changes) {
  if (!changes) return []
  const out = []
  const find = changes.find
  if (find) out.push(find.quest_id ? (find.friend ? 'herd' : 'quest') : find.new ? 'find' : 'again')
  else if (changes.miss) out.push('miss')
  if (changes.cleared?.length) out.push('fog')
  if (changes.stageUp) out.push('grow')
  if (changes.rankUp) out.push('rank')
  return out
}

/** Play effects one after another, `gap` seconds apart. False when audio is not ready. */
export function playSfx(names, gap = 0.55) {
  if (!ctx || ctx.state !== 'running') return false
  names.forEach((name, i) => {
    if (!EFFECTS[name]) return
    if (i === 0) EFFECTS[name]()
    else setTimeout(() => EFFECTS[name](), i * gap * 1000)
  })
  return names.length > 0
}

export const EFFECT_NAMES = Object.keys(EFFECTS)

// Gary's ears in the browser. "Go Gary" is heard here, offline; only the
// question after it leaves the page, as a short 16 kHz WAV to the backend
// (POST /api/talk).
export const RATE = 16000

const FRAME = 320 // 20 ms

// "Go Gary" is spotted in the page by Vosk (an offline recognizer, in a worker), told to hear only
// these words. With so few words it cannot invent a sentence, and the near misses ("so Gary",
// "hey Gary", "go carry") have words of their own instead of becoming "go gary".
export const GRAMMAR = ['go gary', 'go', 'gary', 'so', 'no', 'oh', 'carry', 'go carry', 'go get', 'okay', 'hey', '[unk]']
const SURE = 0.9 // "oh Gary" comes out as "go" at about 0.8
const QUESTION_SECONDS = 0.5 // speech after "Go Gary" shorter than this is not a question

/**
 * Vosk's words for one thing said ([{word, conf, start, end}], times in seconds)
 * -> null if it is not "Go Gary" at the start, else {question: [start, end] of
 * what was said after it, or null when "Go Gary" was said alone}.
 */
export function wakeIn(words) {
  const list = words ?? []
  for (let i = 0; i < Math.min(2, list.length - 1); i += 1) {
    if (list[i].word === 'go' && list[i].conf >= SURE && list[i + 1].word === 'gary') {
      const rest = list.slice(i + 2)
      const from = list[i + 1].end
      const to = rest.length ? rest[rest.length - 1].end : from
      return { question: to - from >= QUESTION_SECONDS ? [from, to] : null }
    }
  }
  return null
}

/** The last seconds the mic heard, so a question can be cut out of it by Vosk's word times. */
export class Tape {
  constructor(seconds = 20) {
    this.keep = seconds * RATE
    this.frames = []
    this.first = 0 // the sample number of frames[0]
    this.heard = 0 // samples so far: Vosk's clock
  }

  push(frame) {
    this.frames.push(frame)
    this.heard += frame.length
    while ((this.frames.length - 1) * FRAME > this.keep) {
      this.first += this.frames.shift().length
    }
  }

  /** Samples from..to (seconds on Vosk's clock), with room either side: Vosk's word ends run early. */
  cut(from, to, before = 0.2, after = 0.5) {
    const a = Math.max(this.first, Math.floor((from - before) * RATE))
    const b = Math.min(this.heard, Math.ceil((to + after) * RATE))
    const out = new Int16Array(Math.max(0, b - a))
    let at = this.first
    for (const f of this.frames) {
      const lo = Math.max(a, at)
      const hi = Math.min(b, at + f.length)
      if (hi > lo) out.set(f.subarray(lo - at, hi - at), lo - a)
      at += f.length
    }
    return out
  }
}

/** 16 kHz PCM -> a base64 WAV. */
export function wavBase64(pcm, rate = RATE) {
  const bytes = new Uint8Array(44 + pcm.length * 2)
  const view = new DataView(bytes.buffer)
  const text = (at, s) => [...s].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)))
  text(0, 'RIFF')
  view.setUint32(4, 36 + pcm.length * 2, true)
  text(8, 'WAVEfmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, rate, true)
  view.setUint32(28, rate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  text(36, 'data')
  view.setUint32(40, pcm.length * 2, true)
  pcm.forEach((s, i) => view.setInt16(44 + i * 2, s, true))
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(binary)
}

/**
 * Open the microphone and call onFrame with 20 ms Int16Array frames at 16 kHz.
 * Returns a function that closes it. Echo cancellation keeps Gary's own voice out.
 */
export async function openMic(onFrame) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
  })
  const ctx = new (window.AudioContext || window.webkitAudioContext)()
  const source = ctx.createMediaStreamSource(stream)
  // ponytail: ScriptProcessor is deprecated but works in every browser; an AudioWorklet if it ever goes
  const node = ctx.createScriptProcessor(4096, 1, 1)
  const mute = ctx.createGain()
  mute.gain.value = 0
  const step = ctx.sampleRate / RATE
  let pending = []
  let at = 0
  node.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0)
    for (; at < input.length; at += step) pending.push(Math.max(-32768, Math.min(32767, input[Math.floor(at)] * 32768)))
    at -= input.length
    while (pending.length >= FRAME) {
      onFrame(Int16Array.from(pending.slice(0, FRAME)))
      pending = pending.slice(FRAME)
    }
  }
  source.connect(node)
  node.connect(mute)
  mute.connect(ctx.destination)
  return () => {
    node.disconnect()
    stream.getTracks().forEach((t) => t.stop())
    ctx.close()
  }
}

// Gary's ears in the browser: the microphone, cut into the things said.
// The same loudness check as Utterances in device/gary_talk.py, so the page
// and the laptop hear alike. Only a thing said leaves the page, as a short
// 16 kHz WAV to the backend (POST /api/talk), and only while the ears are on.
export const RATE = 16000
const FRAME = 320 // 20 ms

const rms = (frame) => {
  let sum = 0
  for (const s of frame) sum += s * s
  return Math.sqrt(sum / frame.length)
}

/** Feed 20 ms frames (Int16Array); get back each thing said, or null. */
export class Utterances {
  constructor({ startFrames = 4, endSilence = 0.6, preRoll = 0.3, longest = 8, shortest = 0.3, minLevel = 350, ratio = 3 } = {}) {
    Object.assign(this, { startFrames, minLevel, ratio })
    this.endFrames = Math.round((endSilence * 1000) / 20)
    this.pre = Math.round((preRoll * 1000) / 20)
    this.longest = Math.round((longest * 1000) / 20)
    this.shortest = Math.round((shortest * 1000) / 20)
    this.noise = null
    this.reset()
  }

  threshold() {
    return Math.max(this.minLevel, (this.noise ?? 0) * this.ratio)
  }

  feed(frame) {
    const level = rms(frame)
    if (this.speech === null) {
      this.noise = this.noise === null ? level : 0.98 * this.noise + 0.02 * level
      this.history = [...this.history, frame].slice(-this.pre - this.startFrames)
      this.loud = level > this.threshold() ? this.loud + 1 : 0
      if (this.loud >= this.startFrames) {
        this.speech = [...this.history]
        this.quiet = 0
      }
      return null
    }
    this.speech.push(frame)
    this.quiet = level <= this.threshold() ? this.quiet + 1 : 0
    if (this.quiet < this.endFrames && this.speech.length < this.longest) return null
    const said = this.speech
    const quiet = this.quiet
    this.reset()
    if (said.length - quiet < this.shortest) return null // a cough or a bump
    const out = new Int16Array(said.length * FRAME)
    said.forEach((f, i) => out.set(f, i * FRAME))
    return out
  }

  reset() {
    this.speech = null
    this.history = []
    this.loud = 0
    this.quiet = 0
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

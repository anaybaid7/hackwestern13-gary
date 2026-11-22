// Talk to Gary, hands free: say "Go Gary", then ask (or tap the pill instead
// of saying it). The microphone opens on the first tap anywhere (browsers need
// one) and stays on; the small button beside the pill turns it off.
//
// "Go Gary" is heard here, by Vosk, offline, in every browser: nothing leaves
// the page until he is called. Then only the question goes to the backend, cut
// out of the last seconds of sound by the times Vosk gives each word.
import { useEffect, useRef, useState } from 'react'
import { GRAMMAR, RATE, Tape, openMic, wakeIn, wavBase64 } from '../ears.js'
import { VOICE, isPlaying, playAndWait } from '../sound.js'

const MODEL = import.meta.env.VITE_EARS_MODEL || `${import.meta.env.BASE_URL}vosk/model.tar.gz`
const LISTEN_MS = 7000 // how long Gary waits for the question to start
const LONGEST_S = 8 // a question longer than this is cut off (a loud room never goes quiet)
const ECHO_MS = 250 // the room's echo of Gary's last word
const BATCH = 5 // 20 ms frames per message to Vosk's worker
const THINKING = ['say_thinking', 'say_thinking_2', 'say_thinking_3', 'say_thinking_4', 'say_thinking_5'].filter((n) => VOICE[n])
const EARS_KEY = 'gary.ears'

const LABEL = {
  waiting: 'Tap to talk to Gary',
  loading: 'Getting ears…',
  idle: 'Say "Go Gary"',
  listening: 'Listening…',
  thinking: 'Thinking…',
  speaking: 'Gary is talking',
  off: 'Voice off',
  denied: 'Mic blocked',
  broken: 'Voice unavailable',
  quota: 'Gary\'s brain is out of credit',
  insecure: 'Voice needs https',
}

// What the ears hear and do, in the browser's console: "[ears] ..." lines. Only here, never sent.
const log = (...args) => console.log('%c[ears]', 'color:#c94634;font-weight:bold', ...args)
const since = (t0) => `${((performance.now() - t0) / 1000).toFixed(2)} s`

let model = null // loaded once a visit, about 40 MB, then the browser caches it
function loadModel() {
  model ??= import('vosk-browser').then((vosk) => vosk.createModel(MODEL, -1)).catch((err) => {
    model = null
    throw err
  })
  return model
}

function readEars() {
  try {
    return window.localStorage.getItem(EARS_KEY) !== 'off'
  } catch {
    return true
  }
}

function writeEars(on) {
  try {
    window.localStorage.setItem(EARS_KEY, on ? 'on' : 'off')
  } catch {
    // this visit only
  }
}

export default function GaryEars({ service }) {
  const [enabled, setEnabled] = useState(false)
  const [mode, setMode] = useState(readEars() ? 'waiting' : 'off')
  // busy: Gary is thinking or talking. listenUntil: waiting for a question.
  // base: the tape's sample number where the current recognizer's clock starts.
  const talk = useRef({ busy: false, listenUntil: 0, speechAt: 0, history: [], close: null, rec: null, model: null, tape: null, base: 0, batch: [], lastThinking: null })

  useEffect(() => {
    if (!service.talkConfig) return
    service.talkConfig().then((c) => setEnabled(Boolean(c?.enabled)), () => {})
  }, [service])

  const secure = typeof window !== 'undefined' && window.isSecureContext && navigator.mediaDevices?.getUserMedia

  function thinkingClip() {
    const t = talk.current
    if (!THINKING.length) return Promise.resolve()
    const pool = THINKING.filter((n) => n !== t.lastThinking)
    t.lastThinking = pool[Math.floor(Math.random() * pool.length)] ?? THINKING[0]
    setMode('thinking')
    return playAndWait([VOICE[t.lastThinking]])
  }

  /** A fresh recognizer after each turn, so nothing heard before Gary spoke runs into what comes after. */
  function newRecognizer() {
    const t = talk.current
    t.rec?.remove()
    t.rec = null
    if (!t.model || !t.close) return
    const rec = new t.model.KaldiRecognizer(RATE, JSON.stringify(GRAMMAR))
    rec.setWords(true)
    rec.on('partialresult', (m) => onPartial(m.result.partial))
    rec.on('result', (m) => onResult(m.result.result))
    t.rec = rec
    t.base = t.tape.heard
    t.batch = []
    t.speechAt = 0
  }

  /** Say what the backend answered. Called with t.busy set; clears it. */
  async function respond(out, thinking) {
    const t = talk.current
    log('reply:', out ? (out.error ? `error: ${out.error}` : out.busy ? 'server busy' : `"${out.say}"${out.listen ? ' (then listens)' : ''}`) : 'no answer (network?)')
    t.listenUntil = 0
    await thinking
    if (!out?.say) {
      if (VOICE.say_ears) await playAndWait([VOICE.say_ears])
    } else {
      setMode('speaking')
      await playAndWait([`data:audio/wav;base64,${out.audio}`])
      t.history = [...t.history, [out.heard || '(something)', out.say]].slice(-4)
      if (out.listen) t.listenUntil = Date.now() + LISTEN_MS
    }
    await new Promise((r) => setTimeout(r, ECHO_MS))
    newRecognizer()
    t.busy = false
    setMode(/HTTP 429/.test(out?.error ?? '') ? 'quota' : Date.now() < t.listenUntil ? 'listening' : 'idle')
  }

  /** The question, seconds from..to on the recognizer's clock: sent, answered. */
  async function ask(from, to) {
    const t = talk.current
    t.busy = true
    const base = t.base / RATE
    const pcm = t.tape.cut(base + from, base + Math.min(to, from + LONGEST_S))
    const thinking = thinkingClip()
    const t0 = performance.now()
    log(`asking: ${(pcm.length / RATE).toFixed(1)} s of speech`)
    const out = await service.talk({ audio: wavBase64(pcm), history: t.history }).catch((err) => log('request failed:', err.message) ?? null)
    log('answered in', since(t0))
    await respond(out, thinking)
  }

  /** "Go Gary" alone, or a tap on the pill: "Go ahead", then wait for the question. */
  async function goAhead() {
    const t = talk.current
    t.busy = true
    setMode('speaking')
    await playAndWait([VOICE.say_go_ahead].filter(Boolean))
    await new Promise((r) => setTimeout(r, ECHO_MS))
    t.listenUntil = Date.now() + LISTEN_MS
    newRecognizer()
    t.busy = false
    setMode('listening')
  }

  function onPartial(partial) {
    const t = talk.current
    if (t.busy || !partial) return
    if (Date.now() < t.listenUntil) {
      t.speechAt ||= Date.now()
      t.listenUntil = Date.now() + LISTEN_MS // still talking: keep waiting
      if (Date.now() - t.speechAt > LONGEST_S * 1000) t.rec?.retrieveFinalResult()
    } else if (partial.startsWith('go gary')) {
      setMode('listening') // show it while they finish
    }
  }

  function onResult(words) {
    const t = talk.current
    if (t.busy || !words?.length) return
    log('heard:', words.map((w) => `${w.word}(${w.conf.toFixed(2)})`).join(' '))
    if (Date.now() < t.listenUntil) return ask(words[0].start, words[words.length - 1].end)
    const wake = wakeIn(words)
    if (!wake) return setMode((m) => (m === 'listening' ? 'idle' : m))
    log('"Go Gary"', wake.question ? 'with a question' : 'alone')
    if (wake.question) ask(...wake.question)
    else goAhead()
  }

  function onFrame(frame) {
    const t = talk.current
    if (!t.rec || t.busy || isPlaying()) return // never hear Gary's own voice, a find's clip included
    if (t.listenUntil && Date.now() > t.listenUntil && !t.speechAt) {
      t.listenUntil = 0
      setMode('idle')
    }
    t.tape.push(frame)
    t.batch.push(frame)
    if (t.batch.length < BATCH) return
    const samples = new Float32Array(BATCH * frame.length)
    t.batch.forEach((f, i) => samples.set(f, i * f.length))
    t.batch = []
    t.rec.acceptWaveformFloat(samples, RATE)
  }

  async function start() {
    const t = talk.current
    if (t.close) return
    setMode('loading')
    try {
      t.close = await openMic(onFrame)
    } catch (err) {
      log('could not open the microphone:', err?.message ?? err)
      return setMode('denied')
    }
    t.tape = new Tape()
    const t0 = performance.now()
    try {
      t.model = await loadModel()
    } catch (err) {
      log('could not load the "Go Gary" model from', MODEL, err?.message ?? err)
      stop()
      return setMode('broken')
    }
    log('ears ready in', since(t0))
    newRecognizer()
    setMode(t.close ? 'idle' : 'off')
  }

  function stop() {
    const t = talk.current
    t.close?.()
    t.close = null
    t.rec?.remove()
    t.rec = null
    t.listenUntil = 0
  }

  // the first tap anywhere opens the microphone (browsers need a tap), unless voice is off
  useEffect(() => {
    if (!enabled || !secure || mode !== 'waiting') return undefined
    const go = () => start()
    window.addEventListener('pointerdown', go, { once: true })
    return () => window.removeEventListener('pointerdown', go)
  }, [enabled, secure, mode])

  useEffect(() => stop, [])

  if (!enabled) return null
  const shown = secure ? mode : 'insecure'
  const on = !['off', 'denied', 'broken', 'insecure', 'waiting'].includes(shown)
  const tap = () => {
    if (shown === 'idle' || shown === 'quota') goAhead()
    else if (shown === 'off' || shown === 'denied' || shown === 'broken') power()
  }
  const power = () => {
    if (on) {
      writeEars(false)
      stop()
      setMode('off')
    } else {
      writeEars(true)
      start()
    }
  }
  return (
    <span className="ears-wrap">
      <button type="button" className={`ears ears-${shown}`} onClick={tap} aria-live="polite"
        title={shown === 'insecure' ? 'Browsers only allow the microphone on https or localhost' : shown === 'idle' ? 'Tap instead of saying "Go Gary"' : ''}>
        <span className="ears-dot" aria-hidden="true" />
        {LABEL[shown]}
      </button>
      {on && (
        <button type="button" className="ears-power" onClick={power} aria-label="Turn voice off" title="Turn voice off">×</button>
      )}
    </span>
  )
}

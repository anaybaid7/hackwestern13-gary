// Talk to Gary, hands free: say "Go Gary", then ask. The microphone opens on
// the first tap anywhere (browsers need one) and stays on; tap the pill to
// turn it off.
//
// Two ways to hear. Where the browser has speech recognition (Chrome, Safari),
// it writes down what is said as it is said, so "Go Gary" is spotted here at
// once and only the question goes to the backend, as text. Elsewhere the page
// cuts the mic into things said and the backend checks each for "Go Gary".
import { useEffect, useRef, useState } from 'react'
import { Utterances, openMic, wakeSplit, wavBase64 } from '../ears.js'
import { VOICE, isPlaying, playAndWait } from '../sound.js'

const LISTEN_MS = 7000 // how long Gary waits for the question after "Go ahead"
const ECHO_MS = 250 // the room's echo of Gary's last word
const CHECKS = 3 // "Go Gary" checks at once, as on the laptop (gary_talk.py)
const THINKING = ['say_thinking', 'say_thinking_2', 'say_thinking_3', 'say_thinking_4', 'say_thinking_5'].filter((n) => VOICE[n])
const EARS_KEY = 'gary.ears'

const LABEL = {
  idle: 'Say "Go Gary"',
  listening: 'Listening…',
  thinking: 'Thinking…',
  speaking: 'Gary is talking',
  off: 'Voice off',
  waiting: 'Tap to talk to Gary',
  denied: 'Mic blocked',
  insecure: 'Voice needs https',
}

// What the ears hear and do, in the browser's console: "[ears] ..." lines. Only here, never sent.
const log = (...args) => console.log('%c[ears]', 'color:#c94634;font-weight:bold', ...args)
const since = (t0) => `${((performance.now() - t0) / 1000).toFixed(2)} s`

const Recognition = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

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
  const talk = useRef({ busy: false, checks: 0, listenUntil: 0, history: [], close: null, rec: null, lastThinking: null })

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

  /** Say what the backend answered. Called with t.busy set; clears it. */
  async function respond(out, thinking, asked) {
    const t = talk.current
    log('reply:', out ? (out.error ? `error: ${out.error}` : out.busy ? 'server busy' : out.say ? `"${out.say}"${out.listen ? ' (then listens)' : ''}` : '"Go ahead"') : 'no answer (network?)')
    t.rec?.abort() // the recognizer must not hear Gary
    t.listenUntil = 0
    if (!out || out.busy || out.error) {
      if (asked && VOICE.say_ears) await thinking.then(() => playAndWait([VOICE.say_ears]))
    } else if (!out.say) {
      setMode('speaking')
      await playAndWait([VOICE.say_go_ahead].filter(Boolean))
      t.listenUntil = Date.now() + LISTEN_MS
    } else {
      await thinking
      setMode('speaking')
      await playAndWait([`data:audio/wav;base64,${out.audio}`])
      t.history = [...t.history, [out.heard || '(something)', out.say]].slice(-4)
      if (out.listen) t.listenUntil = Date.now() + LISTEN_MS
    }
    await new Promise((r) => setTimeout(r, ECHO_MS))
    t.busy = false
    setMode(Date.now() < t.listenUntil ? 'listening' : 'idle')
    resume()
  }

  /** A question, written down by the browser: answered straight away. */
  async function ask(text) {
    const t = talk.current
    t.busy = true
    t.rec?.abort()
    const thinking = thinkingClip()
    const t0 = performance.now()
    log('asking, as text:', `"${text}"`)
    const out = await service.talk({ text, history: t.history }).catch((err) => log('request failed:', err.message) ?? null)
    log('answered in', since(t0))
    await respond(out, thinking, true)
  }

  /** "Go Gary" alone, spotted by the browser: no round trip before "Go ahead". */
  function goAhead() {
    log('"Go Gary" spotted in the browser: "Go ahead"')
    talk.current.busy = true
    respond({ woke: true, say: '' }, Promise.resolve(), false)
  }

  // Checking for "Go Gary" takes Gemini a second or two, and in a loud room most of what the mic
  // catches is other people. So checks run side by side, and the ears stay open while they do:
  // a neighbour's sentence being checked must never make Gary deaf to yours.
  async function hear(pcm) {
    const t = talk.current
    const listening = Date.now() < t.listenUntil
    const secs = (pcm.length / 16000).toFixed(1)
    if (!listening && t.checks >= CHECKS) return log(`dropped ${secs} s of speech: ${CHECKS} checks already running`)
    log(listening ? `question: ${secs} s of speech, sending` : `${secs} s of speech, checking for "Go Gary" (${t.checks + 1} running)`)
    const t0 = performance.now()
    if (listening) t.busy = true // the question itself: answer it, deaf until Gary is done
    else t.checks += 1
    const thinking = listening ? thinkingClip() : Promise.resolve()
    const out = await service.talk({ audio: wavBase64(pcm), listening, history: t.history }).catch(() => null)
    log(`  ${listening ? 'answered' : 'checked'} in ${since(t0)}:`, out?.woke ? `woke, heard "${out.heard ?? ''}"` : out?.error ?? (out?.busy ? 'server busy' : 'not "Go Gary"'))
    if (!listening) {
      t.checks -= 1
      if (!out?.woke || t.busy) return // not "Go Gary", or Gary is already busy with someone
      t.busy = true
    }
    await respond(out, thinking, listening)
  }

  function onResult(event) {
    const t = talk.current
    if (t.busy) return log('(ignored: Gary is busy)')
    const result = event.results[event.results.length - 1]
    const said = result[0].transcript.trim()
    if (!said) return
    log(result.isFinal ? 'heard (final):' : 'hearing…', `"${said}"`, result.isFinal ? `confidence ${result[0].confidence?.toFixed(2) ?? '?'}` : '')
    if (Date.now() < t.listenUntil) {
      if (result.isFinal) ask(said)
      else t.listenUntil = Date.now() + LISTEN_MS // still talking: keep waiting
      return
    }
    const [woke, rest] = wakeSplit(said)
    if (!woke) return
    if (!result.isFinal) return setMode('listening') // heard "Go Gary": show it while they finish
    if (rest.split(' ').filter(Boolean).length >= 2) ask(rest)
    else goAhead()
  }

  function resume() {
    const t = talk.current
    if (!t.rec || t.busy) return
    try {
      t.rec.start()
    } catch {
      // already running
    }
  }

  async function startMic() {
    const t = talk.current
    const ears = new Utterances()
    let frames = 0
    try {
      t.close = await openMic((frame) => {
        if (++frames % 250 === 0) log(`mic: room noise ${Math.round(ears.noise ?? 0)}, speech starts above ${Math.round(ears.threshold())}`) // every 5 s
        if (t.busy || isPlaying()) return ears.reset() // never answer Gary's own voice, a find's clip included
        if (t.listenUntil && Date.now() > t.listenUntil) {
          t.listenUntil = 0
          setMode('idle')
        }
        const said = ears.feed(frame)
        if (said) hear(said)
      })
      log('listening with the page\'s own ears (mic + loudness check). Every thing said goes to the backend to check for "Go Gary"')
      setMode('idle')
    } catch (err) {
      log('could not open the microphone:', err?.message ?? err)
      setMode('denied')
    }
  }

  function start() {
    const t = talk.current
    if (t.close || t.rec) return
    if (!Recognition) return startMic()
    const rec = new Recognition()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = 'en-CA'
    rec.onresult = onResult
    rec.onend = () => {
      log('recognizer stopped', talk.current.busy ? '(Gary is talking)' : '- starting it again')
      if (talk.current.rec === rec) resume() // it stops on its own after a while
    }
    rec.onstart = () => log('recognizer listening')
    rec.onerror = (event) => {
      log('recognizer error:', event.error)
      if (event.error !== 'not-allowed' && event.error !== 'service-not-allowed') return
      t.rec = null // no recognizer here after all: the page's own ears instead
      startMic()
    }
    t.rec = rec
    log('using the browser\'s speech recognition: "Go Gary" is spotted here, only questions are sent')
    resume()
    setMode('idle')
  }

  function stop() {
    const t = talk.current
    t.close?.()
    t.close = null
    const rec = t.rec
    t.rec = null
    rec?.abort()
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

  // the pill goes back to "Say Go Gary" once the wait for a question is over
  useEffect(() => {
    if (mode !== 'listening') return undefined
    const timer = setInterval(() => {
      const t = talk.current
      if (!t.busy && Date.now() >= t.listenUntil + 1500) setMode('idle')
    }, 500)
    return () => clearInterval(timer)
  }, [mode])

  if (!enabled) return null
  const shown = secure ? mode : 'insecure'
  const toggle = () => {
    if (!secure || mode === 'waiting') return // the tap itself opens the microphone
    if (mode === 'off' || mode === 'denied') {
      writeEars(true)
      start()
    } else {
      writeEars(false)
      stop()
      setMode('off')
    }
  }
  return (
    <button type="button" className={`ears ears-${shown}`} onClick={toggle} aria-live="polite"
      title={shown === 'insecure' ? 'Browsers only allow the microphone on https or localhost' : 'Tap to turn voice on or off'}>
      <span className="ears-dot" aria-hidden="true" />
      {LABEL[shown]}
    </button>
  )
}

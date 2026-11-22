// Talk to Gary, hands free: say "Go Gary", then ask. The microphone opens on
// the first tap anywhere (browsers need one) and stays on; tap the pill to
// turn it off. Only things said are sent, and only to this page's backend.
import { useEffect, useRef, useState } from 'react'
import { Utterances, openMic, wavBase64 } from '../ears.js'
import { VOICE, isPlaying, playAndWait } from '../sound.js'

const LISTEN_MS = 7000 // how long Gary waits for the question after "Go ahead"
const ECHO_MS = 250 // the room's echo of Gary's last word
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
  const talk = useRef({ busy: false, listenUntil: 0, history: [], close: null, lastThinking: null })

  useEffect(() => {
    if (!service.talkConfig) return
    service.talkConfig().then((c) => setEnabled(Boolean(c?.enabled)), () => {})
  }, [service])

  const secure = typeof window !== 'undefined' && window.isSecureContext && navigator.mediaDevices?.getUserMedia

  async function hear(pcm) {
    const t = talk.current
    const listening = Date.now() < t.listenUntil
    t.busy = true
    let thinking = Promise.resolve()
    if (listening && THINKING.length) {
      const pool = THINKING.filter((n) => n !== t.lastThinking)
      t.lastThinking = pool[Math.floor(Math.random() * pool.length)] ?? THINKING[0]
      setMode('thinking')
      thinking = playAndWait([VOICE[t.lastThinking]])
    }
    try {
      const out = await service.talk({ audio: wavBase64(pcm), listening, history: t.history })
      t.listenUntil = 0
      if (!out || out.busy || out.error) {
        if (listening && VOICE.say_ears) await thinking.then(() => playAndWait([VOICE.say_ears]))
      } else if (out.woke && !out.say) {
        setMode('speaking')
        await playAndWait([VOICE.say_go_ahead].filter(Boolean))
        t.listenUntil = Date.now() + LISTEN_MS
      } else if (out.woke) {
        await thinking
        setMode('speaking')
        await playAndWait([`data:audio/wav;base64,${out.audio}`])
        t.history = [...t.history, [out.heard || '(something)', out.say]].slice(-4)
        if (out.listen) t.listenUntil = Date.now() + LISTEN_MS
      }
    } catch {
      t.listenUntil = 0
    }
    await new Promise((r) => setTimeout(r, ECHO_MS))
    t.busy = false
    setMode(Date.now() < t.listenUntil ? 'listening' : 'idle')
  }

  async function start() {
    const t = talk.current
    if (t.close) return
    const ears = new Utterances()
    try {
      t.close = await openMic((frame) => {
        if (t.busy || isPlaying()) return ears.reset() // never answer Gary's own voice, a find's clip included
        if (t.listenUntil && Date.now() > t.listenUntil) {
          t.listenUntil = 0
          setMode('idle')
        }
        const said = ears.feed(frame)
        if (said) hear(said)
      })
      setMode('idle')
    } catch {
      setMode('denied')
    }
  }

  function stop() {
    const t = talk.current
    t.close?.()
    t.close = null
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

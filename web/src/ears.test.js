import { describe, expect, it } from 'vitest'
import { Tape, wakeIn, wavBase64 } from './ears.js'

// Vosk's words, as it heard Mac voices say these with GRAMMAR (see ears.js)
const w = (word, conf, start, end) => ({ word, conf, start, end })
const HEARD = {
  'Go Gary': [w('go', 1, 0.3, 0.5), w('gary', 1, 0.5, 0.9)],
  "Go Gary, what's that?": [w('go', 1, 0.3, 0.5), w('gary', 1, 0.5, 0.9), w('[unk]', 1, 1.1, 1.9)],
  'oh Gary': [w('go', 0.79, 0.3, 0.5), w('gary', 1, 0.5, 0.9)],
  'so Gary said': [w('so', 1, 0.3, 0.5), w('gary', 1, 0.5, 0.9), w('so', 1, 0.9, 1.2)],
  'hey Gary can you give me a task': [w('hey', 0.9, 0.2, 0.4), w('gary', 0.9, 0.4, 0.8), w('[unk]', 0.84, 0.9, 2.4)],
  'go carry': [w('go', 1, 0.3, 0.5), w('carry', 0.76, 0.5, 0.9)],
  'I think we should go get lunch with Gary later': [w('[unk]', 1, 0.2, 1.0), w('go', 1, 1.0, 1.2), w('get', 1, 1.2, 1.4), w('[unk]', 1, 1.4, 3)],
  'hey go Gary': [w('hey', 1, 0.2, 0.4), w('go', 1, 0.4, 0.6), w('gary', 1, 0.6, 1.0)],
}

describe('the wake word', () => {
  it('wakes on "Go Gary" at the start, and finds the question after it', () => {
    expect(wakeIn(HEARD['Go Gary'])).toEqual({ question: null })
    expect(wakeIn(HEARD['hey go Gary'])).toEqual({ question: null })
    expect(wakeIn(HEARD["Go Gary, what's that?"]).question).toEqual([0.9, 1.9])
  })

  it('never wakes on near misses or on talk about Gary', () => {
    for (const said of ['oh Gary', 'so Gary said', 'hey Gary can you give me a task', 'go carry', 'I think we should go get lunch with Gary later']) {
      expect(wakeIn(HEARD[said]), said).toBeNull()
    }
    expect(wakeIn([])).toBeNull()
    expect(wakeIn(undefined)).toBeNull()
  })
})

describe('the tape', () => {
  const frame = (n) => new Int16Array(320).fill(n)

  it('cuts out the seconds asked for, with room either side', () => {
    const tape = new Tape()
    for (let i = 0; i < 100; i += 1) tape.push(frame(i)) // 2 s, frame i holds i
    const cut = tape.cut(1, 1.5, 0, 0)
    expect(cut.length).toBe(8000)
    expect(cut[0]).toBe(50)
    expect(cut[cut.length - 1]).toBe(74)
    expect(tape.cut(1.9, 2.5).length).toBe(0.3 * 16000) // never past what was heard
  })

  it('keeps only the last seconds', () => {
    const tape = new Tape(1)
    for (let i = 0; i < 150; i += 1) tape.push(frame(i)) // 3 s
    expect(tape.cut(0, 3, 0, 0).length).toBeLessThanOrEqual(16000 + 320)
    expect(tape.cut(2.5, 3, 0, 0)[0]).toBe(125)
  })
})

describe('the wav', () => {
  it('writes a 16 kHz mono WAV', () => {
    const raw = atob(wavBase64(new Int16Array([1, -1])))
    expect(raw.slice(0, 4)).toBe('RIFF')
    expect(raw.length).toBe(48)
    expect(raw.charCodeAt(24) + raw.charCodeAt(25) * 256).toBe(16000)
  })
})

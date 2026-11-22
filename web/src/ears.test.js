import { describe, expect, it } from 'vitest'
import { Utterances, wakeSplit, wavBase64 } from './ears.js'

const frame = (level) => new Int16Array(320).fill(level)

describe('ears', () => {
  it('cuts speech out of quiet', () => {
    const ears = new Utterances()
    const feed = (level, n) => Array.from({ length: n }, () => ears.feed(frame(level))).filter(Boolean)
    expect(feed(50, 50)).toEqual([])
    const said = feed(3000, 40).concat(feed(50, 40))
    expect(said).toHaveLength(1)
    expect(said[0].length).toBeGreaterThan(40 * 320)
  })

  it('writes a 16 kHz mono WAV', () => {
    const raw = atob(wavBase64(new Int16Array([1, -1])))
    expect(raw.slice(0, 4)).toBe('RIFF')
    expect(raw.length).toBe(48)
    expect(raw.charCodeAt(24) + raw.charCodeAt(25) * 256).toBe(16000)
  })
})

describe('the wake word', () => {
  it('wakes on "Go Gary" at the start, never on talk about Gary', () => {
    expect(wakeSplit('Go Gary, what is that?')).toEqual([true, 'what is that'])
    expect(wakeSplit('uh hey Garry')).toEqual([true, ''])
    expect(wakeSplit('Gary is a good name')).toEqual([false, ''])
    expect(wakeSplit('I told him to go gary')).toEqual([false, ''])
  })
})

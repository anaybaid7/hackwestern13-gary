// Gary's sounds, played by the page. The Pi has only a buzzer unless a USB
// speaker is plugged in, and the page is on a screen with speakers anyway.
// The clips are the device's own (device/sounds), so both sound the same:
// Gary's spoken ElevenLabs lines when they exist, the chimes otherwise.
import again from '../../device/sounds/again.wav'
import herd from '../../device/sounds/herd.wav'
import hello from '../../device/sounds/hello.wav'
import fresh from '../../device/sounds/new.wav'
import quest from '../../device/sounds/quest.wav'

export const CLIPS = { again, herd, hello, new: fresh, quest }

// Gary's spoken clips (ElevenLabs, device/make_voice.py): {say_bottle: url, ...}.
export const VOICE = Object.fromEntries(
  Object.entries(import.meta.glob('../../device/sounds/say_*.wav', { eager: true, query: '?url', import: 'default' })).map(
    ([path, url]) => [path.split('/').pop().replace('.wav', ''), url],
  ),
)

const SOUND_KEY = 'gary.sound'

export function readSound() {
  try {
    return window.localStorage.getItem(SOUND_KEY) !== 'no'
  } catch {
    return true
  }
}

export function writeSound(on) {
  try {
    window.localStorage.setItem(SOUND_KEY, on ? 'yes' : 'no')
  } catch {
    // no storage: the choice lasts for this visit only
  }
}

/**
 * Which clip a change deserves, or null. `changes` is what whatChanged() gives.
 * A sniff that found nothing never reaches the page, so it has no sound here.
 */
export function pickClip(changes) {
  const find = changes?.find
  if (!find) return null
  if (find.quest_id) return find.friend ? 'herd' : 'quest'
  return find.new ? 'new' : 'again'
}

/**
 * What Gary says aloud for a change, as clip names, or null when a clip is
 * missing (then the chime plays). The same rule as voice_clips() on the device
 * (gary_qnx.cpp, gary_device.py). `prev` and `next` are the states either side.
 */
export function voiceFor(changes, prev, next) {
  const find = changes?.find
  if (!find) return null
  const name = find.label.replace(/ /g, '_')
  const clips = []
  if (find.quest_id) clips.push(`say_found_${name}`)
  else if (prev?.quest?.target === find.label && prev.quest.herd && !find.friend) clips.push(`say_${name}`, 'say_need_friend')
  else if ((prev?.quests_open ?? 0) > 0) clips.push('say_not_it', `say_${name}`)
  else clips.push(`say_${name}`, ...(find.new ? ['say_new'] : []))
  if (find.friend) clips.push('say_herd')
  if (find.quest_id && next?.quests_open === 0) clips.push('say_done')
  return clips.every((clip) => VOICE[clip]) ? clips : null
}

/** Play spoken clips one after another. Like playClip, never an error. */
export function playVoice(names) {
  const urls = names.map((name) => VOICE[name]).filter(Boolean)
  if (urls.length === 0 || typeof Audio === 'undefined') return false
  let i = 0
  const next = () => {
    if (i >= urls.length) return
    try {
      const audio = new Audio(urls[i++])
      audio.addEventListener?.('ended', next)
      const playing = audio.play()
      if (playing && playing.catch) playing.catch(() => {})
    } catch {
      // sound is never an error
    }
  }
  next()
  return true
}

/**
 * Play one clip. Browsers stay silent until the page has been tapped once;
 * that refusal, and a missing Audio, are swallowed: sound is never an error.
 */
export function playClip(name) {
  const url = CLIPS[name]
  if (!url || typeof Audio === 'undefined') return false
  try {
    const playing = new Audio(url).play()
    if (playing && playing.catch) playing.catch(() => {})
    return true
  } catch {
    return false
  }
}

// Gary's sounds, played by the page. The Pi has only a buzzer unless a USB
// speaker is plugged in, and the page is on a screen with speakers anyway.
// The clips are the device's own (device/sounds), so both sound the same:
// Gary's spoken ElevenLabs lines when they exist, the chimes otherwise.
import again from '../../device/sounds/again.wav'
import herd from '../../device/sounds/herd.wav'
import hello from '../../device/sounds/hello.wav'
import nothing from '../../device/sounds/nothing.wav'
import fresh from '../../device/sounds/new.wav'
import quest from '../../device/sounds/quest.wav'

export const CLIPS = { again, herd, hello, new: fresh, quest, nothing }

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
 * A sniff that found nothing (state.last_miss changed) gets the "nothing" sound.
 */
export function pickClip(changes) {
  const find = changes?.find
  if (!find) return changes?.miss ? 'nothing' : null
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
  if (!find) return changes?.miss && VOICE.say_nothing ? ['say_nothing'] : null
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

// One audio player for every clip. Safari plays sound only from a player that
// was started by a tap, so the first tap anywhere on the page starts this one
// (unlockSound), and every clip after that reuses it.
let player = null
const SILENT = 'data:audio/wav;base64,UklGRrQBAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YZABAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA' // 50 ms of silence

function shared() {
  if (typeof Audio === 'undefined') return null
  if (!(player instanceof Audio)) player = new Audio()
  return player
}

function start(audio) {
  try {
    const playing = audio.play()
    if (playing && playing.catch) playing.catch(() => {})
    return true
  } catch {
    return false // sound is never an error
  }
}

/** Call from a tap or key press: lets the page play Gary's clips from then on. */
export function unlockSound() {
  const audio = shared()
  if (!audio || audio.unlocked) return
  audio.unlocked = true
  audio.src = SILENT
  start(audio)
}

// Gary's clips were made a little slow. The browser speeds them up, keeping
// his pitch. Back to 1 once the clips are made again (make_voice.py --force).
export const VOICE_RATE = 1.15

/** Play clips (urls) one after another on the shared player. */
function playUrls(urls, rate = 1) {
  const audio = shared()
  if (!audio || urls.length === 0) return false
  let i = 0
  const play = () => {
    audio.src = urls[i++]
    audio.playbackRate = rate // set after src: a new source resets it
    audio.preservesPitch = true
    return start(audio)
  }
  audio.onended = () => i < urls.length && play()
  return play()
}

/** Play spoken clips one after another. Like playClip, never an error. */
export function playVoice(names) {
  return playUrls(names.map((name) => VOICE[name]).filter(Boolean), VOICE_RATE)
}

/**
 * Play one clip. Browsers stay silent until the page has been tapped once;
 * that refusal, and a missing Audio, are swallowed: sound is never an error.
 */
export function playClip(name) {
  const url = CLIPS[name]
  return url ? playUrls([url]) : false
}

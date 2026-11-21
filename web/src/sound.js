// Gary's sounds, played by the page. The Pi has only a buzzer unless a USB
// speaker is plugged in, and the page is on a screen with speakers anyway.
// The clips are the device's own (device/sounds), so both sound the same.
import again from '../../device/sounds/again.wav'
import herd from '../../device/sounds/herd.wav'
import hello from '../../device/sounds/hello.wav'
import fresh from '../../device/sounds/new.wav'
import quest from '../../device/sounds/quest.wav'

export const CLIPS = { again, herd, hello, new: fresh, quest }

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

// The 90 things Gary can recognise, each with a small picture for the field
// guide. The list itself comes from contract/labels.json; this file only adds
// how to draw each one. A thing with no picture here gets its initials.
import labels from '../../contract/labels.json'

export const THINGS = labels.labels // [{name, outdoor}]
export const OUTDOOR = THINGS.filter((thing) => thing.outdoor)
export const INDOOR = THINGS.filter((thing) => !thing.outdoor)

// Emoji, where one fits. "svg:" names a drawing in components/ThingIcon.jsx.
const PICTURES = {
  bicycle: '🚲', car: '🚗', motorcycle: '🏍️', airplane: '✈️', bus: '🚌', train: '🚆', truck: '🚚',
  boat: '⛵', 'traffic light': '🚦', 'fire hydrant': 'svg:hydrant', 'stop sign': '🛑',
  'parking meter': 'svg:meter', bench: 'svg:bench', bird: '🐦', dog: '🐕', horse: '🐎', sheep: '🐑',
  cow: '🐄', elephant: '🐘', bear: '🐻', zebra: '🦓', giraffe: '🦒', umbrella: '☂️', frisbee: '🥏',
  skis: '🎿', snowboard: '🏂', 'sports ball': '⚽', kite: '🪁', 'baseball bat': '🏏',
  'baseball glove': '🧤', skateboard: '🛹', surfboard: '🏄', 'tennis racket': '🎾',
  cat: '🐈', backpack: '🎒', handbag: '👜', tie: '👔', suitcase: '🧳', bottle: '🧴', 'wine glass': '🍷',
  cup: '☕', fork: '🍴', knife: '🔪', spoon: '🥄', bowl: '🥣', banana: '🍌', apple: '🍎',
  sandwich: '🥪', orange: '🍊', broccoli: '🥦', carrot: '🥕', 'hot dog': '🌭', pizza: '🍕',
  donut: '🍩', cake: '🍰', chair: '🪑', couch: '🛋️', 'potted plant': '🪴', bed: '🛏️',
  'dining table': '🍽️', toilet: '🚽', tv: '📺', laptop: '💻', mouse: '🖱️', keyboard: '⌨️',
  'cell phone': '📱', toaster: '🍞', sink: '🚰', refrigerator: '🧊', book: '📖', clock: '🕰️',
  vase: '🏺', scissors: '✂️', 'teddy bear': '🧸', toothbrush: '🪥',
  tree: '🌳', flower: '🌸', 'trash can': '🗑️', 'street lamp': '💡', squirrel: '🐿️', duck: '🦆', goose: '🪿',
  rabbit: '🐇', deer: '🦌', butterfly: '🦋', mushroom: '🍄',
}

/** -> {kind: 'emoji' | 'svg' | 'letters', value} */
export function pictureFor(name) {
  const picture = PICTURES[name]
  if (!picture) {
    const words = String(name).split(' ')
    const letters = words.length > 1 ? words[0][0] + words[1][0] : String(name).slice(0, 2)
    return { kind: 'letters', value: letters.toUpperCase() }
  }
  if (picture.startsWith('svg:')) return { kind: 'svg', value: picture.slice(4) }
  return { kind: 'emoji', value: picture }
}

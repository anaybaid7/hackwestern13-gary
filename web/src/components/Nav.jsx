// The five screens, as the bar at the bottom of Gary's screen.
import { runs } from '../pixel.js'

export const SCREENS = [
  { id: 'home', name: 'Home' },
  { id: 'map', name: 'Map' },
  { id: 'journal', name: 'Journal' },
  { id: 'cup', name: 'Cup' },
  { id: 'settings', name: 'Settings' },
]

// 9 x 9 icons; 'x' is drawn in the button's text colour.
const ICONS = {
  home: ['....x....', '...xxx...', '..xxxxx..', '.xxxxxxx.', 'xxxxxxxxx', '.xx...xx.', '.xx.x.xx.', '.xx.x.xx.', '.xxxxxxx.'],
  map: ['xx...xx..', 'x.xx.x.xx', 'x..x.x..x', 'x..x.x..x', 'x..x.x..x', 'x..x.x..x', 'x..x.x..x', 'xx.x.xx.x', '..xx...xx'],
  journal: ['xxxxxxxx.', 'x.....xx.', 'x.xxx.xx.', 'x.....xx.', 'x.xxx.xx.', 'x.....xx.', 'x.xx..xx.', 'x.....xx.', 'xxxxxxxx.'],
  cup: ['xxxxxxxxx', 'x.xxxxx.x', 'x.xxxxx.x', '.xxxxxxx.', '..xxxxx..', '...xxx...', '....x....', '...xxx...', '.xxxxxxx.'],
  settings: ['...x.x...', '.x.xxx.x.', '..xxxxx..', 'xxx...xxx', '.xx...xx.', 'xxx...xxx', '..xxxxx..', '.x.xxx.x.', '...x.x...'],
}

export function PixelIcon({ name }) {
  const rows = ICONS[name]
  if (!rows) return null
  return (
    <svg className="pixel-icon" viewBox="0 0 9 9" shapeRendering="crispEdges" aria-hidden="true">
      {runs(rows, { x: 'currentColor' }).map((r) => (
        <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width={r.w} height="1" fill={r.fill} />
      ))}
    </svg>
  )
}

export default function Nav({ tab, onPick, dots = {} }) {
  return (
    <nav className="nav" aria-label="Screens">
      {SCREENS.map(({ id, name }) => (
        <button
          key={id}
          type="button"
          className={`nav-button nav-${id}`}
          aria-current={tab === id ? 'page' : undefined}
          onClick={() => onPick(id)}
        >
          <PixelIcon name={id} />
          <span className="nav-name">{name}</span>
          {dots[id] && <span className="nav-dot" aria-label="something new" />}
        </button>
      ))}
    </nav>
  )
}

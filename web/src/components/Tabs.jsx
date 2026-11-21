// The five screens. On a phone this is the bar at the bottom; on a wide
// screen Gary stays on the left and these pick what sits beside him.
export const TABS = [
  { id: 'gary', name: 'Gary' },
  { id: 'map', name: 'Map' },
  { id: 'guide', name: 'Field guide' },
  { id: 'herd', name: 'Herd' },
  { id: 'you', name: 'You' },
]

export default function Tabs({ tab, side, onPick, dots = {} }) {
  return (
    <nav className="tabs" aria-label="Screens">
      {TABS.map(({ id, name }) => (
        <button
          key={id}
          type="button"
          className={`tab tab-${id}${side === id ? ' beside' : ''}`}
          aria-current={tab === id ? 'page' : undefined}
          onClick={() => onPick(id)}
        >
          {name}
          {dots[id] && <span className="tab-dot" aria-label="something new" />}
        </button>
      ))}
    </nav>
  )
}

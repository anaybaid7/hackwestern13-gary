// Mock mode only: the controls for the demo story.
export default function StoryBar({ story, onMove }) {
  const first = story.index === 0
  const last = story.index === story.total - 1
  return (
    <aside className="storybar" aria-label="Demo story">
      <div className="storybar-text">
        <p className="storybar-title">
          Demo story, step {story.index + 1} of {story.total}: {story.title}
        </p>
        <p className="storybar-note">{story.note}</p>
      </div>
      <div className="storybar-buttons">
        <button type="button" disabled={first} onClick={() => onMove(() => story.back())}>
          Back
        </button>
        <button type="button" className="primary" onClick={() => onMove(() => (last ? story.restart() : story.next()))}>
          {last ? 'Start again' : 'Next'}
        </button>
      </div>
    </aside>
  )
}

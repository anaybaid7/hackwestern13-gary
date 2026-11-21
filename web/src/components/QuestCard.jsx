// The quest on the card, drawn as a trail sign, with the short or long
// choice under it (issue #28).
import { host, plural, webAddress } from '../format.js'

export default function QuestCard({ quest, choice, options = {}, open = 0, onChoose, busy = false }) {
  return (
    <section className="quest" aria-labelledby="quest-title">
      {quest ? (
        <>
          <div className={`sign${quest.herd ? ' sign-herd' : ''}`}>
            <p className="sign-top">{choice ? `Your ${choice} quest` : "Today's quest"}</p>
            <h3 id="quest-title">{quest.title}</h3>
            <p className="sign-facts">
              At {quest.place}. Sniff {aThing(quest.target)}
              {quest.minutes ? `, about ${quest.minutes} minutes` : ''}. Worth {quest.xp} XP.
            </p>
            {quest.herd && <p className="sign-herd-note">Needs a friend in the frame.</p>}
            {quest.note && <p className="sign-note">{quest.note}</p>}
          </div>
          <p className="source">
            {quest.source === 'tinyfish' && webAddress(quest.source_url) ? (
              <>
                Found by the scout on <a href={quest.source_url}>{host(quest.source_url)}</a>.
              </>
            ) : quest.source === 'tinyfish' ? (
              'Found by the scout.'
            ) : quest.source === 'sample' ? (
              'A sample quest, written by hand. The scout did not find this one.'
            ) : (
              'A starter quest. The scout did not find this one.'
            )}
          </p>
        </>
      ) : (
        <div className="sign sign-done">
          <h3 id="quest-title">Every quest is done</h3>
          <p className="sign-facts">The scout brings more tomorrow. Gary will sniff anything in the meantime.</p>
        </div>
      )}

      <div className="choice" role="group" aria-label="Pick a quest by how long you have">
        {['short', 'long'].map((time) => (
          <button
            key={time}
            type="button"
            className="choice-button"
            aria-pressed={choice === time}
            disabled={busy || !options?.[time]}
            onClick={() => onChoose?.(time)}
          >
            <span className="choice-name">{time === 'short' ? 'Short' : 'Long'}</span>
            <span className="choice-detail">
              {options?.[time] ? `about ${options[time].minutes ?? (time === 'short' ? 15 : 40)} minutes` : 'none open'}
            </span>
          </button>
        ))}
      </div>
      <p className="hint">
        {choice ? 'Press the same button again for a different quest.' : 'Pick how long you have.'}{' '}
        {open > 0 && `${plural(open, 'quest')} open.`}
      </p>
    </section>
  )
}

function aThing(target) {
  return `${/^[aeiou]/.test(target) ? 'an' : 'a'} ${target}`
}

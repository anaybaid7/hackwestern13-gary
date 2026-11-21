// The small picture of one thing, for the field guide and the journal.
// `locked` draws it as a silhouette: a thing Gary has not found yet.
import { pictureFor } from '../things.js'

const DRAWINGS = {
  bench: (
    <svg viewBox="0 0 32 32">
      <rect x="6" y="9" width="3" height="18" rx="1" fill="#33423d" />
      <rect x="23" y="9" width="3" height="18" rx="1" fill="#33423d" />
      <rect x="2" y="8" width="28" height="5" rx="1.5" fill="#b97f45" />
      <rect x="2" y="16" width="28" height="5" rx="1.5" fill="#c98f52" />
    </svg>
  ),
  hydrant: (
    <svg viewBox="0 0 32 32">
      <rect x="6" y="14" width="20" height="6" rx="2" fill="#b82a23" />
      <path d="M11 12 a5 6 0 0 1 10 0 v15 h-10 z" fill="#d93a31" />
      <rect x="13.5" y="3" width="5" height="4" rx="1" fill="#b82a23" />
      <rect x="8" y="26" width="16" height="4" rx="1.5" fill="#b82a23" />
      <circle cx="16" cy="17" r="2.2" fill="#f6d9d6" />
    </svg>
  ),
  meter: (
    <svg viewBox="0 0 32 32">
      <rect x="14.5" y="15" width="3" height="15" fill="#5d6f78" />
      <rect x="9" y="3" width="14" height="15" rx="7" fill="#7f95a0" />
      <rect x="12" y="7" width="8" height="5" rx="1" fill="#dfe9ee" />
    </svg>
  ),
}

export default function ThingIcon({ name, locked = false }) {
  const picture = pictureFor(name)
  const className = `thing-icon${locked ? ' locked' : ''}`
  if (picture.kind === 'emoji') {
    return (
      <span className={className} aria-hidden="true">
        {picture.value}
      </span>
    )
  }
  if (picture.kind === 'svg') {
    return (
      <span className={className} aria-hidden="true">
        {DRAWINGS[picture.value]}
      </span>
    )
  }
  return (
    <span className={`${className} letters`} aria-hidden="true">
      {locked ? '?' : picture.value}
    </span>
  )
}

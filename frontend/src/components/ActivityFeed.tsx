import { useEffect, useRef } from 'react'
import { AGENT_COLOR, type FeedLine } from '../agents'

const ICON: Record<FeedLine['kind'], string> = {
  say: '💬', tool: '🔧', result: '📥', ask: '➡️', reply: '↩️', refused: '⛔', start: '▶', end: '✓', error: '⚠️', run: '🏁', approve: '✅', deny: '🚫', wait: '⏳',
}

/** Running log of what every agent said and did, newest at the bottom. */
export function ActivityFeed({ feed }: { feed: FeedLine[] }) {
  const end = useRef<HTMLLIElement>(null)
  useEffect(() => {
    const list = end.current?.parentElement
    if (list) list.scrollTop = list.scrollHeight
  }, [feed.length])
  return (
    <section className="panel feed-panel" aria-label="Live activity">
      <h2>Live activity</h2>
      <ul className="feed">
        {feed.length === 0 && <li className="empty">Pick a ticket and run the team to watch the agents work.</li>}
        {feed.map((f) => (
          <li key={`${f.step}-${f.kind}-${f.text.slice(0, 12)}`} className={`feed-${f.kind}`}>
            <span className="feed-time">{f.t.toFixed(0)}s</span>
            <span className="feed-icon">{ICON[f.kind]}</span>
            <span className="feed-text">
              <b style={{ color: AGENT_COLOR[f.agent] || '#bcd6ff' }}>{f.agent}</b> {f.text}
            </span>
          </li>
        ))}
        <li ref={end} aria-hidden />
      </ul>
    </section>
  )
}

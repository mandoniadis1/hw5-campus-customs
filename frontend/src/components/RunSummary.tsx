import { AGENTS, type LiveState } from '../agents'
import type { RunInfo, Ticket } from '../types'


/** After (and during) a run: the Boss's decision and a short line on what each agent did. */
export function RunSummary({ ticket, live, run }: { ticket: Ticket; live: LiveState; run: RunInfo | null }) {
  const decision = run?.report?.tickets.find((d) => d.ticket_id === ticket.id) ?? run?.report?.tickets[0]
  const t = live.totals
  return (
    <section className="panel summary" aria-label="Run summary">
      <h2>
        Ticket #{ticket.id} summary
        {t.requests > 0 && (
          <span className="totals">
            {t.seconds.toFixed(0)}s · {t.requests} model calls · {t.tools} tool calls · {t.delegations} hand-offs · {t.tokens.toLocaleString()} tokens
          </span>
        )}
      </h2>

      {run?.status === 'error' && <p className="error">The run failed: {run.error}</p>}

      {decision && (
        <div className="decision">
          <div className="decision-head">
            <span className="decision-label">Boss's call</span>
            <span className={`status s-${decision.status}`}>{decision.status === 'resolved' ? 'RESOLVED' : 'OPEN'}</span>
          </div>
          <p>{decision.decision}</p>
          <ul className="numbers">
            {decision.numbers.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
          {decision.status === 'open' && (decision.still_needed?.length ?? 0) > 0 && (
            <p className="needs">Still needed: {decision.still_needed!.join(' · ')}</p>
          )}
          {decision.approvals_needed.length > 0 && (
            <p className="needs">
              Needs approval:{' '}
              {decision.approvals_needed.map((a) => `${a.what}${a.amount != null ? ` ($${a.amount.toLocaleString()})` : ''}`).join(' · ')}
            </p>
          )}
          {decision.customer_draft && <blockquote className="draft">{decision.customer_draft}</blockquote>}
        </div>
      )}

      {live.humans.some((h) => h.ticket === ticket.id) && (
        <div className="humans">
          <span className="decision-label">Human decisions</span>
          <ul>
            {live.humans.filter((h) => h.ticket === ticket.id).map((h) => (
              <li key={h.text}>{h.text}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="agent-summaries">
        {AGENTS.map((a) => {
          const s = live.agents[a.name]
          const tools = Object.entries(s.tools)
          const took = tools.length || s.asked.length || s.askedBy.length || s.lastSaid
          return (
            <div key={a.name} className={`agent-summary ${took ? '' : 'skipped'}`} style={{ ['--c' as string]: a.color }}>
              <div className="as-name">
                <span>{a.icon}</span> {a.name}
              </div>
              {took ? (
                <>
                  {s.askedBy.length > 0 && <div className="as-line">Asked by {[...new Set(s.askedBy)].join(', ')}</div>}
                  {tools.length > 0 && <div className="as-line">Used {tools.map(([k, n]) => (n > 1 ? `${k} ×${n}` : k)).join(', ')}</div>}
                  {s.asked.length > 0 && <div className="as-line">Handed off to {[...new Set(s.asked)].join(', ')}</div>}
                  {s.lastSaid && <p className="as-said">{s.lastSaid.length > 260 ? `${s.lastSaid.slice(0, 259)}…` : s.lastSaid}</p>}
                </>
              ) : (
                <div className="as-line muted">Not needed on this ticket</div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

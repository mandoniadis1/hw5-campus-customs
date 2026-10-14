import type { ApprovalRequest, Ticket } from '../types'

const TYPE_LABEL: Record<string, string> = { customer_order: 'Customer order', rent_notice: 'Rent notice', price_override: 'Price override' }

export function linkedApprovals(t: Ticket, pending: ApprovalRequest[]) {
  return pending.filter((p) => (p.kind === 'invoice' && p.ref_id === t.invoice_id) || (p.kind === 'rent' && p.ref_id === t.lease_id))
}

function ask(t: Ticket): string {
  if (t.type === 'customer_order') return `${t.qty} × ${t.sku} · size ${t.size}`
  if (t.type === 'price_override') return `${t.qty} × ${t.sku} · size ${t.size} · discount ask`
  if (t.type === 'rent_notice') return `Lease ${t.lease_id}`
  return t.subject
}

interface Props {
  tickets: Ticket[]
  selected: number | null
  working: Set<number> // tickets the current run is working on
  busy: boolean // any run going
  finishedRuns: Set<number>
  pending: ApprovalRequest[]
  onSelect: (id: number) => void
  onRun: (id: number) => void
  onRunAll: () => void
  onResolve: (id: number) => void
}

export function TicketList({ tickets, selected, working, busy, finishedRuns, pending, onSelect, onRun, onRunAll, onResolve }: Props) {
  const openCount = tickets.filter((t) => t.state === 'open').length
  return (
    <section className="panel tickets" aria-label="Tickets">
      <h2>Tickets</h2>
      <div className="run-modes">
        <button className="btn primary wide" disabled={busy || openCount === 0} onClick={onRunAll} title="One Boss run over every open ticket: one shared cash plan, specialists work in parallel">
          {openCount === 0 ? '✓ All tickets resolved' : <>▶ Run all {openCount} with Boss</>}
        </button>
        <p className="run-hint">{openCount === 0 ? 'Reset the shop to run them again' : 'or run one ticket at a time below'}</p>
      </div>
      <ul>
        {tickets.map((t) => {
          const resolved = t.state === 'resolved'
          const isRunning = working.has(t.id)
          const waiting = linkedApprovals(t, pending)
          return (
            <li key={t.id}>
              <article
                className={`ticket ${resolved ? 'resolved' : ''} ${selected === t.id ? 'selected' : ''} ${isRunning ? 'running' : ''}`}
                onClick={() => onSelect(t.id)}
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onSelect(t.id)}
                aria-current={selected === t.id}
              >
                <header>
                  <span className="ticket-id">#{t.id}</span>
                  {resolved ? <span className="resolved-badge">✓ RESOLVED</span> : <span className="status s-open">OPEN</span>}
                </header>
                <div className="ticket-subject">{t.subject}</div>
                <div className="ticket-meta">{TYPE_LABEL[t.type] || t.type} · {t.requester}</div>
                <div className="ticket-ask">{ask(t)}</div>
                {!resolved && (
                  <div className="ticket-actions" onClick={(e) => e.stopPropagation()}>
                    <button className="btn primary" disabled={busy} onClick={() => onRun(t.id)}>
                      {isRunning ? <><span className="spinner" /> Team working…</> : finishedRuns.has(t.id) ? 'Run this ticket again' : 'Run this ticket'}
                    </button>
                    {finishedRuns.has(t.id) && !isRunning && (
                      <button
                        className="btn ghost"
                        disabled={waiting.length > 0}
                        title={waiting.length ? 'Approve or deny its payment first' : 'Close this ticket'}
                        onClick={() => onResolve(t.id)}
                      >
                        Mark resolved
                      </button>
                    )}
                  </div>
                )}
                {!resolved && waiting.length > 0 && <div className="ticket-waiting">💳 {waiting.length} payment waiting for your approval</div>}
              </article>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

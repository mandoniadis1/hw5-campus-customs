import type { ApprovalRequest, Cash } from '../types'

const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

/** Checking balance. Dark green normally; red when there isn't enough to cover what's owed. */
export function CashCard({ cash, history }: { cash: Cash | null; history: ApprovalRequest[] }) {
  if (!cash) return <div className="cash-card">…</div>
  // A pay-tool decline only counts while that bill is still unpaid (no later paid request for it).
  const paid = new Set(history.filter((h) => h.status === 'paid').map((h) => `${h.kind}:${h.ref_id}`))
  const shortFor = history.filter((d) => d.status === 'declined' && d.decided_by === 'pay tool' && !paid.has(`${d.kind}:${d.ref_id}`))
  const short = cash.checking_if_all_pending_paid < 0 || shortFor.length > 0
  return (
    <div className={`cash-card ${short ? 'short' : ''}`} aria-live="polite">
      <div className="cash-label">Checking</div>
      <div className="cash-amount">{usd(cash.checking)}</div>
      <div className="cash-sub">
        {cash.pending_total > 0 ? (
          <>
            {usd(cash.pending_total)} waiting for approval · {usd(cash.checking_if_all_pending_paid)} after
          </>
        ) : (
          <>Nothing waiting for approval</>
        )}
      </div>
      {short && (
        <div className="cash-warn">
          Not enough cash
          {shortFor.length > 0 && <> for {shortFor.map((d) => (d.kind === 'invoice' ? `invoice ${d.ref_id}` : 'rent')).join(', ')}</>}
        </div>
      )}
    </div>
  )
}

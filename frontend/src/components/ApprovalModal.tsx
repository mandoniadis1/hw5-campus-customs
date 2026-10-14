import { useEffect, useState } from 'react'
import type { ApprovalRequest, Cash } from '../types'

const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

interface Props {
  request: ApprovalRequest
  cash: Cash | null
  queued: number
  onDecide: (approve: boolean, name: string) => Promise<void>
  onLater: () => void
}

/** Pops up whenever the team has queued a payment: a human approves or denies it. */
export function ApprovalModal({ request, cash, queued, onDecide, onLater }: Props) {
  const [name, setName] = useState(() => localStorage.getItem('desk.approver') || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => setError(''), [request.id])
  const after = cash ? cash.checking - request.amount : null

  async function decide(approve: boolean) {
    if (!name.trim()) return setError('Type your name so the payment records who approved it.')
    localStorage.setItem('desk.approver', name.trim())
    setBusy(true)
    setError('')
    try {
      await onDecide(approve, name.trim())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal aria-labelledby="approval-title">
      <div className="modal">
        <div className="modal-kicker">Human approval needed{queued > 1 && ` · ${queued} waiting`}</div>
        <h3 id="approval-title">
          Pay {request.payee} <span className="modal-amount">{usd(request.amount)}</span>
        </h3>
        <dl>
          <dt>For</dt>
          <dd>{request.kind === 'rent' ? `Rent, lease ${request.ref_id}` : `Invoice ${request.ref_id}`}</dd>
          <dt>Asked by</dt>
          <dd>{request.requested_by}</dd>
          {request.reason && (
            <>
              <dt>Why</dt>
              <dd>{request.reason}</dd>
            </>
          )}
          {cash && (
            <>
              <dt>Checking</dt>
              <dd>
                {usd(cash.checking)} → <b className={after! < 0 ? 'neg' : 'pos'}>{usd(after!)}</b>
              </dd>
            </>
          )}
        </dl>
        <label className="modal-name">
          Your name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Madison" maxLength={80} autoFocus />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button className="btn deny" disabled={busy} onClick={() => decide(false)}>
            DENY
          </button>
          <button className="btn approve" disabled={busy} onClick={() => decide(true)}>
            APPROVE
          </button>
        </div>
        <button className="later" onClick={onLater} disabled={busy}>
          Decide later
        </button>
        <p className="modal-foot">Approving pays it from checking. The pay tool still declines it if cash would go below $0.</p>
      </div>
    </div>
  )
}

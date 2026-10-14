export type AgentName = 'Boss' | 'Inventory' | 'Accounting' | 'Facilities' | 'Customer Service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: 'open' | 'resolved'
  state: 'open' | 'resolved'
  notes: string | null
  created_at: string
}

export interface Cash {
  date_today: string
  checking: number
  as_of: string
  pending_total: number
  checking_if_all_pending_paid: number
  pending_approvals: { id: number; kind: string; ref_id: number; payee: string; amount: number }[]
}

export interface ApprovalRequest {
  id: number
  kind: 'invoice' | 'rent'
  ref_id: number
  payee: string
  amount: number
  account: string
  reason: string | null
  requested_by: string
  status: 'pending' | 'paid' | 'declined'
  decided_by: string | null
  decision_note: string | null
  created_at: string
}

export interface AuditEvent {
  run_id: string
  step: number
  timestamp: string
  elapsed_s: number
  event: string
  agent?: string
  chain?: string[]
  model?: string
  text?: string
  tool_calls?: { tool: string; call_id: string; args: Record<string, unknown> }[]
  tool_returns?: { tool: string; call_id: string; content: string }[]
  usage?: { requests: number; input_tokens: number; output_tokens: number }
  detail?: Record<string, unknown>
}

export interface RunInfo {
  run_id: string
  ticket_id: number | null // null = all open tickets in one Boss run
  status: 'running' | 'done' | 'error' | 'stopped'
  started_at: string
  finished_at?: string
  error?: string
  delegations?: number
  report?: BossReport
}

export interface TicketDecision {
  ticket_id: number
  decision: string
  numbers: string[]
  approvals_needed: { request_id: number | null; what: string; amount: number | null; status: string }[]
  customer_draft: string | null
  agents_consulted: AgentName[]
  status: 'open' | 'resolved'
  still_needed?: string[]
}

export interface BossReport {
  date_today: string
  cash_plan: string[]
  tickets: TicketDecision[]
  missing_info: string[]
}

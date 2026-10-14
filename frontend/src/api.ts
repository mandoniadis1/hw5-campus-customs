import type { ApprovalRequest, AuditEvent, Cash, RunInfo, Ticket } from './types'

export const API_BASE = ((import.meta.env.VITE_API_BASE as string | undefined) || 'http://localhost:8017').replace(/\/$/, '')

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail[0]?.msg : `HTTP ${res.status}`)
  }
  return data as T
}

export const api = {
  tickets: () => call<{ date_today: string; tickets: Ticket[] }>('/api/tickets'),
  cash: () => call<Cash>('/api/cash'),
  approvals: (status = 'pending') => call<{ count: number; requests: ApprovalRequest[] }>(`/api/approvals?status=${status}`),
  run: (ticketId: number) => call<RunInfo>(`/api/tickets/${ticketId}/run`, { method: 'POST' }),
  runAll: () => call<RunInfo & { tickets: number[] }>('/api/run-all', { method: 'POST' }),
  stop: (runId: string) => call<{ status: string; denied_requests: number[] }>(`/api/runs/${runId}/stop`, { method: 'POST' }),
  health: () => call<{ ok: boolean; running: RunInfo | null }>('/api/health'),
  runStatus: (runId: string) => call<RunInfo>(`/api/runs/${runId}`),
  events: (runId: string, since: number) =>
    call<{ events: AuditEvent[]; next_since: number; running: RunInfo | null }>(
      `/api/events?run_id=${encodeURIComponent(runId)}&since=${since}&limit=500`,
    ),
  decide: (requestId: number, approvedBy: string, approve: boolean, note = '') =>
    call<{ ok: boolean; status: string; error?: string; checking_balance?: number }>(`/api/approvals/${requestId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy, approve, note }),
    }),
  resolve: (ticketId: number, resolvedBy: string) =>
    call<{ ok: boolean }>(`/api/tickets/${ticketId}/resolve`, { method: 'POST', body: JSON.stringify({ resolved_by: resolvedBy }) }),
  reset: () => call<{ ok: boolean }>('/api/reset', { method: 'POST' }),
}

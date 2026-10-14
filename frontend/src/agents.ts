import type { AgentName, AuditEvent } from './types'

export interface AgentMeta {
  name: AgentName
  role: string
  color: string
  icon: string
}

// Each agent glows its own color when active (the rest of the board stays Yale navy).
export const AGENTS: AgentMeta[] = [
  { name: 'Boss', role: 'Runs the tickets · final calls', color: '#63a4ff', icon: '★' },
  { name: 'Inventory', role: 'Stock · shortfalls · restock dates', color: '#4fd1c5', icon: '▤' },
  { name: 'Accounting', role: 'Cash · invoices · margins', color: '#f2c94c', icon: '$' },
  { name: 'Facilities', role: 'Lease · rent notices', color: '#b794f4', icon: '⌂' },
  { name: 'Customer Service', role: 'Customer drafts (never sent)', color: '#f687b3', icon: '✉' },
]
export const AGENT_COLOR = { ...Object.fromEntries(AGENTS.map((a) => [a.name, a.color])), Human: '#ffffff' } as Record<string, string>

export interface AgentLive {
  activeRuns: number // >0 while this agent's loop is running (an agent can be asked twice in parallel)
  doing: string // what it's doing right now, in plain words
  lastSaid: string // last thing it said (model text or its final report)
  tools: Record<string, number> // MCP tool -> times called
  askedBy: string[] // who delegated to it
  asked: string[] // who it delegated to
  flash: number // bumps whenever it talks to another agent, to replay the flash animation
  tokens: number
}

export interface Talk {
  key: number
  from: string
  to: string
  kind: 'ask' | 'reply' | 'refused'
}

export interface LiveState {
  agents: Record<string, AgentLive>
  talks: Talk[] // newest last
  feed: FeedLine[]
  humans: { ticket: number | null; text: string }[] // human approve / deny / resolve decisions on this run
  totals: { requests: number; tokens: number; tools: number; delegations: number; seconds: number }
}

export interface FeedLine {
  step: number
  t: number
  agent: string
  kind: 'say' | 'tool' | 'result' | 'ask' | 'reply' | 'refused' | 'start' | 'end' | 'error' | 'run' | 'approve' | 'deny' | 'wait'
  text: string
}

const blank = (): AgentLive => ({ activeRuns: 0, doing: 'Idle', lastSaid: '', tools: {}, askedBy: [], asked: [], flash: 0, tokens: 0 })

function prettyArgs(args: Record<string, unknown>): string {
  const parts = Object.entries(args)
    .filter(([k]) => !['reason', 'message', 'request', 'note'].includes(k))
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
  return parts.join(', ')
}

/** Agents answer in markdown; show it as plain text on the board. */
export const plain = (s: string) => s.replace(/\*\*|__|`/g, '').replace(/^#+\s*/gm, '').replace(/\s+/g, ' ').trim()
const clip = (s: string, n = 180) => { const p = plain(s); return p.length > n ? `${p.slice(0, n - 1)}…` : p }

/** Fold the audit trail of one run into what each agent is doing and has done. */
export function foldEvents(events: AuditEvent[]): LiveState {
  const agents: Record<string, AgentLive> = Object.fromEntries(AGENTS.map((a) => [a.name, blank()]))
  const talks: Talk[] = []
  const feed: FeedLine[] = []
  const humans: LiveState['humans'] = []
  const totals = { requests: 0, tokens: 0, tools: 0, delegations: 0, seconds: 0 }
  const get = (name?: string) => (name && agents[name]) || null

  for (const e of events) {
    // run time = the agents' own steps (human clicks can come long after the run ended)
    if (!e.event.startsWith('human_')) totals.seconds = e.elapsed_s
    const a = get(e.agent)
    const d = (e.detail || {}) as Record<string, unknown>
    switch (e.event) {
      case 'run_start':
        feed.push({ step: e.step, t: e.elapsed_s, agent: 'Boss', kind: 'run', text: d.ticket_id == null ? 'Run started on all open tickets' : `Run started on ticket ${d.ticket_id}` })
        break
      case 'user_prompt':
        if (a) {
          a.activeRuns += 1
          a.doing = 'Reading the request…'
        }
        break
      case 'model_request':
        if (a) a.doing = e.tool_returns?.length ? `Reading ${e.tool_returns.map((r) => r.tool).join(', ')} results…` : 'Thinking…'
        for (const r of e.tool_returns || []) {
          if (r.tool === 'ask_agent' || r.tool === 'final_result') continue
          feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent || '', kind: 'result', text: `${r.tool} → ${clip(r.content, 110)}` })
        }
        break
      case 'model_response': {
        if (!a) break
        totals.requests += e.usage?.requests || 1
        const tok = (e.usage?.input_tokens || 0) + (e.usage?.output_tokens || 0)
        totals.tokens += tok
        a.tokens += tok
        if (e.text) {
          a.lastSaid = plain(e.text)
          feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent!, kind: 'say', text: clip(e.text, 220) })
        }
        const calls = (e.tool_calls || []).filter((c) => c.tool !== 'final_result')
        for (const c of calls) {
          if (c.tool === 'ask_agent') continue // shown as a delegation instead
          a.tools[c.tool] = (a.tools[c.tool] || 0) + 1
          totals.tools += 1
          feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent!, kind: 'tool', text: `${c.tool}(${clip(prettyArgs(c.args), 90)})` })
        }
        a.doing = calls.length ? `Calling ${calls.map((c) => (c.tool === 'ask_agent' ? `→ ${c.args.agent}` : c.tool)).join(', ')}` : 'Writing a reply…'
        break
      }
      case 'delegation_start': {
        const to = String(d.to)
        totals.delegations += 1
        if (a) {
          a.asked.push(to)
          a.flash += 1
          a.doing = `Talking to ${to}…`
        }
        const b = get(to)
        if (b) {
          b.askedBy.push(e.agent!)
          b.flash += 1
        }
        talks.push({ key: e.step, from: e.agent!, to, kind: 'ask' })
        feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent!, kind: 'ask', text: `asks ${to}: ${clip(String(d.request || ''), 200)}` })
        break
      }
      case 'delegation_end': {
        const to = String(d.to)
        const b = get(to)
        if (a) a.flash += 1
        if (b) b.flash += 1
        talks.push({ key: e.step, from: e.agent!, to, kind: 'reply' })
        feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent!, kind: 'reply', text: `reports back to ${to}: ${clip(String(d.reply || ''), 200)}` })
        break
      }
      case 'delegation_refused':
      case 'delegation_reused':
        talks.push({ key: e.step, from: e.agent!, to: String(d.to), kind: 'refused' })
        feed.push({
          step: e.step, t: e.elapsed_s, agent: e.agent!, kind: 'refused',
          text: e.event === 'delegation_reused' ? `re-asked ${d.to}: answered from the first reply` : `blocked from asking ${d.to}: ${clip(String(d.reason || ''), 140)}`,
        })
        break
      case 'agent_end':
        if (a) {
          a.activeRuns = Math.max(0, a.activeRuns - 1)
          // the Boss's final answer is its structured report: point to it instead of dumping JSON
          a.lastSaid = e.text?.trimStart().startsWith('{') ? 'Sent the final report (see the Boss\'s call below).' : e.text ? plain(e.text) : a.lastSaid
          a.doing = a.activeRuns ? a.doing : 'Done'
        }
        feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent || '', kind: 'end', text: e.text?.trimStart().startsWith('{') ? 'finished: sent the final report' : `finished${e.text ? `: ${clip(e.text, 160)}` : ''}` })
        break
      case 'error':
        feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent || 'Boss', kind: 'error', text: e.text || 'error' })
        break
      case 'approval_wait_start':
        if (a) a.doing = `⏳ Waiting for your approval (request #${d.request_id})`
        feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent || '', kind: 'wait', text: `queued $${Number(d.amount).toLocaleString()} to ${d.payee}. The team is waiting for your APPROVE / DENY` })
        break
      case 'approval_wait_end':
        if (a) a.doing = 'Reading the decision…'
        feed.push({ step: e.step, t: e.elapsed_s, agent: e.agent || '', kind: 'wait', text: `got the decision on request #${d.request_id}: ${clip(String(d.outcome || ''), 140)}` })
        break
      case 'human_approval': {
        const money = (n: unknown) => (typeof n === 'number' ? `$${n.toLocaleString()}` : '')
        const what = `${d.kind === 'rent' ? 'rent' : `invoice ${d.ref_id}`} to ${d.payee} (${money(d.amount)})`
        const line =
          d.outcome === 'paid'
            ? `${d.by} approved ${what}. Paid; checking now ${money(d.checking_after)}`
            : d.decision === 'deny'
              ? `${d.by} denied ${what}`
              : `${d.by} approved ${what}, but the pay tool declined it: ${d.note ?? 'not enough cash'}`
        humans.push({ ticket: (d.ticket_id as number) ?? null, text: line })
        feed.push({ step: e.step, t: e.elapsed_s, agent: 'Human', kind: d.outcome === 'paid' ? 'approve' : 'deny', text: line.replace(`${d.by} `, `(${d.by}) `) })
        break
      }
      case 'human_resolve': {
        const line = `${d.by} marked ticket ${d.ticket_id} resolved`
        humans.push({ ticket: (d.ticket_id as number) ?? null, text: line })
        feed.push({ step: e.step, t: e.elapsed_s, agent: 'Human', kind: 'approve', text: `(${d.by}) marked ticket ${d.ticket_id} resolved` })
        break
      }
      case 'run_stopped': {
        const denied = (d.denied_requests as number[] | undefined) ?? []
        feed.push({ step: e.step, t: e.elapsed_s, agent: 'Human', kind: 'deny', text: `stopped the run${denied.length ? `; denied unapproved request${denied.length > 1 ? 's' : ''} #${denied.join(', #')}` : ''}` })
        for (const x of Object.values(agents)) {
          x.activeRuns = 0
          if (x.doing !== 'Idle' && x.doing !== 'Done') x.doing = 'Stopped'
        }
        break
      }
      case 'run_end':
        feed.push({ step: e.step, t: e.elapsed_s, agent: 'Boss', kind: 'run', text: 'Run finished' })
        for (const x of Object.values(agents)) x.activeRuns = 0
        break
    }
  }
  return { agents, talks, feed, humans, totals }
}

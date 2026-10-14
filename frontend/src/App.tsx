import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { foldEvents } from './agents'
import { api } from './api'
import { ActivityFeed } from './components/ActivityFeed'
import { AgentStage } from './components/AgentStage'
import { ApprovalModal } from './components/ApprovalModal'
import { CashCard } from './components/CashCard'
import { DanDoodles, DanFace, WalkingDan } from './components/Dan'
import { RunSummary } from './components/RunSummary'
import { TicketList } from './components/TicketList'
import type { ApprovalRequest, AuditEvent, Cash, RunInfo, Ticket } from './types'

const RUNS_KEY = 'desk.runs' // ticket id -> latest run id, so the board remembers runs across reloads
const loadRuns = (): Record<number, string> => JSON.parse(localStorage.getItem(RUNS_KEY) || '{}')
const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [today, setToday] = useState('')
  const [cash, setCash] = useState<Cash | null>(null)
  const [pending, setPending] = useState<ApprovalRequest[]>([])
  const [history, setHistory] = useState<ApprovalRequest[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [runs, setRuns] = useState<Record<number, string>>(loadRuns)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [runInfo, setRunInfo] = useState<RunInfo | null>(null)
  const [running, setRunning] = useState<RunInfo | null>(null) // the run in progress, if any
  const [snoozed, setSnoozed] = useState<number[]>([])
  const [toast, setToast] = useState('')
  const [offline, setOffline] = useState(false)
  const since = useRef(0)

  const flash = (msg: string) => {
    setToast(msg)
    window.setTimeout(() => setToast((t) => (t === msg ? '' : t)), 4500)
  }

  // ---- shop state: tickets, cash, approvals (polled) ----
  const refresh = useCallback(async () => {
    try {
      const [t, c, p, d, h] = await Promise.all([api.tickets(), api.cash(), api.approvals('pending'), api.approvals('all'), api.health()])
      setRunning(h.running)
      setTickets(t.tickets)
      setToday(t.date_today)
      setCash(c)
      setPending(p.requests)
      setHistory(d.requests)
      setSelected((s) => s ?? t.tickets[0]?.id ?? null)
      setOffline(false)
    } catch {
      setOffline(true)
    }
  }, [])
  useEffect(() => {
    refresh()
    const id = window.setInterval(refresh, 4000)
    return () => window.clearInterval(id)
  }, [refresh])

  useEffect(() => localStorage.setItem(RUNS_KEY, JSON.stringify(runs)), [runs])

  // ---- events for the selected ticket's latest run ----
  const runId = selected != null ? runs[selected] : undefined
  useEffect(() => {
    setEvents([])
    setRunInfo(null)
    since.current = 0
    if (!runId) return
    let stop = false
    let timer = 0
    const poll = async () => {
      try {
        const r = await api.events(runId, since.current)
        if (stop) return
        if (r.events.length) {
          since.current = r.next_since
          setEvents((e) => [...e, ...r.events])
        }
        const live = r.running?.run_id === runId
        setRunning(r.running)
        if (!live) {
          api.runStatus(runId).then((info) => !stop && setRunInfo(info)).catch(() => {})
          refresh()
          return // run is over: stop polling
        }
      } catch {
        /* backend hiccup: try again */
      }
      timer = window.setTimeout(poll, 1500)
    }
    poll()
    return () => {
      stop = true
      window.clearTimeout(timer)
    }
  }, [runId, refresh])

  const live = useMemo(() => foldEvents(events), [events])
  // Which tickets the current run covers: one ticket, or every open ticket for a Boss run-all.
  const working = useMemo(
    () => new Set(running ? (running.ticket_id == null ? tickets.filter((t) => t.state === 'open').map((t) => t.id) : [running.ticket_id]) : []),
    [running, tickets],
  )
  // A run started somewhere else (another tab, the API): attach its tickets to it so the board shows it live.
  useEffect(() => {
    if (!running || working.size === 0 || [...working].every((id) => runs[id] === running.run_id)) return
    setRuns((m) => ({ ...m, ...Object.fromEntries([...working].map((id) => [id, running.run_id])) }))
    if (selected == null || !working.has(selected)) setSelected([...working][0])
  }, [running, working, runs, selected])
  const finishedRuns = useMemo(
    () => new Set(Object.keys(runs).map(Number).filter((id) => !working.has(id))),
    [runs, working],
  )
  const ticket = tickets.find((t) => t.id === selected) || null
  const ask = pending.find((p) => !snoozed.includes(p.id))

  // ---- actions ----
  async function runTeam(id: number) {
    try {
      const r = await api.run(id)
      setSelected(id)
      setRunning(r)
      setRuns((m) => ({ ...m, [id]: r.run_id }))
      flash(`The team is on ticket #${id}`)
    } catch (e) {
      flash(e instanceof Error ? e.message : String(e))
    }
  }

  async function runAll() {
    try {
      const r = await api.runAll()
      setRunning(r)
      // every ticket in this run shows the same live run
      setRuns((m) => ({ ...m, ...Object.fromEntries(r.tickets.map((id) => [id, r.run_id])) }))
      if (selected == null || !r.tickets.includes(selected)) setSelected(r.tickets[0])
      flash(`The Boss is on all ${r.tickets.length} open tickets`)
    } catch (e) {
      flash(e instanceof Error ? e.message : String(e))
    }
  }

  async function stop() {
    if (!running) return
    if (!window.confirm('Stop the run now? Any payment it queued that you haven\'t decided yet will be denied.')) return
    try {
      const r = await api.stop(running.run_id)
      setRunning(null)
      flash(`Run stopped${r.denied_requests.length ? `; denied request #${r.denied_requests.join(', #')}` : ''}`)
      await refresh()
    } catch (e) {
      flash(e instanceof Error ? e.message : String(e))
    }
  }

  async function decide(approve: boolean, name: string) {
    if (!ask) return
    const r = await api.decide(ask.id, name, approve)
    if (r.status === 'paid') flash(`Paid ${usd(ask.amount)} to ${ask.payee}. Checking is now ${usd(r.checking_balance!)}.`)
    else if (approve) flash(`Declined by the pay tool: ${r.error ?? 'not enough cash'}`)
    else flash(`Denied: ${ask.payee} won't be paid.`)
    await refresh()
  }

  async function resolve(id: number) {
    const name = localStorage.getItem('desk.approver') || window.prompt('Your name (recorded on the ticket):')?.trim()
    if (!name) return
    localStorage.setItem('desk.approver', name)
    try {
      await api.resolve(id, name)
      flash(`Ticket #${id} marked resolved`)
      await refresh()
    } catch (e) {
      flash(e instanceof Error ? e.message : String(e))
    }
  }

  async function reset() {
    if (!window.confirm('Reset the shop database to the original values? Payments, drafts and ticket updates will be wiped.')) return
    try {
      await api.reset()
      setRuns({})
      setSnoozed([])
      flash('Shop reset to the original data')
      await refresh()
    } catch (e) {
      flash(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="app">
      <DanDoodles />
      <header className="topbar">
        <div className="brand">
          <DanFace size={58} strokeWidth={3.2} />
          <div>
            <div className="kicker">Campus Customs · back office</div>
            <h1>Agent Desk</h1>
            <div className="shopday">Shop day {today || '…'} {offline && <span className="offline">· backend offline (port 8017)</span>}</div>
          </div>
        </div>
        <div className="topbar-right">
          <CashCard cash={cash} history={history} />
          {running && (
            <button className="btn stop" onClick={stop} title="Cancel the run immediately">
              ■ Stop run
            </button>
          )}
          <button className="btn ghost small" onClick={reset} disabled={running !== null}>
            Reset shop
          </button>
        </div>
      </header>

      <main className="board">
        <TicketList
          tickets={tickets}
          selected={selected}
          working={working}
          busy={running !== null}
          finishedRuns={finishedRuns}
          pending={pending}
          onSelect={setSelected}
          onRun={runTeam}
          onRunAll={runAll}
          onResolve={resolve}
        />
        <AgentStage live={live} running={selected != null && working.has(selected)} />
        <ActivityFeed feed={live.feed} />
      </main>

      {ticket && (events.length > 0 || runInfo) && <RunSummary ticket={ticket} live={live} run={runInfo} />}

      {ask && (
        <ApprovalModal
          request={ask}
          cash={cash}
          queued={pending.length}
          onDecide={decide}
          onLater={() => setSnoozed((s) => [...s, ask.id])}
        />
      )}
      {snoozed.length > 0 && pending.some((p) => snoozed.includes(p.id)) && !ask && (
        <button className="pending-pill" onClick={() => setSnoozed([])}>
          💳 {pending.length} payment{pending.length > 1 ? 's' : ''} waiting for approval
        </button>
      )}
      {toast && <div className="toast">{toast}</div>}
      <WalkingDan onBark={() => flash('🐶 Boola boola!')} />
    </div>
  )
}

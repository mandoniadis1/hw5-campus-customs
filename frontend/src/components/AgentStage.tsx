import { useEffect, useState } from 'react'
import { AGENTS, type LiveState, type Talk } from '../agents'

// Pentagon layout (percent of the stage). Boss on top; lines connect every pair: full connectivity.
const POS: Record<string, [number, number]> = {
  Boss: [50, 15],
  Facilities: [15, 45],
  Inventory: [85, 45],
  Accounting: [29, 84],
  'Customer Service': [71, 84],
}
const PAIRS = AGENTS.flatMap((a, i) => AGENTS.slice(i + 1).map((b) => [a.name, b.name] as const))

/** The five agents: each glows its own color while working and flashes when it talks to another agent. */
export function AgentStage({ live, running }: { live: LiveState; running: boolean }) {
  // Show each talk as a pulse on its line for a moment after it arrives.
  const [pulses, setPulses] = useState<Talk[]>([])
  const lastKey = live.talks.at(-1)?.key ?? 0
  useEffect(() => {
    const fresh = live.talks.filter((t) => !pulses.some((p) => p.key === t.key)).slice(-4)
    if (!fresh.length) return
    setPulses((p) => [...p, ...fresh].slice(-6))
    const timer = window.setTimeout(() => setPulses((p) => p.filter((x) => !fresh.includes(x))), 2600)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastKey])

  return (
    <section className="panel stage-panel" aria-label="Agent team">
      <h2>
        Agent team {running && <span className="live-dot">LIVE</span>}
      </h2>
      <div className="stage">
        <svg className="links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
          {PAIRS.map(([a, b]) => {
            const [x1, y1] = POS[a]
            const [x2, y2] = POS[b]
            const pulse = pulses.find((p) => (p.from === a && p.to === b) || (p.from === b && p.to === a))
            const color = pulse ? AGENTS.find((x) => x.name === pulse.from)!.color : undefined
            return (
              <g key={`${a}-${b}`}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} className="link" />
                {pulse && (
                  <line
                    key={pulse.key}
                    x1={pulse.from === a ? x1 : x2}
                    y1={pulse.from === a ? y1 : y2}
                    x2={pulse.from === a ? x2 : x1}
                    y2={pulse.from === a ? y2 : y1}
                    className={`link-pulse ${pulse.kind}`}
                    style={{ stroke: color }}
                    pathLength={100}
                  />
                )}
              </g>
            )
          })}
        </svg>
        {AGENTS.map((a) => {
          const s = live.agents[a.name]
          const active = running && s.activeRuns > 0
          const used = Object.values(s.tools).reduce((x, y) => x + y, 0)
          const [x, y] = POS[a.name]
          return (
            <div
              key={a.name}
              className={`agent ${active ? 'active' : ''} ${s.doing === 'Idle' ? 'idle' : ''}`}
              style={{ left: `${x}%`, top: `${y}%`, ['--c' as string]: a.color }}
            >
              {s.flash > 0 && <span key={s.flash} className="agent-flash" />}
              <div className="agent-head">
                <span className="agent-icon">{a.icon}</span>
                <div>
                  <div className="agent-name">{a.name}</div>
                  <div className="agent-role">{a.role}</div>
                </div>
              </div>
              <div className="agent-doing">{s.doing}</div>
              {s.lastSaid && <p className="agent-said">“{s.lastSaid}”</p>}
              {used > 0 && (
                <div className="agent-tools">
                  {Object.entries(s.tools).slice(0, 3).map(([tool, n]) => (
                    <span key={tool} className="chip">
                      {tool}
                      {n > 1 && <b> ×{n}</b>}
                    </span>
                  ))}
                  {Object.keys(s.tools).length > 3 && <span className="chip more">+{Object.keys(s.tools).length - 3} more</span>}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

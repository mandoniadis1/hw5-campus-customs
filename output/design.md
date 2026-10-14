# Campus Customs Agent Desk: Design

The React board in `hw5/frontend/` (React + Vite + TypeScript). It talks only to the FastAPI backend at
`http://localhost:8017` (Problem 7). The backend gets every shop fact from the campus-customs MCP server.

**Run it:**
1. Start the backend: `cd backend && .venv/bin/uvicorn main:app --reload --port 8017`
2. Start the board: `cd frontend && npm run dev`. It opens **http://localhost:5177**. Vite's usual
   5173 is taken by another class app here, so the port is pinned in `vite.config.ts`.
3. The backend's CORS list allows the board's origin (`localhost:5173` and `localhost:5177`, plus the
   `127.0.0.1` versions) and nothing else.

## Layout

The goal is an easily readable dashboard for tracking tickets, agent activity, and our money.

- **Top bar:** a Handsome Dan doodle, the "Agent Desk" title, the shop's day (`desk.date_today`), the
  **checking balance card**, and *Reset shop*.
- **Left column, Tickets:**
  - All 3 tickets with id, subject, type, requester, what they want, and a status chip.
  - **Run agent team** starts the team on that one ticket. Only one run at a time, because the tickets
    share the same cash.
  - **Mark resolved** appears after a run. It stays disabled while that ticket still has a payment
    waiting for approval.
- **Middle, Agent team:** the five agents in a pentagon (Boss on top). Faint lines join every pair, to
  show that any agent can talk to any other. Each agent card shows what it's doing right now, what it
  last said, and the MCP tools it has used.
- **Right column, Live activity:** a running log, newest at the bottom: who said what, each tool call
  and a short result, hand-offs, refused hand-offs, and when each agent finished.
- **Bottom, Ticket summary:**
  - The Boss's call (decision, the numbers behind it, what needs approval, the customer draft, status).
  - One card per agent saying what it did (who asked it, tools used, who it handed off to, its final words).
  - Agents that weren't needed say **"Not needed on this ticket"**, so it's visible that the team didn't
    send every specialist on every ticket.
  - Run totals: seconds, model calls, tool calls, hand-offs, tokens.
- **APPROVE / DENY popup:**
  - Appears whenever the team queues a payment. It shows the payee, amount, what it's for, who asked,
    why, and checking before → after (red if it would go negative).
  - The approver types their name once (it's remembered). That name goes into `payments.approved_by`.
  - *Decide later* hides it behind a yellow "payment waiting" pill.

## How the agents read differently

- Each agent has its own color: Boss sky blue, Inventory teal, Accounting gold, Facilities violet,
  Customer Service pink. The color shows on the name, icon, card border and feed lines, and the agent's
  name is always written next to it.
- **Glow when active:** while an agent's loop is running, its card glows and pulses in its color.
  Agents that aren't working are dimmed.
- **Flash when talking to each other:** on every hand-off (`delegation_start`) and every report back
  (`delegation_end`), both agents' cards flash. A pulse of light also travels along the line between
  them, in the asker's color. A refused hand-off, like a bounce back up the chain, shows as a red dashed
  line and a ⛔ line in the feed.

## How resolved tickets and cash show up

- **Resolved tickets** are grayed out (dark gray card, gray text) with a bright green **✓ RESOLVED** badge
  and a green outline glow. Only the text is grayed, so the badge stays bright green. Their run buttons
  disappear.
- **Cash** is a big **dark green** number on a light green card. Dark green on the dark navy board
  wouldn't be readable, so the card is light. It shows what's waiting for approval and what checking
  would be after.
- The card **turns red** with "Not enough cash for invoice N" when what's owed can't be covered: either
  the pending total is more than checking, or the pay tool has declined a payment for lack of cash.
- The balance **drops right after an approval.** In testing, approving rent took checking from
  $3,400.00 to $1,000.00 and showed a toast: "Paid $2,400.00 to Elm City Properties. Checking is now
  $1,000.00."

## Creative choices

- **Clean Yale look:** the same dark navy / Yale Blue palette as the hw4 Campus Customs site (no rainbow),
  rounded glassy panels, a Georgia serif title, and plenty of spacing. Red, amber and green are only
  used where they mean something: approvals, blocked or needs-human, resolved, and cash.
- **Handsome Dan doodles:** faint white outline scribbles behind the board. There are three bulldog
  faces (wrinkly brow, jowls, underbite, a "Y" sweater collar), paw prints, a chew bone, a hand-drawn
  Yale "Y" with a squiggle, and a star.
- **Walking Handsome Dan 'moji:** a little bulldog in a navy "Y" sweater trots back and forth along the
  bottom of the page, with bobbing body and alternating legs, turning around at each edge. Click him
  for a "🐶 Boola boola!".
- All motion (glows, pulses, the walking Dan) turns off for users who have "reduce motion" set.

## How it works

| Piece | File |
| --- | --- |
| API client (all routes from Problem 7, base URL from `VITE_API_BASE`, default `http://localhost:8017`) | `src/api.ts` |
| Turns the audit trail into live per-agent state: active, doing, last said, tools, hand-offs, flashes, feed | `src/agents.ts` (`foldEvents`) |
| Tickets, agent stage, live feed, summary, cash card, approval popup | `src/components/*.tsx` |
| Handsome Dan doodles and the walking 'moji (hand-drawn SVG) | `src/components/Dan.tsx` |
| Polling and actions | `src/App.tsx` |

- **Polling:** tickets, cash and approvals refresh every 4 s. During a run, `/api/events?since=` is
  polled every 1.5 s, so only new steps come down. When the run ends, the Boss's report is fetched from
  `/api/runs/{id}`.
- **Remembering runs:** each ticket's latest run id is kept in `localStorage`, so a reload still shows
  that ticket's agents and summary.
- **New backend route:** `POST /api/tickets/{id}/resolve` (human only) sets the ticket to `resolved`
  through the MCP `update_ticket` tool.

## Fixes found while testing

- **A paid rent could be queued again.** After rent was approved mid-run, an agent queued rent again,
  because the lease's due date had already moved to the next month. The pay tool declined it, which
  would have turned the cash card red. Two fixes:
  - `queue_payment` now refuses rent that was already paid in the last month: "already paid on
    2026-08-31; next due 2026-10-02".
  - The cash card ignores a decline once that bill has been paid.
- **Agent text showed raw markdown.** It's now shown as plain text.
- **Agent cards grew too tall.** Each card now shows at most 3 tool chips, plus "+N more".
- **Five ticket statuses were confusing.** Tickets are now just **OPEN** (blue chip) or **✓ RESOLVED**
  (grayed out, green badge). When a ticket is open, the summary shows **Still needed:** with exactly what
  it's waiting on.

## Run modes and the Stop button

- **▶ Run all N with Boss** (top of the Tickets panel): one Boss run over every open ticket. They share
  one cash plan, and the Boss sends independent work to the specialists in parallel. Every ticket in the
  run shows the same live agents and feed. Each ticket's summary shows its own decision from the Boss's
  report.
- **Run this ticket** (on each card): a separate run on just that ticket. It can only queue that
  ticket's own bill.
- Only one run at a time, either kind, because the tickets share the same cash.
- **■ Stop run** (red, next to the cash card, only while a run is going): asks for confirmation, then
  cancels the run immediately. Any payment that run queued without a decision yet is **denied by "Stop
  button"**, so nothing from a stopped run can be paid later. A Stop or human deny is a one-time "no": a
  later run may queue it again. Only a pay-tool decline (not enough cash) stays declined.
- The board attaches to a run started anywhere (another tab, the API), so it always shows what's running.

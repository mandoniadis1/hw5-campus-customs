# HW5: Campus Customs multi-agent desk

A five-agent team (Boss, Inventory, Accounting, Facilities, Customer Service) that works the Campus
Customs back-office tickets. The agents are built with PydanticAI on `gpt-6-luna` through Portkey. Every
shop fact comes from a FastMCP server over SQLite. A FastAPI backend and a React board let a human run
the team, watch it work, approve payments, and track the cash.

- **Design record:** `output/harness.md`
- **Board design:** `output/design.md`
- **Plan vs. actual, cash ledger, reflection:** `output/desk_tickets.html` (double-click it)

## Layout

```
hw5/
├── AI_prompts.md            every prompt, by problem
├── requirements.txt         one Python env for the MCP server + backend
├── .env.example             copy to .env and add PORTKEY_API_KEY (the real .env is not in git)
├── .mcp.json                how Claude Code / the backend launch the MCP server
├── data/
│   ├── campus_customs.db       original. Never modified
│   └── campus_customs_new.db   working copy every run reads and writes
├── mcp_server/              FastMCP server: 13 tools (see mcp_server/README.md)
├── backend/                 FastAPI (main.py), agents/, prompts/, models.py
├── frontend/                React + Vite + TypeScript board
└── output/                  harness, smoke test, plan, design, resolved tickets, board screenshots, audit trail
```

## Setup (once)

You need Python 3.11+ and Node 20+.

```bash
cd hw5
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
cp .env.example .env                             # then put your PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

## Run it

**1. Clean database (any time you want a fresh start).** This copies the original over the working copy.
The board's **Reset shop** button and `backend/reset_db.py` do the same thing.

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

**2. MCP server.** The backend (and Claude Code, through `.mcp.json`) starts it automatically over stdio,
so you don't need to keep it running yourself. To check that it starts:

```bash
.venv/bin/python mcp_server/server.py            # Ctrl+C to stop
```

**3. FastAPI backend (port 8017).** Run this in its own terminal:

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8017
```

Interactive API docs: http://localhost:8017/docs

**4. React board (port 5177).** Run this in a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5177. The board talks to `http://localhost:8017`. To change that, copy
`frontend/.env.example` to `frontend/.env`.

**5. Full three-ticket run.** Reset the database first (step 1, or **Reset shop** on the board). Then
either:
- click **▶ Run all 3 with Boss** on the board, or
- from `backend/`, run `../.venv/bin/python run_tickets.py`. This one resets the database itself before it
  starts.

When the team queues a payment, the run **waits for a human**:
- On the board, click **APPROVE** or **DENY** in the popup.
- From the terminal, run `cd backend && ../.venv/bin/python approve.py` to list pending payments, then
  `../.venv/bin/python approve.py 1 --by "Your Name"` to approve one.

**■ Stop run** cancels a run and denies any of its payments that haven't been decided.

You can also run a single ticket with **Run this ticket**. That only pays that ticket's own bill.

## Shop rules (enforced in code)

- `desk.date_today` is "today". Lead times come from `vendors`.
- A vendor won't ship while it has an unpaid invoice.
- Every payment needs human approval, and the amount comes from the database.
- The pay tool **declines** anything that would take checking below $0.
- Cash only goes out; no revenue is modeled.
- Customer messages are saved as drafts starting "DRAFT - NOT SENT". Nothing is ever emailed.

## Outputs

| File | What it is |
| --- | --- |
| `output/harness.md` | Design record: tables, MCP tools, agents, routes, dashboard, safety, results |
| `output/mcp_smoke.json` | Problem 4 evidence that each tool returns values matching the database |
| `output/desk_tickets.html` | Expected vs. actual per ticket, the cash ledger, and the reflection |
| `output/design.md` | Dashboard design notes |
| `output/resolved_tickets.json` | Final status, outcome, agent contributions, and human approvals per ticket |
| `output/resolved_board.html` | Board screenshots for each resolved ticket (PNGs in `output/resolved_board/`) |
| `output/audit_trail.json` | Append-only log of every agent step, hand-off, approval wait, and human decision |
| `output/github_url.txt` | This repo's URL |

# HW5: Campus Customs Multi-Agent Team Harness

A running record of how the hw5 system is built and why. New sections are added as each problem is finished.

---

## Problem 2: Study the Campus Customs database

### Setup

`data (3).zip` unzips to `data/campus_customs.db` (9 tables, 53 KB). We copied it to
`data/campus_customs_new.db`, the **working copy** that the MCP server and backend will read and write.
The original stays untouched so we can reset to the starting state and replay ticket resolution
any time (`cp data/campus_customs.db data/campus_customs_new.db`).

This is the shop's **back office**, not the hw4 storefront: stock, costs, vendors, bills, rent, cash,
and a ticket queue. The agents' job is to work the open tickets.

### Tables

| Table | Rows | Fields | Why it matters to the agents |
| --- | --- | --- | --- |
| `desk` | 1 | `date_today`, `notes` | The agents' "today" (2026-08-31), so overdue and due-soon dates are judged against the shop's clock, not the real one. |
| `tickets` | 3 | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The work queue: each ticket's `type` decides which agent picks it up, and its `sku`/`lease_id`/`invoice_id` point to the rows it needs. |
| `inventory` | 10 | `sku`, `name`, `size`, `qty`, `location` | Tells the agents whether an order can be filled from stock right now, per SKU and size (key is `sku` + `size`). |
| `pricing` | 4 | `sku`, `unit_cost`, `list_price` | The margin floor for discount decisions: never sell below `unit_cost` without a human saying so. |
| `vendors` | 3 | `id`, `name`, `specialty`, `lead_days` | Who can restock what and how long it takes, so an agent can promise a realistic date when stock is out. |
| `invoices` | 1 | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Bills the shop owes; an unpaid or overdue invoice can block a restock a customer is waiting on. |
| `leases` | 1 | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | The source of truth for rent, used to check that a rent notice's landlord and due date are real before paying. |
| `cash_accounts` | 1 | `name`, `balance`, `date` | How much money there is ($3,400 in checking) to cover rent and bills before anything is paid. |
| `payments` | 0 | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | The audit log the agents write to when money moves; `approved_by` records the human who signed off. It starts empty. |

### How the 3 open tickets link to the other tables

| Ticket | Type | Ask | Links | What the data shows |
| --- | --- | --- | --- | --- |
| 101 | `customer_order` | 1 × Classic Bulldog Tee, size S | `inventory` (CC-TEE-WHITE, S) → `invoice_id` 501 → `vendors` 1 | Tee S is **out of stock (0)**. The rush reprint for it is invoice 501, **$840 to Bulldog Print Co, due 2026-08-28: 3 days overdue** and still open. The vendor's lead time is 5 days, so the customer waits until it's paid. |
| 102 | `rent_notice` | Rent due in 2 days | `lease_id` 1 → `leases` | Matches the lease: Elm City Properties, Chapel Street shop, **$2,400 due 2026-09-02**. The email gives no amount, so the agent should take it from `leases`, not from the email. |
| 103 | `price_override` | 20 × Basic Hoodie, size M, bulk discount | `inventory` (CC-HOOD-NAVY, M) → `pricing` → `vendors` 1 | Only **8 in stock** in M (short 12). List price $58 and cost $22, so 20 hoodies run $1,160 at list and $440 at cost; any discount must stay above cost. The other 12 need a reprint (5 days). |

**Cash check.** Invoice 501 ($840) plus rent ($2,400) is $3,240, which leaves **$160** of the $3,400 in
checking. Both can be paid, but only just. That's why paying needs a human approval step
(`payments.approved_by`), and why the agents have to look at all the tickets together rather than one
at a time.

---

## Problem 3: Build the MCP server

### Shop rules the tools follow

- `desk.date_today` (2026-08-31) is "today": every overdue / days-until figure is measured against it.
- Vendor lead times come only from `vendors.lead_days`.
- A vendor won't ship new product while it has any unpaid invoice.
- Tools only report what's in the database; a missing row comes back as `"found": false` with a reason, never a guess.
- Payment rules (human approval, decline if cash would go negative, update the tables, cash only goes out) apply to the pay tool, which isn't built yet.

### The 3 tools

`mcp_server/server.py` is a FastMCP server on `data/campus_customs_new.db`. All three tools open the
database **read-only**, so a lookup can never change the shop's data.

| Tool | Reads | Unlocks | Why it's the right tool for that ticket |
| --- | --- | --- | --- |
| `check_stock_and_price(sku, size?, qty_wanted?)` | `inventory`, `pricing`, `desk` | **103** (also confirms 101's stockout) | The bulk-discount ask needs two facts together, how many M hoodies exist (8 of 20, short 12) and the cost floor ($22 vs $58 list, max 62.1% off), so one call answers both "can we fill it?" and "how low can we go?". |
| `get_invoice_status(invoice_id)` | `invoices`, `vendors`, `desk` | **101** | The tee in size S is out of stock and the reprint is stuck behind invoice 501 ($840, 3 days overdue); this tool applies the "no shipping while unpaid" rule and gives the real arrival date if paid today (2026-09-05, from the 5-day lead time). |
| `get_lease(lease_id)` | `leases`, `desk` | **102** | The rent email gives no amount, so the agent must check it against the lease on file (Elm City Properties, $2,400, due in 2 days) before anyone approves paying it. |

### How it was tested

Each tool was called through an in-memory FastMCP client against the working copy. The results matched the
Problem 2 findings above. Unknown ids (`CC-NOPE`, invoice 999) returned "not found", and the database
file was byte-for-byte unchanged afterward.

### Files and how to run

| File | Purpose |
| --- | --- |
| `mcp_server/server.py` | The FastMCP server and its 3 tools |
| `mcp_server/requirements.txt` | `fastmcp` (tested on 4.1.0) |
| `mcp_server/README.md` | What the server is for, the database it uses, and the tools |

Run: `cd mcp_server && .venv/bin/python server.py` (stdio). Not connected to an agent yet.

### Not built yet

*(Update 2026-10-14: all of these were built in Problem 5; see the final overview at the end.)*

Reading the ticket queue, checking the cash balance, the pay tool (with human approval, decline on
insufficient cash, and writes to `payments` / `invoices` / `cash_accounts`), and closing tickets. None of
the tools send email to customers or vendors.

---

## Problem 5: Build the agent team and grow the MCP tools

### How the team is wired

Five PydanticAI agents, all on **gpt-6-luna** through Portkey (`PORTKEY_API_KEY`, hard-coded model in
`backend/config.py`). Each agent's instructions are `backend/prompts/shared_rules.md` (shop rules +
"never invent data" + "only ask the owner, don't bounce") plus its own prompt file.

- **Shop facts only come from MCP.** The backend opens one connection to the `campus-customs` server
  using the command in `hw5/.mcp.json`. There is no second tools layer: agents have no SQL and no file access.
  Each agent sees only the MCP tools its role needs.
- **Full connectivity.** Every agent has `ask_agent(agent, request)`, so any agent can delegate to any
  other, and the child's report comes back as the tool result. Guard rails stop loops:
  - no asking yourself;
  - no asking an agent already up the current chain (A → B → A);
  - chains are at most 3 agents deep;
  - at most 16 delegations per run;
  - the same question to the same agent is answered from the first reply.
- **Agent loop + audit.** `run_agent` drives each agent with `agent.iter()` and appends every loop step
  to `output/audit_trail.json`. That covers the prompt, each model request (with tool results), each
  model response (text, tool calls with arguments, tokens), and the end. Every delegation start, end,
  refusal or reuse is logged too, with the delegation chain. The file is append-only: it's file-locked,
  read, appended to and atomically replaced, and never wiped.

### Agents

| Agent | File | Job | MCP tools it can use |
| --- | --- | --- | --- |
| Boss | `backend/agents/boss.py`, `prompts/boss.md` | Reads all open tickets, routes each one, decides, sets statuses; returns a structured `BossReport` | `list_open_tickets`, `get_cash_balance`, `list_approval_queue`, `update_ticket` |
| Inventory | `backend/agents/inventory.py`, `prompts/inventory.md` | Stock vs wanted vs short; vendor + restock date (`date_today` + `lead_days`); flags unpaid-invoice blocks to Accounting | `check_stock_and_price`, `list_vendors`, `get_invoice_status`, `list_open_tickets` |
| Accounting | `backend/agents/accounting.py`, `prompts/accounting.md` | Cash plan across all tickets, days overdue, margins (below cost = no), queues payments for approval | `get_cash_balance`, `list_invoices`, `get_invoice_status`, `check_stock_and_price`, `queue_payment`, `list_approval_queue`, `list_open_tickets` |
| Facilities | `backend/agents/facilities.py`, `prompts/facilities.md` | Checks a rent notice against the lease (landlord, amount, due date); flags mismatches as possible scams; asks Accounting to queue rent | `get_lease`, `list_open_tickets` |
| Customer Service | `backend/agents/customer_service.py`, `prompts/customer_service.md` | Customer drafts starting "DRAFT - NOT SENT"; Inventory dates and Boss prices only; no cash/vendor talk | `save_customer_draft`, `list_open_tickets` |

Data types live in `backend/models.py`: `TicketDecision` (decision, numbers, approvals, draft, status),
`BossReport`, `ApprovalItem`, and `AuditEntry`.

### MCP tools (after Problem 5)

Nine tools were added to the original three. `approve_payment` is **not given to any agent**.

| Tool | Table(s) | New? | Used by |
| --- | --- | --- | --- |
| `list_open_tickets` | `tickets`, `desk` | new | all agents |
| `update_ticket` | `tickets` (write) | new | Boss |
| `check_stock_and_price` | `inventory`, `pricing`, `desk` | P3 | Inventory, Accounting |
| `list_vendors` | `vendors`, `invoices`, `desk` | new | Inventory |
| `get_invoice_status` | `invoices`, `vendors`, `desk` | P3 | Inventory, Accounting |
| `list_invoices` | `invoices`, `vendors`, `desk` | new | Accounting |
| `get_lease` | `leases`, `desk` | P3 | Facilities |
| `get_cash_balance` | `cash_accounts`, `approval_queue`, `desk` | new | Boss, Accounting |
| `queue_payment` | reads `invoices`/`leases`, `cash_accounts`; writes `approval_queue` | new | Accounting |
| `list_approval_queue` | `approval_queue` | new | Boss, Accounting |
| `approve_payment` | writes `approval_queue`, `payments`, `cash_accounts`, `invoices`/`leases` | new | **humans only** (`backend/approve.py`) |
| `save_customer_draft` | writes `message_drafts` | new | Customer Service |

`approval_queue` and `message_drafts` are bookkeeping tables the server creates in the working copy.
A reset removes them along with everything else.

**Why a queue instead of a pay tool for agents:** the rules say a human approves every payment. So an
agent can only *queue* one, and the amount is read from the invoice or lease, never typed by the agent.
Paying is a separate tool that only a person runs.

### Safety

Guardrails already in place:
- **Payments:** agents can't pay. Amounts come from the database, not from agents, and queuing the
  same item twice is refused. The pay tool declines anything that would take checking below $0, both
  when queued (counting payments already pending) and again at approval. A declined payment stays
  declined.
- **Customer messages:** drafts only, and the tool refuses any text without the "DRAFT - NOT SENT"
  prefix. Nothing can email anyone.
- **Data access:** lookup tools open the database read-only, and each role sees only the tools its job
  needs.
- **Reset:** every full run starts from a fresh copy of the original database.

What we'd add if this were **real money**:
- **Two-person approval** above a set amount, with approver identity coming from a login, not a typed
  name.
- **Payee checks:** verify the vendor's bank details out-of-band (a phone call, not the email), and
  treat new or changed payee details as a fraud flag.
- **Limits:** daily and per-payee spending caps, and a cash floor (keep, say, one month's rent in
  reserve), not just "≥ $0".
- **Idempotent payment IDs**, so a retry can never pay twice.
- **Tamper-evident audit:** a hash-chained log in write-once storage.
- **Separate credentials** for read-only and write tools, with no write access in development.
- **Treat incoming emails and notices as untrusted input** (prompt injection), and never act on
  instructions inside them.
- **Monitoring:** alerts on declined or unusual payments.

**Token and cost limits** (`backend/agents/base.py`):
- One team-wide `UsageLimits` budget per run: **80 model requests, 400,000 total tokens, 120 tool
  calls**. Child agents share the parent's usage, so delegation can't escape the cap.
- At most **16 delegations** per run, chains at most **3 agents** deep, and repeated questions are
  answered from the first reply.
- Audit fields are capped at 300 to 600 characters so the log stays small.
- gpt-6-luna is the only model, which keeps cost per run low.

### Full run results

Run `20261014T181824-0a3f0d`: `cd backend && .venv/bin/python run_tickets.py` (reset first). It took
**142 s**, with **31 model requests, 72,667 input + 10,019 output tokens**, 8 delegations and 47 MCP
tool calls. That's well inside the 80-request / 400k-token budget. It added 99 entries to
`output/audit_trail.json`, which also keeps the 88 entries from an earlier run that was cut off when the
session closed. The Boss's report is saved in `output/boss_report.json`.

| Ticket | Decision | Status |
| --- | --- | --- |
| 101 (tee S) | 0 in stock, short 1. The restock is blocked by unpaid invoice 501 ($840, overdue), and the tee arrives 2026-09-05 if it's paid today. Invoice queued for approval (request #2). | waiting on approval |
| 102 (rent) | The notice matches lease 1: Elm City Properties, $2,400, due 2026-09-02, so 2 days away and not overdue. Rent queued first (request #1). | waiting on approval |
| 103 (20 hoodies M) | Price set at **$52.20** (10% off the $58 list, $30.20 margin over the $22 cost). 8 ship now and 12 wait on the same blocked restock. Draft sent to the club for their OK. | waiting on approval |

**Cash plan:** rent first ($3,400 → $1,000), then invoice 501 ($1,000 → **$160**). That matches the
Problem 2 analysis.

What the database shows afterward:
- 2 pending approval requests. A third `queue_payment` call was refused as a duplicate.
- 2 drafts saved with "DRAFT - NOT SENT" and `sent = 0`.
- All 3 tickets set to `waiting_on_approval`, with dated notes.
- Checking still **$3,400**, with **0 payments**: nothing is paid until a human runs `approve.py`.

Guard rails seen working:
- The depth limit stopped Boss → Inventory → Accounting from going on to Facilities.
- The earlier run refused Customer Service bouncing a question back to the Boss.

**Known issue:** in `boss_report.json` the Boss shortened the drafts and left off the
"DRAFT - NOT SENT" prefix. The drafts actually saved in `message_drafts` have it.

---

## Problem 7: Backend routes

`backend/main.py` is a FastAPI app for the React board. Start it from `backend/` with
`uvicorn main:app --reload --port 8000`. Shop data still only comes through the campus-customs MCP
server. One MCP tool was added for the board: `list_tickets` reads `tickets` and `desk` and returns every
ticket whatever its status. A team run takes minutes, so it starts in the background, only one runs at
a time, and the board polls for events.

| Route | What it does |
| --- | --- |
| `GET /api/tickets` | All 3 tickets with their `status` and an `open` / `resolved` flag (MCP `list_tickets`). |
| `POST /api/tickets/{id}/run` | Starts the agent team on that one ticket in the background and returns a `run_id`. Returns 409 if a run is already going or the ticket is resolved. |
| `GET /api/runs/{run_id}` | Run status (`running` / `done` / `error`), plus the Boss's report when it's done. |
| `GET /api/events?run_id=&since=&limit=` | Recent agent events from `output/audit_trail.json`: who said what, tool calls and results, delegations. Pass back `next_since` to get only newer ones. |
| `GET /api/approvals?status=pending` | Payments waiting for a human (or paid / declined) (MCP `list_approval_queue`). |
| `POST /api/approvals/{request_id}/approve` | A human approves or rejects a queued payment (`approved_by`, `approve`, `note`). The pay tool still declines if checking would go below $0 (MCP `approve_payment`). |
| `GET /api/cash` | Current checking balance from `cash_accounts`, plus the pending total and the balance if all were paid (MCP `get_cash_balance`). |
| `POST /api/reset` | Copies the original `campus_customs.db` over the working copy for a fresh run. Returns 409 while a run is going. |
| `GET /api/health` | Lists the MCP tools and shows whether a run is in progress. |

Purchase orders aren't modeled in the database: there's no PO table and no restock cost. So "approve a
purchase" means approving the queued invoice that unblocks the vendor's restock.

**Update (2026-10-14): model call timeout.** A ticket 101 run from the board hung for more than 5 minutes.
Accounting's first model request was dropped and never answered, and the OpenAI client's default waits
up to 600 s per attempt. `backend/config.py` now sets a **90 s timeout per model call with 2 retries**, so
a dropped call fails fast and retries. A direct test call to gpt-6-luna answered in 5 s.

**Update (2026-10-14): just two ticket statuses, open or resolved.** The five statuses (resolved,
waiting on approval, blocked, needs human, open) were confusing on the board. For example, a ticket whose
invoice had just been approved showed "blocked" because the tee was still in transit. Now:
- **resolved:** nothing is left for the shop or a person to do. Payments are approved, the draft is
  written, the decision is made. A restock already on its way doesn't keep it open; the arrival date goes
  in the note.
- **open:** it still needs someone (a payment waiting for approval, a customer's OK, or a human
  decision). The Boss lists exactly what in `still_needed` and in the ticket note.

`update_ticket` only accepts these two, as do `TicketDecision.status` in `backend/models.py`, the Boss
prompt and the board. A human can still close an open ticket with **Mark resolved** once nothing is
waiting for approval. The Problem 6 plan (`output/desk_tickets.html`) keeps its original expected
statuses as a record of what was expected at the time.

**Update (2026-10-14): runs wait for the human's approval.** When Accounting queues a payment, the run
pauses until a person clicks APPROVE or DENY (board popup or `approve.py`). Then the team finishes with the
decision in hand, so the same ticket ends the same way every time. This lives in the orchestration layer
(`wait_for_human` in `backend/agents/base.py`, a PydanticAI `process_tool_call` hook on the MCP toolset),
not in the MCP server. After `queue_payment` returns "queued", it checks `list_approval_queue` every 2 s and
gives the agent a `human_decision`: paid, denied, declined by the pay tool, or still pending after 15 minutes
(`APPROVAL_WAIT_S`). The wait start and end are both logged to the audit trail.

Test on ticket 102: rent was queued at 51 s, the run paused, and after approval the Boss marked 102
resolved. The shop was reset afterward.

**Update (2026-10-14): single-ticket runs only pay their own bill.** On a ticket 101 run, Accounting
queued ticket 102's rent first ("rent comes first") and then 101's invoice, so 101's run paid 102's rent.
Fixed in two places:
- **Code:** `run_team` looks up the ticket's own bill (`invoice_id` → that invoice, `lease_id` → that
  lease's rent). `wait_for_human` refuses any other `queue_payment` with an "out of scope" message, logs
  `payment_out_of_scope`, and never sends it to the MCP server.
- **Prompts:** Boss and Accounting count other tickets' bills only to leave room for them; they never queue
  them. A full run over all tickets can still queue everything.

Tested: on a 101 run, rent was refused and invoice 501 went through. The shop was reset afterward.

**Update (2026-10-14): run all together, and a Stop button.** New routes:

| Route | What it does |
| --- | --- |
| `POST /api/run-all` | One Boss run over every open ticket: one cash plan, specialists in parallel. Can queue every ticket's bill. |
| `POST /api/runs/{run_id}/stop` | Cancels a running run, denies any payment it queued that has no decision yet ("Stop button"), and logs `run_stopped`. |

`queue_payment` now only refuses a repeat when the **pay tool** declined it for cash. A human deny or Stop
is a one-time no. Tested: run-all started on 101, 102 and 103, and a second run was refused while it went.
Stopping mid-run ended it within seconds, auto-denied the pending $840 invoice, kept checking at $3,400,
and freed the run lock.


---

## Problem 8: Agent dashboard

A React + Vite + TypeScript board in `frontend/` that talks only to the FastAPI backend at
`http://localhost:8017`. It lets a person run the team, watch it work, approve payments and track the cash.
The full design write-up is in `output/design.md`.

**Run it:**
1. Start the backend: `cd backend && .venv/bin/uvicorn main:app --reload --port 8017`
2. Start the board: `cd frontend && npm run dev`. It opens http://localhost:5177; 5173 to 5176 are taken
   by other class apps on this machine.
3. The backend's CORS list allows only `localhost:5173` and `localhost:5177` (plus the `127.0.0.1`
   versions).

| Area | What it shows | Why |
| --- | --- | --- |
| Tickets | All 3 tickets, **OPEN** or grayed-out **✓ RESOLVED** with a green badge. Buttons: **Run all with Boss** or **Run this ticket**, plus **Mark resolved** | Pick the scope of a run and close tickets once nothing is pending |
| Agent team | Five agent cards connected by lines. The working agent glows in its own color, and both agents flash when they hand off | Makes delegation visible: who is working and who they asked |
| Live activity | What agents said, tool calls with short results, hand-offs, refused hand-offs, ⏳ approval waits, ✅ / 🚫 human decisions | The audit trail, readable as it happens |
| Ticket summary | The Boss's call (decision, numbers, still needed, draft), human decisions for this ticket, one card per agent, run totals | A short record of what each agent did on that ticket |
| Cash card | Checking in dark green on a light card. It turns red if a bill can't be paid | The number managers care about most |
| APPROVE / DENY popup | Payee, amount, reason, checking before → after, and the approver's name | Human approval is a shop rule |
| ■ Stop run | Cancels the run. Payments it queued without a decision are denied | A kill switch if something goes wrong |
| Handsome Dan | White outline doodles and a walking 'moji. All motion turns off with "reduce motion" | Yale branding; Madison asked for it |

### Deliverables from the final run

- `output/desk_tickets.html` keeps the Problem 6 **Expected** sections, now next to the **Actual**
  sections and a **Cash** ledger.
- `output/resolved_tickets.json` has, per ticket: final status, outcome, what each agent did, human
  approvals, how it was resolved, the customer draft, and the Boss's numbers.
- `output/resolved_board.html` is a double-click page with a board screenshot for each resolved ticket.
  The PNG files are in `output/resolved_board/`.

---

## Final system overview (2026-10-14)

The whole hw5 system as it stands now. The earlier sections are the history; this section is the
current state.

### Tables

`data/campus_customs.db` is never changed. All runs use the working copy `data/campus_customs_new.db`,
which **Reset** copies back from the original. The working copy has the 9 original tables (fields are in
Problem 2) plus 2 bookkeeping tables that the MCP server creates.

| Table | Rows (original) | Why it matters to the agents |
| --- | --- | --- |
| `desk` | 1 | `date_today` = 2026-08-31 is the shop's "today" for every overdue and days-until figure |
| `tickets` | 3 | The work queue; `invoice_id` / `lease_id` link each ticket to its bill |
| `inventory` | 10 | Stock per SKU and size, used to fill an order or find the shortfall |
| `pricing` | 4 | `unit_cost` is the floor for discounts, `list_price` the starting point |
| `vendors` | 3 | Who restocks what and the lead days, which give the restock dates |
| `invoices` | 1 | Bills owed. An unpaid one blocks that vendor's shipments |
| `leases` | 1 | The source of truth for rent amount and due date |
| `cash_accounts` | 1 | Checking balance ($3,400 at the start). Payments come out of it |
| `payments` | 0 | One row per approved payment, with `approved_by` = the human |
| `approval_queue` (new) | 0 | Payments waiting for a human: amount from the database, `requested_by`, pending / paid / declined, `decided_by` |
| `message_drafts` (new) | 0 | Customer drafts starting "DRAFT - NOT SENT", with `sent` always 0 |

### MCP tools (13)

The campus-customs FastMCP server in `mcp_server/server.py` is the only way agents and the backend touch
shop data. The connection is in `.mcp.json`.

| Tool | Tables | Called by |
| --- | --- | --- |
| `list_open_tickets` | `tickets`, `desk` | all five agents |
| `list_tickets` | `tickets`, `desk` | backend (board) |
| `update_ticket` | writes `tickets` (open / resolved only) | Boss, backend (Mark resolved) |
| `check_stock_and_price` | `inventory`, `pricing`, `desk` | Inventory, Accounting |
| `list_vendors` | `vendors`, `invoices`, `desk` | Inventory |
| `get_invoice_status` | `invoices`, `vendors`, `desk` | Inventory, Accounting |
| `list_invoices` | `invoices`, `vendors`, `desk` | Accounting |
| `get_lease` | `leases`, `desk` | Facilities |
| `get_cash_balance` | `cash_accounts`, `approval_queue`, `desk` | Boss, Accounting, backend |
| `queue_payment` | reads `invoices` / `leases`, `payments`, `cash_accounts`; writes `approval_queue` | Accounting |
| `list_approval_queue` | `approval_queue` | Boss, Accounting, backend |
| `approve_payment` | writes `approval_queue`, `payments`, `cash_accounts`, `invoices` / `leases` | **humans only**: board popup or `backend/approve.py` |
| `save_customer_draft` | writes `message_drafts` | Customer Service |

### The five agents

All five run on PydanticAI with **gpt-6-luna** only, through Portkey. Each gets the shared rules in
`backend/prompts/shared_rules.md` plus its own prompt, only the MCP tools its role needs, and
`ask_agent` for delegating to any other agent.

| Agent | Code / prompt | Job | MCP tools |
| --- | --- | --- | --- |
| Boss | `agents/boss.py`, `prompts/boss.md` | Reads all open tickets, routes each one, picks prices, sets open / resolved, and returns a `BossReport` | `list_open_tickets`, `get_cash_balance`, `list_approval_queue`, `update_ticket` |
| Inventory | `agents/inventory.py`, `prompts/inventory.md` | Stock vs wanted vs short; vendor and restock date; flags unpaid-invoice blocks | `check_stock_and_price`, `list_vendors`, `get_invoice_status`, `list_open_tickets` |
| Accounting | `agents/accounting.py`, `prompts/accounting.md` | Cash plan across bills, days overdue, margins; queues payments and reports the human's decision | `get_cash_balance`, `list_invoices`, `get_invoice_status`, `check_stock_and_price`, `queue_payment`, `list_approval_queue`, `list_open_tickets` |
| Facilities | `agents/facilities.py`, `prompts/facilities.md` | Checks rent notices against the lease and flags mismatches as possible scams | `get_lease`, `list_open_tickets` |
| Customer Service | `agents/customer_service.py`, `prompts/customer_service.md` | Customer drafts only, with no cash or vendor talk | `save_customer_draft`, `list_open_tickets` |

Each loop step (prompt, model request, model response with tool calls and tokens, tool results, end),
each hand-off, each approval wait, and each human decision is appended to `output/audit_trail.json`. It
now holds 982 entries across 28 runs, including test runs.

### API routes (12)

These are in `backend/main.py`. Shop data goes through MCP; the only file access is the audit trail and
the reset copy.

| Route | What it does |
| --- | --- |
| `GET /api/health` | MCP tools available, and the run in progress if any |
| `GET /api/tickets` | All tickets with status and open / resolved |
| `POST /api/tickets/{id}/run` | Runs the team on one ticket in the background and returns a `run_id` |
| `POST /api/run-all` | Runs the Boss over every open ticket in one run |
| `POST /api/runs/{run_id}/stop` | Stops a run and denies its undecided payments |
| `GET /api/runs/{run_id}` | Run status and the Boss's report |
| `GET /api/events?run_id=&since=` | New audit-trail events for the board to poll |
| `GET /api/approvals?status=` | The approval queue |
| `POST /api/approvals/{id}/approve` | Human approve or deny; logged to the audit trail |
| `POST /api/tickets/{id}/resolve` | Human marks a ticket resolved; logged to the audit trail |
| `GET /api/cash` | Checking balance, pending total, and the balance if all pending were paid |
| `POST /api/reset` | Copies the original database over the working copy; logged |

### Safety rules: where each one is enforced

The rules a mistake could cost money on are enforced in code, not just written in prompts.

| Rule | Enforced by |
| --- | --- |
| Human approval for every payment | No agent has `approve_payment`; agents can only `queue_payment`. The run waits up to 15 minutes for the human (`wait_for_human` in `agents/base.py`) |
| Never invent amounts | `queue_payment` reads the amount and payee from `invoices` / `leases`; the agent can't type them |
| No negative balance | `queue_payment` declines if checking minus pending can't cover it; `approve_payment` checks again. A pay-tool decline stays declined |
| No double payments | Duplicate pending requests are refused, and rent already paid in the last month is refused |
| A ticket run only pays its own bill | `wait_for_human` refuses `queue_payment` outside the ticket's `invoice_id` / `lease_id` and logs `payment_out_of_scope` |
| Desk date is "today"; lead times come from `vendors` | Every date is computed by the MCP tools from `desk.date_today` and `lead_days` |
| Don't email customers or vendors | No send tool exists. `save_customer_draft` requires "DRAFT - NOT SENT" and stores `sent = 0` |
| Reset before a full run | `run_tickets.py` resets automatically; the board has **Reset shop**. The original database is never written |
| Stop if something goes wrong | **■ Stop run** cancels the run and denies its undecided payments |
| No delegation loops | No asking yourself or an agent already up the chain; chains are at most 3 deep; at most 16 hand-offs per run; repeated questions reuse the first answer |
| Token and cost limits | One team budget per run: 80 model requests, 400,000 tokens, 120 tool calls. Model calls time out after 90 s with 2 retries |
| Least privilege | Each role sees only its tools. Lookups open the database read-only. CORS allows only the board |

For handling real money we'd still add: two-person approval above a set amount, approver identity from a
login instead of a typed name, payee checks done out-of-band, daily caps and a cash reserve, idempotent
payment ids, and a tamper-evident audit log.

### Final run and cash

The final run was "Run all with Boss", run `20261014T212032-d36dbf`: 134 s, 35 model calls, 96,804 tokens,
9 hand-offs plus 1 refused by the depth limit. Madison approved both payments during the run.

| Step | Change | Checking |
| --- | --- | --- |
| Start (after reset) | | $3,400.00 |
| Ticket 101: invoice 501 to Bulldog Print Co (request #1) | −$840.00 | $2,560.00 |
| Ticket 102: rent, lease 1, to Elm City Properties (request #2) | −$2,400.00 | $160.00 |
| Ticket 103: price quote only, no purchase | $0.00 | $160.00 |
| **End**: matches `cash_accounts.checking` in the working copy | | **$160.00** |

Statuses at the end of the run:
- 102 was resolved by the Boss.
- 101 and 103 were left open, waiting on customer replies. They were then marked resolved through the
  board's human route ("Madison (marked via Claude)") so all three show as resolved.

### Known issues

- **Model stalls:** gpt-6-luna through Portkey sometimes drops a request. The 90 s timeout and retries
  cover it, but a stall can still add a minute or so to a run.
- **No purchase orders:** there's no PO table or restock cost, so the 9/5 restock dates are estimates and
  the 12-hoodie reprint for 103 can't be ordered.
- **Audit trail includes testing:** it mixes real runs with development test runs (stopped runs, a scratch
  approver name). Each run has its own `run_id`; the final run is `20261014T212032-d36dbf`.

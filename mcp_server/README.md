# Campus Customs MCP server

The shared toolbox for the hw5 multi-agent team (Boss, Inventory, Accounting, Facilities, Customer
Service). Every agent works the shop's tickets through these tools instead of touching the database
directly, so they all see the same data and follow the same shop rules: `desk.date_today` is "today",
a vendor won't ship while it has an unpaid invoice, payments need a human, cash can't go negative, and
nothing is ever emailed. Built with [FastMCP](https://gofastmcp.com).

## Database

- Uses the **working copy** `../data/campus_customs_new.db` (override with the `CAMPUS_CUSTOMS_DB` env var).
- The original `../data/campus_customs.db` is never touched. Reset before a full run
  (`../backend/run_tickets.py` does it automatically): `cp ../data/campus_customs.db ../data/campus_customs_new.db`
- Tools only report what's in the database and say "not found" rather than guess.
- Two bookkeeping tables are created in the working copy on first use: `approval_queue` (payments
  waiting for a human) and `message_drafts` (unsent customer messages).

## Tools

| Tool | Reads / writes | What it does |
| --- | --- | --- |
| `list_open_tickets()` | reads `tickets`, `desk` | Every open ticket, oldest first. |
| `list_tickets()` | reads `tickets`, `desk` | Every ticket, open or resolved (for the board). |
| `update_ticket(ticket_id, status, note)` | writes `tickets` | Sets status `open` or `resolved` and appends a dated note. |
| `check_stock_and_price(sku, size?, qty_wanted?)` | reads `inventory`, `pricing`, `desk` | Stock per size, shortfall for a quantity, list price, unit cost (the discount floor), order totals. |
| `list_vendors()` | reads `vendors`, `invoices`, `desk` | Specialty, lead days, unpaid invoices, whether each vendor will ship, restock dates. |
| `get_invoice_status(invoice_id)` | reads `invoices`, `vendors`, `desk` | One invoice: days overdue, the vendor's unpaid invoices, whether it will ship, earliest arrival. |
| `list_invoices(unpaid_only?)` | reads `invoices`, `vendors`, `desk` | All (or unpaid) invoices with days overdue and totals. |
| `get_lease(lease_id)` | reads `leases`, `desk` | Landlord, monthly rent, next due date, days until due. |
| `get_cash_balance()` | reads `cash_accounts`, `approval_queue`, `desk` | Checking balance, payments waiting for approval, balance if all were paid. |
| `queue_payment(kind, ref_id, requested_by, reason)` | reads `invoices`/`leases`, `cash_accounts`; writes `approval_queue` | Puts a payment on the human approval list. Amount comes from the database. **Declines** if cash can't cover it on top of what's pending; a pay-tool decline stays declined (a human deny doesn't). Refuses duplicates and rent already paid this month. Moves no money. |
| `list_approval_queue(status?)` | reads `approval_queue` | Pending / paid / declined payment requests. |
| `approve_payment(request_id, approved_by, approve?, note?)` | writes `approval_queue`, `payments`, `cash_accounts`, `invoices` / `leases` | **Human only** (no agent is given it; use `../backend/approve.py`). Re-checks cash and declines if it would go below $0; otherwise records the payment, deducts cash, and marks the invoice paid or moves the lease due date forward a month. |
| `save_customer_draft(ticket_id, customer, message, created_by?)` | writes `message_drafts` | Saves a customer message that must start with `DRAFT - NOT SENT`. Never sends. |

## Run

From the `hw5/` folder, using the shared environment (see the top-level README):

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python mcp_server/server.py          # stdio transport
```

The connection used by Claude Code and the backend is in `../.mcp.json`. Its paths are relative to `hw5/`.

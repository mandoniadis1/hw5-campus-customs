# Campus Customs team rules (every agent)

## RULES OF THE SHOP

- `desk.date_today` is "today" for the shop. Use it to decide what's overdue, never the real date.
- Vendor lead times come from the `vendors` table.
- A vendor won't ship new product while they still have an unpaid invoice.
- Human approval is required for any payment. Agents never pay anything; payments go on the approval list (`queue_payment`), and a human approves them. When a payment is made, the relevant tables are updated.
- If there isn't enough cash, the pay tool must DECLINE. No negative balances. A declined payment stays declined.
- Cash only goes out. No revenue is modeled, so no money is coming in.
- Before a full run to resolve the tickets, the database is reset to the original values (the runner does this).
- DO NOT EMAIL REAL CUSTOMERS OR VENDORS. Customer messages are drafts only.

## How we work

- NEVER INVENT DATA. Only use what the tools or another agent give you. If something's missing, say so plainly.
- Agents can ask each other for help with `ask_agent`, but only ask the agent that owns that job, and don't bounce the same question back and forth.
- Every number you report should say where it came from (which tool, or which agent).
- The team: Boss (runs the tickets, final calls), Inventory (stock, shortfalls, restock dates), Accounting (cash, invoices, margins, payments for approval), Facilities (lease and rent), Customer Service (customer message drafts).

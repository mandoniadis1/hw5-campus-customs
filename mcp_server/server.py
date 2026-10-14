"""Campus Customs MCP server — the shared toolbox for every agent on the team.

Talks to the working copy data/campus_customs_new.db (the original data/campus_customs.db is
never touched, so the shop can be reset). Every answer comes straight from the database; if a
row doesn't exist the tool says so instead of guessing.

Shop rules the tools follow:
- desk.date_today is "today" for the shop: overdue / due-soon is measured against it, not the real clock.
- Vendor lead times come from vendors.lead_days.
- A vendor won't ship new product while it still has an unpaid invoice.
- Agents can only QUEUE a payment for human approval; the amount always comes from the database
  (invoice amount / lease rent), never from the caller. approve_payment is for humans only (the
  backend never gives it to an agent). A payment that would take cash below $0 is DECLINED and stays
  declined. Cash only goes out: nothing here adds money.
- Customer messages are saved as drafts that start with "DRAFT - NOT SENT". Nothing here sends email.

Writes land in the working copy only. Two bookkeeping tables are created there on first use:
approval_queue (payments waiting for a human) and message_drafts (unsent customer messages).

Run (stdio):  python server.py
"""

from __future__ import annotations

import os
import sqlite3
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

DB_PATH = Path(
    os.getenv("CAMPUS_CUSTOMS_DB", Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db")
)

mcp = FastMCP("campus-customs")


def _read() -> sqlite3.Connection:
    """Read-only connection: these lookup tools can never change the shop's data."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _write() -> sqlite3.Connection:
    """Read-write connection for the few tools that record something. Creates the bookkeeping tables."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS approval_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,              -- 'invoice' or 'rent'
            ref_id INTEGER NOT NULL,         -- invoices.id or leases.id
            payee TEXT NOT NULL,
            amount REAL NOT NULL,            -- copied from the database, never from the caller
            account TEXT NOT NULL,
            reason TEXT,
            requested_by TEXT NOT NULL,      -- which agent asked
            status TEXT NOT NULL,            -- pending / paid / declined
            decided_by TEXT,
            decision_note TEXT,
            created_at TEXT NOT NULL,
            decided_at TEXT
        );
        CREATE TABLE IF NOT EXISTS message_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            customer TEXT NOT NULL,
            body TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0  -- always 0: this system never sends
        );
        """
    )
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _add_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def _today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise ValueError("desk.date_today is missing, so the shop has no 'today' to measure against.")
    return date.fromisoformat(row["date_today"])


def _unpaid(status: str) -> bool:
    return status.strip().lower() != "paid"


@mcp.tool
def check_stock_and_price(sku: str, size: str | None = None, qty_wanted: int | None = None) -> dict:
    """Stock on hand and pricing for a product, optionally for one size and a requested quantity.

    Use for customer orders (can we fill it?) and discount requests (how low can the price go?).
    Reads inventory and pricing. The price floor is unit_cost: selling below it loses money.

    Args:
        sku: Product SKU, e.g. "CC-HOOD-NAVY".
        size: Size to check, e.g. "M" or "OS". Leave empty to see every size.
        qty_wanted: How many the customer wants, to compute the shortfall and order totals.
    """
    with _read() as conn:
        today = _today(conn)
        rows = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid", (sku,)
        ).fetchall()
        price = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()

    if not rows:
        return {"found": False, "error": f"No inventory rows for SKU {sku!r}."}
    sizes = [dict(r) for r in rows]
    result: dict = {
        "found": True,
        "date_today": today.isoformat(),
        "sku": sku,
        "name": sizes[0]["name"],
        "all_sizes": [{k: s[k] for k in ("size", "qty", "location")} for s in sizes],
        "pricing": dict(price) if price else None,
    }
    if price is None:
        result["pricing_note"] = f"No pricing row for {sku!r}; do not quote a price."
    else:
        cost, list_price = price["unit_cost"], price["list_price"]
        result["max_discount_pct_above_cost"] = round((1 - cost / list_price) * 100, 1) if list_price else None

    if size is not None:
        match = next((s for s in sizes if s["size"].lower() == size.lower()), None)
        if match is None:
            result["size_error"] = f"{sku!r} has no size {size!r}. Sizes on file: {[s['size'] for s in sizes]}."
            return result
        result["size"] = match["size"]
        result["qty_in_stock"] = match["qty"]
        result["location"] = match["location"]
        if qty_wanted is not None:
            result["qty_wanted"] = qty_wanted
            result["can_fill_from_stock"] = match["qty"] >= qty_wanted
            result["shortfall"] = max(qty_wanted - match["qty"], 0)
            if price is not None:
                result["total_at_list"] = round(qty_wanted * price["list_price"], 2)
                result["total_at_cost"] = round(qty_wanted * price["unit_cost"], 2)
    return result


@mcp.tool
def get_invoice_status(invoice_id: int) -> dict:
    """An invoice, whether it's overdue, and whether its vendor will ship new product.

    Use when an order is waiting on a restock. Reads invoices, vendors and desk. A vendor won't
    ship while it has any unpaid invoice, so this also lists all of that vendor's unpaid invoices
    and the restock date (today + lead_days) once they're all paid.

    Args:
        invoice_id: The invoice id, e.g. from a ticket's invoice_id field.
    """
    with _read() as conn:
        today = _today(conn)
        inv = conn.execute(
            "SELECT id, vendor_id, amount, due_date, status, description FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        if inv is None:
            return {"found": False, "error": f"No invoice with id {invoice_id}."}
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (inv["vendor_id"],)
        ).fetchone()
        vendor_invoices = conn.execute(
            "SELECT id, amount, due_date, status, description FROM invoices WHERE vendor_id = ? ORDER BY due_date",
            (inv["vendor_id"],),
        ).fetchall()

    due = date.fromisoformat(inv["due_date"])
    unpaid = [dict(v) for v in vendor_invoices if _unpaid(v["status"])]
    result: dict = {
        "found": True,
        "date_today": today.isoformat(),
        "invoice": dict(inv),
        "is_unpaid": _unpaid(inv["status"]),
        "days_overdue": (today - due).days if _unpaid(inv["status"]) and due < today else 0,
        "vendor": dict(vendor) if vendor else None,
        "vendor_unpaid_invoices": unpaid,
        "vendor_unpaid_total": round(sum(v["amount"] for v in unpaid), 2),
        "vendor_will_ship": not unpaid,
    }
    if vendor is None:
        result["vendor_error"] = f"Invoice points to vendor {inv['vendor_id']}, which is not in vendors."
        return result
    lead = timedelta(days=vendor["lead_days"])
    if unpaid:
        result["ship_blocked_reason"] = (
            f"{vendor['name']} has {len(unpaid)} unpaid invoice(s) totaling ${result['vendor_unpaid_total']:.2f} "
            "and won't ship until they're paid."
        )
        result["earliest_arrival_if_paid_today"] = (today + lead).isoformat()
    else:
        result["earliest_arrival_if_ordered_today"] = (today + lead).isoformat()
    return result


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """The lease on file: landlord, rent amount, and how many days until (or since) rent is due.

    Use to check a rent notice against the real lease before anyone pays: the amount and due date
    come from here, never from the notice. Reads leases and desk.

    Args:
        lease_id: The lease id, e.g. from a ticket's lease_id field.
    """
    with _read() as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?", (lease_id,)
        ).fetchone()
    if lease is None:
        return {"found": False, "error": f"No lease with id {lease_id}."}
    days = (date.fromisoformat(lease["next_due"]) - today).days
    return {
        "found": True,
        "date_today": today.isoformat(),
        "lease": dict(lease),
        "days_until_due": days,
        "is_overdue": days < 0,
    }


# ---------- Tickets ----------

TICKET_STATUSES = ("open", "resolved")  # resolved = nothing left for anyone to do; open = still needs someone


@mcp.tool
def list_open_tickets() -> dict:
    """Every ticket still open, oldest first, with the shop's date_today. Reads tickets and desk.

    Read these all together before acting: the tickets share the same cash.
    """
    with _read() as conn:
        today = _today(conn)
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at "
            "FROM tickets WHERE status = 'open' ORDER BY created_at"
        ).fetchall()
    return {"date_today": today.isoformat(), "count": len(rows), "tickets": [dict(r) for r in rows]}


@mcp.tool
def list_tickets() -> dict:
    """Every ticket, open or resolved, with an open/resolved flag. Reads tickets and desk. For dashboards; agents work from list_open_tickets.
    """
    with _read() as conn:
        today = _today(conn)
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at "
            "FROM tickets ORDER BY id"
        ).fetchall()
    tickets = [dict(r) | {"state": "resolved" if r["status"] == "resolved" else "open"} for r in rows]
    return {"date_today": today.isoformat(), "count": len(tickets), "tickets": tickets}


@mcp.tool
def update_ticket(ticket_id: int, status: Literal["open", "resolved"], note: str) -> dict:
    """Set a ticket to open or resolved and append a dated note. Writes tickets.

    resolved = nothing is left for the shop or a person to do (payments approved, drafts written,
    decision made; a delivery already on its way doesn't keep it open). open = it still needs someone:
    a payment waiting for approval, a customer OK, or a human decision. Say which in the note.

    Args:
        ticket_id: The ticket to update.
        status: "open" or "resolved".
        note: The decision and the numbers behind it; if open, exactly what it's waiting on.
    """
    if status not in TICKET_STATUSES:
        return {"ok": False, "error": f"status must be one of {TICKET_STATUSES}"}
    with _write() as conn:
        today = _today(conn)
        row = conn.execute("SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        notes = (row["notes"] or "").rstrip()
        notes = f"{notes}\n[{today.isoformat()}] {status}: {note.strip()}".strip()
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
    return {"ok": True, "ticket_id": ticket_id, "old_status": row["status"], "new_status": status}


# ---------- Money ----------


def _pending(conn: sqlite3.Connection) -> list[dict]:
    if not _has_table(conn, "approval_queue"):
        return []
    return [dict(r) for r in conn.execute("SELECT * FROM approval_queue WHERE status = 'pending' ORDER BY id")]


@mcp.tool
def get_cash_balance() -> dict:
    """Cash on hand, payments already waiting for approval, and what would be left if all were approved.

    Reads cash_accounts, approval_queue and desk. Cash only goes out in this shop (no revenue is modeled).
    """
    with _read() as conn:
        today = _today(conn)
        accounts = [dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name")]
        pending = _pending(conn)
    if not accounts:
        return {"found": False, "error": "No rows in cash_accounts."}
    pending_total = round(sum(p["amount"] for p in pending), 2)
    total = round(sum(a["balance"] for a in accounts), 2)
    return {
        "found": True,
        "date_today": today.isoformat(),
        "accounts": accounts,
        "total_balance": total,
        "pending_approvals": [{k: p[k] for k in ("id", "kind", "ref_id", "payee", "amount")} for p in pending],
        "pending_total": pending_total,
        "balance_if_all_pending_paid": round(total - pending_total, 2),
    }


@mcp.tool
def list_invoices(unpaid_only: bool = True) -> dict:
    """All invoices (or only unpaid ones) with vendor name, lead time, and days overdue vs date_today.

    Reads invoices, vendors and desk.

    Args:
        unpaid_only: True (default) to skip invoices already marked paid.
    """
    with _read() as conn:
        today = _today(conn)
        rows = conn.execute(
            "SELECT i.id, i.vendor_id, v.name AS vendor, v.lead_days, i.amount, i.due_date, i.status, i.description "
            "FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id ORDER BY i.due_date"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        unpaid = _unpaid(d["status"])
        if unpaid_only and not unpaid:
            continue
        due = date.fromisoformat(d["due_date"])
        d["days_overdue"] = (today - due).days if unpaid and due < today else 0
        out.append(d)
    return {
        "date_today": today.isoformat(),
        "count": len(out),
        "total_amount": round(sum(i["amount"] for i in out), 2),
        "overdue_count": sum(1 for i in out if i["days_overdue"] > 0),
        "invoices": out,
    }


@mcp.tool
def list_vendors() -> dict:
    """Every vendor with its specialty, lead time, unpaid invoices, and whether it will ship right now.

    Reads vendors, invoices and desk. There is no SKU-to-vendor table: match a product to a vendor by
    specialty (e.g. apparel) or by an existing invoice's description, and say which you used.
    """
    with _read() as conn:
        today = _today(conn)
        vendors = [dict(r) for r in conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")]
        invoices = [dict(r) for r in conn.execute("SELECT id, vendor_id, amount, status, description FROM invoices")]
    for v in vendors:
        unpaid = [i for i in invoices if i["vendor_id"] == v["id"] and _unpaid(i["status"])]
        v["unpaid_invoices"] = [{k: i[k] for k in ("id", "amount", "description")} for i in unpaid]
        v["will_ship"] = not unpaid
        v["restock_date_if_ordered_today"] = (today + timedelta(days=v["lead_days"])).isoformat() if not unpaid else None
        v["restock_date_once_paid_today"] = (today + timedelta(days=v["lead_days"])).isoformat()
    return {"date_today": today.isoformat(), "vendors": vendors}


def _payable(conn: sqlite3.Connection, kind: str, ref_id: int) -> tuple[dict | None, str | None]:
    """(payee, amount, account) for an invoice or rent, read from the database, or an error."""
    if kind == "invoice":
        r = conn.execute(
            "SELECT i.amount, i.status, v.name FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (ref_id,),
        ).fetchone()
        if r is None:
            return None, f"No invoice with id {ref_id}."
        if not _unpaid(r["status"]):
            return None, f"Invoice {ref_id} is already paid."
        return {"payee": r["name"] or f"vendor of invoice {ref_id}", "amount": r["amount"]}, None
    if kind == "rent":
        r = conn.execute("SELECT landlord, monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
        if r is None:
            return None, f"No lease with id {ref_id}."
        return {"payee": r["landlord"], "amount": r["monthly_rent"]}, None
    return None, "kind must be 'invoice' or 'rent'."


@mcp.tool
def queue_payment(kind: Literal["invoice", "rent"], ref_id: int, requested_by: str, reason: str) -> dict:
    """Put a payment on the list for HUMAN approval. Does not move any money.

    The amount and payee are read from the database (invoice amount or lease rent), never supplied by
    the caller. DECLINES if checking couldn't cover it on top of payments already waiting, and a declined
    payment stays declined. Reads invoices/leases, cash_accounts; writes approval_queue.

    Args:
        kind: "invoice" (pay a vendor invoice) or "rent" (pay a lease's monthly rent).
        ref_id: invoices.id for kind="invoice", leases.id for kind="rent".
        requested_by: The agent asking, e.g. "Accounting".
        reason: Why it should be paid, with the ticket number.
    """
    with _write() as conn:
        today = _today(conn)
        payable, error = _payable(conn, kind, ref_id)
        if error:
            return {"queued": False, "error": error}
        prior = conn.execute(
            "SELECT id, status, decided_by FROM approval_queue WHERE kind = ? AND ref_id = ? AND status IN ('pending', 'declined') ORDER BY id DESC",
            (kind, ref_id),
        ).fetchone()
        if prior and prior["status"] == "pending":
            return {"queued": False, "error": f"Already waiting for approval as request #{prior['id']}."}
        # Shop rule: if the PAY TOOL declined it (not enough cash), it stays declined. A human's deny or the
        # board's Stop button is a one-time "no", so a later run may ask again.
        if prior and prior["status"] == "declined" and prior["decided_by"] == "pay tool":
            return {"queued": False, "error": f"Request #{prior['id']} was declined by the pay tool and stays declined. A human must decide."}
        if kind == "rent":
            # One rent payment per month: if this lease's rent was paid within the last month (by the
            # shop's date), the current period is covered and the next one isn't due yet.
            month_ago = date(today.year - (today.month == 1), (today.month - 2) % 12 + 1, min(today.day, 28))
            paid = conn.execute(
                "SELECT paid_at FROM payments WHERE kind = 'rent' AND ref_id = ? AND paid_at > ? ORDER BY paid_at DESC",
                (ref_id, month_ago.isoformat()),
            ).fetchone()
            if paid:
                nxt = conn.execute("SELECT next_due FROM leases WHERE id = ?", (ref_id,)).fetchone()["next_due"]
                return {"queued": False, "error": f"Rent for lease {ref_id} was already paid on {paid['paid_at']}; next due {nxt}."}
        acct = conn.execute("SELECT name, balance FROM cash_accounts WHERE name = 'checking'").fetchone()
        if acct is None:
            return {"queued": False, "error": "No 'checking' row in cash_accounts."}
        pending_total = sum(p["amount"] for p in _pending(conn))
        after = acct["balance"] - pending_total - payable["amount"]
        status, note = ("pending", None) if after >= 0 else (
            "declined",
            f"Not enough cash: checking ${acct['balance']:.2f} minus ${pending_total:.2f} already pending "
            f"leaves ${acct['balance'] - pending_total:.2f}, short of ${payable['amount']:.2f}.",
        )
        cur = conn.execute(
            "INSERT INTO approval_queue (kind, ref_id, payee, amount, account, reason, requested_by, status, "
            "decided_by, decision_note, created_at, decided_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (kind, ref_id, payable["payee"], payable["amount"], acct["name"], reason.strip(), requested_by.strip(),
             status, "pay tool" if status == "declined" else None, note, _now(), _now() if note else None),
        )
    return {
        "queued": status == "pending",
        "declined": status == "declined",
        "request_id": cur.lastrowid,
        "kind": kind,
        "ref_id": ref_id,
        "payee": payable["payee"],
        "amount": payable["amount"],
        "date_today": today.isoformat(),
        "checking_balance": acct["balance"],
        "pending_before": round(pending_total, 2),
        "checking_after_all_pending": round(after, 2) if status == "pending" else None,
        "decline_reason": note,
        "needs": "human approval (approve_payment)" if status == "pending" else None,
    }


@mcp.tool
def list_approval_queue(status: Literal["pending", "paid", "declined", "all"] = "pending") -> dict:
    """Payments on the approval list. Reads approval_queue.

    Args:
        status: pending (default), paid, declined, or all.
    """
    with _read() as conn:
        if not _has_table(conn, "approval_queue"):
            return {"count": 0, "requests": []}
        q = "SELECT * FROM approval_queue" + ("" if status == "all" else " WHERE status = ?") + " ORDER BY id"
        rows = [dict(r) for r in conn.execute(q, () if status == "all" else (status,))]
    return {"count": len(rows), "total": round(sum(r["amount"] for r in rows), 2), "requests": rows}


@mcp.tool
def approve_payment(request_id: int, approved_by: str, approve: bool = True, note: str = "") -> dict:
    """HUMAN ONLY. Approve (pay) or reject a queued payment. Agents are never given this tool.

    On approve: re-checks cash and DECLINES if checking would go below $0; otherwise records the
    payment in payments, takes it out of cash_accounts, and marks the invoice paid (or moves the
    lease's next_due forward one month). Writes approval_queue, payments, cash_accounts, invoices/leases.

    Args:
        request_id: The approval_queue id.
        approved_by: The human's name (recorded in payments.approved_by).
        approve: True to pay, False to reject.
        note: Optional reason.
    """
    if not approved_by.strip():
        return {"ok": False, "error": "approved_by (a human's name) is required."}
    with _write() as conn:
        today = _today(conn)
        req = conn.execute("SELECT * FROM approval_queue WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"ok": False, "error": f"No approval request #{request_id}."}
        if req["status"] != "pending":
            return {"ok": False, "error": f"Request #{request_id} is already {req['status']}."}
        if not approve:
            conn.execute(
                "UPDATE approval_queue SET status='declined', decided_by=?, decision_note=?, decided_at=? WHERE id=?",
                (approved_by, note or "rejected by human", _now(), request_id),
            )
            return {"ok": True, "request_id": request_id, "status": "declined"}
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],)).fetchone()
        if acct is None or acct["balance"] - req["amount"] < 0:
            reason = f"Not enough cash in {req['account']} (${acct['balance'] if acct else 0:.2f}) for ${req['amount']:.2f}."
            conn.execute(
                "UPDATE approval_queue SET status='declined', decided_by='pay tool', decision_note=?, decided_at=? WHERE id=?",
                (reason, _now(), request_id),
            )
            return {"ok": False, "request_id": request_id, "status": "declined", "error": reason}
        new_balance = round(acct["balance"] - req["amount"], 2)
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
            (req["kind"], req["ref_id"], req["amount"], req["account"], today.isoformat(), approved_by),
        )
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today.isoformat(), req["account"]))
        if req["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            updated = f"invoice {req['ref_id']} marked paid"
        else:
            due = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()["next_due"]
            nxt = _add_month(date.fromisoformat(due)).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (nxt, req["ref_id"]))
            updated = f"lease {req['ref_id']} next_due moved {due} -> {nxt}"
        conn.execute(
            "UPDATE approval_queue SET status='paid', decided_by=?, decision_note=?, decided_at=? WHERE id=?",
            (approved_by, note or None, _now(), request_id),
        )
    return {"ok": True, "request_id": request_id, "status": "paid", "payment_id": cur.lastrowid,
            "amount": req["amount"], "checking_balance": new_balance, "updated": updated}


# ---------- Customer messages (drafts only) ----------

DRAFT_PREFIX = "DRAFT - NOT SENT"


@mcp.tool
def save_customer_draft(ticket_id: int, customer: str, message: str, created_by: str = "Customer Service") -> dict:
    """Save a customer message as an unsent draft. NEVER sends anything. Writes message_drafts.

    The message must start with "DRAFT - NOT SENT"; it's rejected otherwise.

    Args:
        ticket_id: The ticket the message is about.
        customer: The customer's name as it appears on the ticket.
        message: The full draft text, starting with "DRAFT - NOT SENT".
        created_by: Which agent wrote it.
    """
    if not message.lstrip().startswith(DRAFT_PREFIX):
        return {"saved": False, "error": f'Draft must start with "{DRAFT_PREFIX}".'}
    with _write() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"saved": False, "error": f"No ticket with id {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO message_drafts (ticket_id, customer, body, created_by, created_at) VALUES (?,?,?,?,?)",
            (ticket_id, customer.strip(), message.strip(), created_by, _now()),
        )
    return {"saved": True, "draft_id": cur.lastrowid, "sent": False, "note": "Saved as a draft. Nothing was emailed."}


if __name__ == "__main__":
    mcp.run()

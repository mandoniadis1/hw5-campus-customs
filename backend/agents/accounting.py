"""Accounting: cash, invoices, margins; gets payments ready for human approval (never pays)."""

from agents.base import make_agent

ROLE_TOOLS = {
    "get_cash_balance",
    "list_invoices",
    "get_invoice_status",
    "check_stock_and_price",
    "queue_payment",
    "list_approval_queue",
    "list_open_tickets",
}

agent = make_agent("Accounting", "accounting.md", ROLE_TOOLS)

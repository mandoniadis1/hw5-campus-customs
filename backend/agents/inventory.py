"""Inventory: stock by SKU and size, shortfalls, which vendor can restock and when (or why it's blocked)."""

from agents.base import make_agent

ROLE_TOOLS = {"check_stock_and_price", "list_vendors", "get_invoice_status", "list_open_tickets"}

agent = make_agent("Inventory", "inventory.md", ROLE_TOOLS)

"""Customer Service: writes customer messages as drafts only ("DRAFT - NOT SENT"); never sends."""

from agents.base import make_agent

ROLE_TOOLS = {"save_customer_draft", "list_open_tickets"}

agent = make_agent("Customer Service", "customer_service.md", ROLE_TOOLS)

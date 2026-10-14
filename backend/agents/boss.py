"""Boss: reads every open ticket, routes each one to the right agents, and makes the final calls."""

from agents.base import make_agent
from models import BossReport

ROLE_TOOLS = {"list_open_tickets", "get_cash_balance", "list_approval_queue", "update_ticket"}

agent = make_agent("Boss", "boss.md", ROLE_TOOLS, output_type=BossReport)

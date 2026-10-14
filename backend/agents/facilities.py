"""Facilities: the shop space. Checks rent notices against the lease and flags mismatches as possible scams."""

from agents.base import make_agent

ROLE_TOOLS = {"get_lease", "list_open_tickets"}

agent = make_agent("Facilities", "facilities.md", ROLE_TOOLS)

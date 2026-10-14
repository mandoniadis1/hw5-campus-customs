"""The Campus Customs agent team. Importing this package registers all five roles."""

from agents import accounting, boss, customer_service, facilities, inventory  # noqa: F401
from agents.base import AGENTS, MCP, TeamDeps, TeamState, run_agent  # noqa: F401

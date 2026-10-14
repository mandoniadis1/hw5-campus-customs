"""Data types for the Campus Customs agent team."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
TicketStatus = Literal["open", "resolved"]


class ApprovalItem(BaseModel):
    """A payment waiting on a human, as queued on the MCP server."""

    request_id: int | None = Field(None, description="approval_queue id from queue_payment, if it was queued")
    what: str = Field(description="e.g. 'Rent, lease 1' or 'Invoice 501, Bulldog Print Co'")
    amount: float | None = None
    status: Literal["pending", "declined", "not_queued"] = "pending"


class TicketDecision(BaseModel):
    ticket_id: int
    decision: str = Field(description="What we're doing about the ticket, in one or two sentences")
    numbers: list[str] = Field(description="The figures behind the decision, each from a tool or an agent")
    approvals_needed: list[ApprovalItem] = Field(default_factory=list)
    customer_draft: str | None = Field(None, description="Customer Service's draft, if one was written")
    agents_consulted: list[AgentName] = Field(default_factory=list)
    status: TicketStatus = Field(description="resolved only if nothing is left for anyone to do; otherwise open")
    still_needed: list[str] = Field(default_factory=list, description="If open: exactly what it's waiting on (e.g. 'Approve request #1, $840')")


class BossReport(BaseModel):
    """The Boss's final answer for a full run over the open tickets."""

    date_today: str = Field(description="desk.date_today, the shop's today")
    cash_plan: list[str] = Field(description="Every payment in priority order and checking left after each one")
    tickets: list[TicketDecision]
    missing_info: list[str] = Field(default_factory=list, description="Anything a tool or agent couldn't provide")


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json. Short summaries only."""

    run_id: str
    step: int
    timestamp: str
    elapsed_s: float
    event: str  # run_start, user_prompt, model_request, model_response, delegation_*, run_end, error
    agent: str | None = None
    chain: list[str] | None = None  # delegation path, e.g. ["Boss", "Inventory"]
    model: str | None = None
    text: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_returns: list[dict[str, Any]] | None = None
    usage: dict[str, int] | None = None
    detail: dict[str, Any] | None = None

"""Run the Campus Customs agent team: all open tickets, or just one. Used by run_tickets.py and main.py."""

from __future__ import annotations

from pathlib import Path

from agents import MCP, TeamDeps, TeamState, run_agent
from audit import AuditTrail, short
from config import MODEL_NAME, WORKING_DB, mcp_client
from models import BossReport

REPORT = Path(__file__).resolve().parent.parent / "output" / "boss_report.json"

ALL_TICKETS = "Work all the open tickets: read them all first, delegate, decide, update each ticket, and give me the report."
ONE_TICKET = (
    "Work ticket {id} only. Read all open tickets first so you know the shared cash picture, but only delegate "
    "for ticket {id}, only update ticket {id}, and only include ticket {id} in the report."
)


async def run_team(ticket_id: int | None = None, trail: AuditTrail | None = None) -> tuple[BossReport, TeamState]:
    """Boss + team on the current working copy. Every step goes to output/audit_trail.json."""
    trail = trail or AuditTrail()
    state = TeamState(trail=trail, ticket_id=ticket_id)
    if ticket_id is not None:
        # A single-ticket run may only queue that ticket's own bill: its invoice or its lease's rent.
        async with mcp_client() as client:
            tickets = (await client.call_tool("list_tickets", {})).structured_content["tickets"]
        t = next((x for x in tickets if x["id"] == ticket_id), {})
        state.payable = {("invoice", t["invoice_id"])} if t.get("invoice_id") else set()
        if t.get("lease_id"):
            state.payable.add(("rent", t["lease_id"]))
    kickoff = ALL_TICKETS if ticket_id is None else ONE_TICKET.format(id=ticket_id)
    limits = state.limits
    await trail.log(
        "run_start", agent="Boss", model=MODEL_NAME,
        detail={"db": WORKING_DB.name, "ticket_id": ticket_id,
                "payable": sorted(f"{k} {r}" for k, r in state.payable) if state.payable is not None else "any", "limits": {
            "request_limit": limits.request_limit, "total_tokens_limit": limits.total_tokens_limit,
            "tool_calls_limit": limits.tool_calls_limit}},
    )
    try:
        async with MCP:  # one MCP connection for the whole team
            report = await run_agent("Boss", kickoff, TeamDeps(state=state, chain=("Boss",)))
    except Exception as exc:
        await trail.log("error", agent="Boss", text=short(exc, 600))
        raise
    REPORT.write_text(report.model_dump_json(indent=2) + "\n")
    await trail.log("run_end", agent="Boss", detail={"ticket_id": ticket_id, "delegations": state.delegations})
    return report, state

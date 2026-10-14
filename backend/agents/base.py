"""Shared machinery for the five Campus Customs agents.

- One MCP connection (campus-customs, from hw5/.mcp.json) is shared by everyone. Each agent sees only
  the MCP tools its role needs (`ROLE_TOOLS` in each role file); `approve_payment` is never given to
  any agent, because paying is a human decision. There is no other shop-tools layer: every shop fact
  comes from an MCP tool call.
- Full connectivity: every agent has `ask_agent`, so any agent can delegate to any other. Guard rails
  stop loops: no asking yourself, no asking an agent already up the current chain (A → B → A), a
  maximum chain depth, a team-wide delegation cap, and an identical question to the same agent is
  answered from the first reply instead of being asked again.
- Every agent-loop step (prompt in, model request, model response with tool calls and tokens, tool
  results, end) and every delegation is appended to output/audit_trail.json.
- One UsageLimits budget covers the whole team for a run: child agents share the parent's usage.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import RunUsage, UsageLimits

from audit import AuditTrail, short
from config import MODEL_NAME, build_mcp_toolset, build_model
from models import AgentName

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
SHARED_RULES = (PROMPTS / "shared_rules.md").read_text(encoding="utf-8")

MAX_CHAIN_DEPTH = 3  # e.g. Boss → Facilities → Accounting, and no deeper
MAX_DELEGATIONS = 16  # team-wide per run
TEAM_LIMITS = UsageLimits(request_limit=80, total_tokens_limit=400_000, tool_calls_limit=120)
HUMAN_ONLY_TOOLS = {"approve_payment"}
# When an agent queues a payment, the run waits here for the human's APPROVE / DENY (board popup or
# approve.py), so the team always finishes with the human's decision in hand and the outcome is the same
# every run. After this long with no decision, the agent is told it's still pending.
APPROVAL_WAIT_S = int(os.getenv("APPROVAL_WAIT_S", "900"))
APPROVAL_POLL_S = 2


def _as_dict(result: Any) -> Any:
    if isinstance(result, str):
        try:
            return json.loads(result)
        except ValueError:
            return result
    return result


async def wait_for_human(ctx: RunContext["TeamDeps"], call_tool, name: str, args: dict) -> Any:
    """Wrap every MCP tool call. queue_payment: refuse bills outside this run's ticket, and after a
    payment is queued, hold the tool call until a human decides."""
    state = ctx.deps.state
    if name == "queue_payment" and state.payable is not None and (args.get("kind"), args.get("ref_id")) not in state.payable:
        reason = (
            f"Out of scope: this run is only for ticket {state.ticket_id}, and {args.get('kind')} {args.get('ref_id')} "
            "belongs to another ticket. Don't queue it; just leave enough cash for it and say so in your report."
        )
        await state.trail.log("payment_out_of_scope", agent=ctx.deps.me, chain=list(ctx.deps.chain),
                              detail={"kind": args.get("kind"), "ref_id": args.get("ref_id"), "ticket_id": state.ticket_id})
        return {"queued": False, "error": reason}
    result = _as_dict(await call_tool(name, args))
    if name != "queue_payment" or not isinstance(result, dict) or not result.get("queued"):
        return result
    deps = ctx.deps
    rid = result["request_id"]
    who = {"request_id": rid, "payee": result.get("payee"), "amount": result.get("amount"), "kind": result.get("kind")}
    await deps.state.trail.log("approval_wait_start", agent=deps.me, chain=list(deps.chain), detail=who)
    print(f"Waiting for a human to approve request #{rid} (${result.get('amount')} to {result.get('payee')}): "
          f"use the board's popup or `approve.py {rid} --by NAME`", file=sys.stderr, flush=True)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + APPROVAL_WAIT_S
    req: dict = {}
    while True:
        queue = _as_dict(await call_tool("list_approval_queue", {"status": "all"}))
        req = next((r for r in queue.get("requests", []) if r["id"] == rid), {})
        if req.get("status", "pending") != "pending" or loop.time() >= deadline:
            break
        await asyncio.sleep(APPROVAL_POLL_S)
    status = req.get("status", "pending")
    if status == "paid":
        outcome = f"APPROVED and paid by {req.get('decided_by')}."
    elif status == "declined" and req.get("decided_by") == "pay tool":
        outcome = f"The pay tool DECLINED it: {req.get('decision_note')}. It stays declined."
    elif status == "declined":
        outcome = f"DENIED by {req.get('decided_by')}" + (f": {req['decision_note']}" if req.get("decision_note") else ".")
    else:
        outcome = f"No human decision after {APPROVAL_WAIT_S // 60} minutes; it is still pending approval."
    await deps.state.trail.log("approval_wait_end", agent=deps.me, chain=list(deps.chain), detail={**who, "status": status, "outcome": outcome})
    return {**result, "human_decision": {"status": status, "decided_by": req.get("decided_by"), "note": req.get("decision_note"), "outcome": outcome}}


MCP = build_mcp_toolset(process_tool_call=wait_for_human)  # connects when entered (once per run)
AGENTS: dict[str, Agent] = {}


@dataclass
class TeamState:
    """Shared by every agent in one run."""

    trail: AuditTrail
    ticket_id: int | None = None  # set for a single-ticket run
    # Payments this run may queue, as (kind, ref_id). None = any (full run over all tickets).
    payable: set[tuple[str, int]] | None = None
    limits: UsageLimits = field(default_factory=lambda: TEAM_LIMITS)
    delegations: int = 0
    answers: dict[tuple[str, str], asyncio.Future] = field(default_factory=dict)


@dataclass
class TeamDeps:
    state: TeamState
    chain: tuple[str, ...] = ()  # delegation path ending with the agent that's running

    @property
    def me(self) -> str:
        return self.chain[-1]


def make_agent(name: AgentName, prompt_file: str, mcp_tools: set[str], output_type: Any = str) -> Agent:
    """Build a role agent: shared rules + its own prompt, its slice of the MCP tools, and ask_agent."""
    allowed = set(mcp_tools) - HUMAN_ONLY_TOOLS
    agent = Agent(
        instructions=f"{SHARED_RULES}\n\n---\n\n{(PROMPTS / prompt_file).read_text(encoding='utf-8')}\n\nYou are {name}.",
        deps_type=TeamDeps,
        output_type=output_type,
        toolsets=[MCP.filtered(lambda ctx, tool_def: tool_def.name in allowed)],
        tools=[ask_agent],
        name=name.lower().replace(" ", "_"),
        retries=3,
    )
    AGENTS[name] = agent
    return agent


async def ask_agent(ctx: RunContext[TeamDeps], agent: AgentName, request: str) -> str:
    """Ask a teammate to do the part of the work they own, and get their report back.

    Only ask the agent that owns the job: Inventory (stock, shortfalls, vendors, restock dates),
    Accounting (cash, invoices, margins, queuing payments for approval), Facilities (lease, rent),
    Customer Service (customer message drafts), Boss (final calls). Include every fact they need
    (ticket number, SKU, size, quantity, names, approved price) so they don't have to ask back.

    Args:
        agent: Who to ask.
        request: What you need from them, with the details.
    """
    deps, state = ctx.deps, ctx.deps.state
    me = deps.me
    refusal = None
    if agent == me:
        refusal = "You can't delegate to yourself. Do it with your own tools."
    elif agent in deps.chain:
        refusal = (
            f"{agent} is already working on this further up the chain ({' → '.join(deps.chain)}). "
            "Don't bounce it back; answer with what you have and say what's missing."
        )
    elif len(deps.chain) >= MAX_CHAIN_DEPTH:
        refusal = f"Delegation depth limit ({MAX_CHAIN_DEPTH}) reached. Answer with what you have."
    elif state.delegations >= MAX_DELEGATIONS:
        refusal = f"Team delegation limit ({MAX_DELEGATIONS}) reached for this run. Answer with what you have."
    if refusal:
        await state.trail.log("delegation_refused", agent=me, chain=list(deps.chain), detail={"to": agent, "request": short(request), "reason": refusal})
        return refusal

    key = (agent, " ".join(request.lower().split()))
    if key in state.answers:  # same question to the same agent: reuse the first answer
        await state.trail.log("delegation_reused", agent=me, chain=list(deps.chain), detail={"to": agent, "request": short(request)})
        return await state.answers[key]

    state.delegations += 1
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    state.answers[key] = future
    await state.trail.log("delegation_start", agent=me, chain=list(deps.chain), detail={"to": agent, "request": short(request, 600)})
    try:
        reply = await run_agent(agent, request, replace(deps, chain=(*deps.chain, agent)), usage=ctx.usage)
        reply = reply if isinstance(reply, str) else reply.model_dump_json()
    except Exception as exc:  # report the failure upward instead of crashing the whole team
        reply = f"{agent} couldn't finish: {short(exc, 200)}"
    future.set_result(reply)
    await state.trail.log("delegation_end", agent=agent, chain=[*deps.chain, agent], detail={"to": me, "reply": short(reply, 600)})
    return reply


def _usage(u: Any) -> dict[str, int]:
    return {
        "requests": getattr(u, "requests", 0) or 0,
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
    }


async def _log_node(trail: AuditTrail, name: str, chain: list[str], node: Any) -> None:
    if Agent.is_user_prompt_node(node):
        await trail.log("user_prompt", agent=name, chain=chain, text=short(node.user_prompt, 600))
    elif Agent.is_model_request_node(node):
        parts = node.request.parts
        returns = [
            {"tool": p.tool_name, "call_id": p.tool_call_id, "content": short(p.model_response_str(), 400)}
            for p in parts
            if isinstance(p, ToolReturnPart)
        ]
        retries = [short(p.model_response(), 200) for p in parts if isinstance(p, RetryPromptPart)]
        await trail.log(
            "model_request", agent=name, chain=chain, model=MODEL_NAME,
            tool_returns=returns or None, detail={"retries": retries} if retries else None,
        )
    elif Agent.is_call_tools_node(node):
        resp = node.model_response
        calls = [{"tool": p.tool_name, "call_id": p.tool_call_id, "args": p.args_as_dict()} for p in resp.parts if isinstance(p, ToolCallPart)]
        text = "".join(p.content for p in resp.parts if isinstance(p, TextPart))
        await trail.log(
            "model_response", agent=name, chain=chain, model=resp.model_name or MODEL_NAME,
            text=short(text) if text else None, tool_calls=calls or None, usage=_usage(resp.usage),
        )
    elif Agent.is_end_node(node):
        await trail.log("agent_end", agent=name, chain=chain, text=short(node.data.output, 600))


async def run_agent(name: str, prompt: str, deps: TeamDeps, usage: RunUsage | None = None) -> Any:
    """Drive one agent's loop node by node, auditing every step. Returns its output."""
    agent = AGENTS[name]
    chain = list(deps.chain)
    async with agent.iter(prompt, deps=deps, model=build_model(), usage=usage, usage_limits=deps.state.limits) as run:
        async for node in run:
            await _log_node(deps.state.trail, name, chain, node)
    return run.result.output

"""Campus Customs desk API — the backend for the React ticket board.

Run from this folder:
  uvicorn main:app --reload --port 8000        (or .venv/bin/uvicorn ...)

Every shop fact (tickets, cash, approvals) comes from the campus-customs MCP server, the same one the
agents use; nothing here reads or writes the shop tables directly. The only file access is the audit
trail (our own log) and the reset, which copies the original database over the working copy.

Agent runs take minutes, so POST /api/tickets/{id}/run starts the team in the background and returns
a run_id right away; the board polls GET /api/events (and GET /api/runs/{run_id}) to watch it work.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from audit import AUDIT_PATH, AuditTrail, short
from config import mcp_client
from reset_db import reset_db
from team import run_team

RUNS: dict[str, dict[str, Any]] = {}  # run_id -> status, ticket, report / error (this server's runs only)
TASKS: dict[str, asyncio.Task] = {}  # run_id -> its background task, so Stop can cancel it
TRAILS: dict[str, AuditTrail] = {}  # run_id -> its live AuditTrail while running, so human steps share its step counter
RUN_LOCK = asyncio.Lock()  # one team run at a time: the tickets share the same cash


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One MCP connection for the routes (the agents open their own while a run is going).
    async with mcp_client() as client:
        app.state.mcp = client
        yield


app = FastAPI(title="Campus Customs desk API", version="1.0.0", lifespan=lifespan)
# The browser may only call these routes from the Vite board: 5173 is Vite's default, 5177 is the port
# frontend/vite.config.ts pins (5173-5176 are busy on this machine). Add more with FRONTEND_ORIGINS.
FRONTEND_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5177,http://127.0.0.1:5177",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


async def mcp(tool: str, args: dict | None = None) -> dict:
    """Call a campus-customs MCP tool and return its structured result."""
    result = await app.state.mcp.call_tool(tool, args or {}, raise_on_error=False)
    data = result.structured_content
    if data is None:
        data = json.loads(result.content[0].text) if result.content else {}
    if result.is_error:
        raise HTTPException(502, short(data, 300))
    return data


def scope(run: dict) -> str:
    return "all open tickets" if run["ticket_id"] is None else f"ticket {run['ticket_id']}"


def running() -> dict | None:
    return next((r for r in RUNS.values() if r["status"] == "running"), None)


async def audit_human(ticket_id: int | None, event: str, who: str, **detail: Any) -> None:
    """Append a human decision (approve / deny / resolve) to the audit trail, under that ticket's latest run.

    Human clicks don't go through an agent loop, so without this they'd never reach audit_trail.json.
    """
    trail = None
    run_id = None
    if ticket_id is not None:
        run_id = next((r["run_id"] for r in reversed(list(RUNS.values())) if r["ticket_id"] in (ticket_id, None)), None)
        if run_id is None:  # a run from before this server started: find it in the trail
            entries = json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() else []
            run_id = next((e["run_id"] for e in reversed(entries)
                           if e["event"] == "run_start" and (e.get("detail") or {}).get("ticket_id") == ticket_id), None)
    if run_id in TRAILS:
        trail = TRAILS[run_id]  # run still going: share its step counter
    else:
        trail = AuditTrail()
        if run_id:
            entries = json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() else []
            mine = [e for e in entries if e["run_id"] == run_id]
            trail.run_id = run_id
            trail.step = max((e["step"] for e in mine), default=0)
            start = next((e for e in mine if e["event"] == "run_start"), None)
            if start:  # keep elapsed_s on the run's clock
                age = (datetime.now(UTC) - datetime.fromisoformat(start["timestamp"])).total_seconds()
                trail.started = time.perf_counter() - age
    await trail.log(event, agent="Human", detail={"by": who, "ticket_id": ticket_id, **detail})


async def ticket_for_payment(kind: str, ref_id: int) -> int | None:
    """Which ticket a payment belongs to: invoice -> tickets.invoice_id, rent -> tickets.lease_id."""
    for t in (await mcp("list_tickets"))["tickets"]:
        if (kind == "invoice" and t["invoice_id"] == ref_id) or (kind == "rent" and t["lease_id"] == ref_id):
            return t["id"]
    return None


# ---------- Routes ----------


@app.get("/api/health")
async def health():
    return {"ok": True, "tools": [t.name for t in await app.state.mcp.list_tools()], "running": running()}


@app.get("/api/tickets")
async def tickets():
    """All tickets with their status and whether each is open or resolved."""
    data = await mcp("list_tickets")
    return {
        "date_today": data["date_today"],
        "tickets": [
            {k: t[k] for k in ("id", "type", "requester", "subject", "sku", "size", "qty", "lease_id", "invoice_id", "status", "state", "notes", "created_at")}
            for t in data["tickets"]
        ],
    }


async def _run(run_id: str, ticket_id: int | None, trail: AuditTrail) -> None:
    async with RUN_LOCK:
        try:
            report, state = await run_team(ticket_id, trail)
            RUNS[run_id].update(status="done", report=report.model_dump(), delegations=state.delegations)
        except asyncio.CancelledError:  # Stop button
            RUNS[run_id].update(status="stopped")
        except Exception as exc:
            RUNS[run_id].update(status="error", error=short(exc, 400))
        RUNS[run_id]["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        TRAILS.pop(run_id, None)
        TASKS.pop(run_id, None)


def _start(ticket_id: int | None) -> dict:
    trail = AuditTrail()
    TRAILS[trail.run_id] = trail
    RUNS[trail.run_id] = {
        "run_id": trail.run_id, "ticket_id": ticket_id, "status": "running",
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    TASKS[trail.run_id] = asyncio.create_task(_run(trail.run_id, ticket_id, trail))
    return {"run_id": trail.run_id, "ticket_id": ticket_id, "status": "running", "events": f"/api/events?run_id={trail.run_id}"}


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int):
    """Start the agent team on one ticket. Returns a run_id; watch it with /api/events."""
    if busy := running():
        raise HTTPException(409, f"The team is already working {scope(busy)} (run {busy['run_id']}).")
    ids = {t["id"]: t for t in (await mcp("list_tickets"))["tickets"]}
    if ticket_id not in ids:
        raise HTTPException(404, f"No ticket {ticket_id}.")
    if ids[ticket_id]["state"] == "resolved":
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved. Reset to try it again.")
    return _start(ticket_id)


@app.post("/api/run-all", status_code=202)
async def run_all():
    """Start the Boss on every open ticket in one run. The tickets share one cash plan, and the Boss
    sends independent work out to the specialists in parallel."""
    if busy := running():
        raise HTTPException(409, f"The team is already working {scope(busy)} (run {busy['run_id']}).")
    open_ids = [t["id"] for t in (await mcp("list_tickets"))["tickets"] if t["state"] == "open"]
    if not open_ids:
        raise HTTPException(409, "No open tickets. Reset to try again.")
    return {**_start(None), "tickets": open_ids}


@app.post("/api/runs/{run_id}/stop")
async def stop_run(run_id: str):
    """Stop button: cancel a running team run immediately. Any payment it queued that a human hasn't
    decided yet is denied, so nothing from a stopped run gets paid later."""
    run = RUNS.get(run_id)
    task = TASKS.get(run_id)
    if run is None or task is None or run["status"] != "running":
        raise HTTPException(409, f"Run {run_id} isn't running.")
    trail = TRAILS.get(run_id)
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=10)
    except (asyncio.CancelledError, TimeoutError):
        pass
    started = run["started_at"]
    denied = []
    for req in (await mcp("list_approval_queue", {"status": "pending"}))["requests"]:
        if req["created_at"] >= started:
            await mcp("approve_payment", {"request_id": req["id"], "approved_by": "Stop button", "approve": False,
                                          "note": f"run {run_id} was stopped before a decision"})
            denied.append(req["id"])
    if trail:
        await trail.log("run_stopped", agent="Human", detail={"by": "Stop button", "denied_requests": denied})
    return {"run_id": run_id, "status": "stopped", "denied_requests": denied}


class ResolveIn(BaseModel):
    resolved_by: str = Field(min_length=1, max_length=80, description="The human marking it resolved")
    note: str = Field("", max_length=300)


@app.post("/api/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, body: ResolveIn):
    """A human marks a ticket resolved after the team finished (and any payment was handled)."""
    if (busy := running()) and busy["ticket_id"] in (ticket_id, None):
        raise HTTPException(409, f"The team is still working {scope(busy)}.")
    note = f"Marked resolved by {body.resolved_by}" + (f": {body.note}" if body.note else ".")
    result = await mcp("update_ticket", {"ticket_id": ticket_id, "status": "resolved", "note": note})
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "Couldn't update the ticket."))
    await audit_human(ticket_id, "human_resolve", body.resolved_by, old_status=result.get("old_status"), note=body.note or None)
    return result


@app.get("/api/runs/{run_id}")
async def run_status(run_id: str):
    """Status of a run started here: running, done (with the Boss's report), stopped, or error."""
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} on this server.")
    return RUNS[run_id]


class EventsOut(BaseModel):
    events: list[dict]
    next_since: int = Field(description="Pass back as ?since= to get only newer events")
    running: dict | None


@app.get("/api/events", response_model=EventsOut)
async def events(
    run_id: str | None = Query(None, description="Only this run (default: the latest run in the trail)"),
    since: int = Query(0, description="Only events with step > since"),
    limit: int = Query(100, ge=1, le=500),
):
    """Recent agent events from output/audit_trail.json: who said what and which tools they called."""
    trail = await asyncio.to_thread(lambda: json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() else [])
    if run_id is None and trail:
        run_id = (running() or {}).get("run_id") or trail[-1]["run_id"]
    picked = [e for e in trail if e["run_id"] == run_id and e["step"] > since][-limit:]
    return {"events": picked, "next_since": picked[-1]["step"] if picked else since, "running": running()}


@app.get("/api/approvals")
async def approvals(status: str = Query("pending", pattern="^(pending|paid|declined|all)$")):
    """Payments waiting for a human (or paid / declined)."""
    return await mcp("list_approval_queue", {"status": status})


class ApproveIn(BaseModel):
    approved_by: str = Field(min_length=1, max_length=80, description="The human clicking approve")
    approve: bool = True
    note: str = Field("", max_length=300)


@app.post("/api/approvals/{request_id}/approve")
async def approve(request_id: int, body: ApproveIn):
    """A human approves (or rejects) a queued payment. The pay tool still declines if cash would go below $0."""
    queue = (await mcp("list_approval_queue", {"status": "all"}))["requests"]
    req = next((r for r in queue if r["id"] == request_id), None)
    result = await mcp("approve_payment", {"request_id": request_id, **body.model_dump()})
    if not result.get("ok") and result.get("status") != "declined":
        raise HTTPException(400, result.get("error", "Approval failed."))
    if req:
        await audit_human(
            await ticket_for_payment(req["kind"], req["ref_id"]),
            "human_approval",
            body.approved_by,
            request_id=request_id,
            decision="approve" if body.approve else "deny",
            outcome=result.get("status"),
            kind=req["kind"], ref_id=req["ref_id"], payee=req["payee"], amount=req["amount"],
            checking_after=result.get("checking_balance"),
            note=body.note or result.get("error") or None,
        )
    return result


@app.get("/api/cash")
async def cash():
    """Current checking balance from cash_accounts, plus what's waiting for approval."""
    data = await mcp("get_cash_balance")
    checking = next((a for a in data.get("accounts", []) if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {
        "date_today": data["date_today"],
        "checking": checking["balance"],
        "as_of": checking["date"],
        "pending_total": data["pending_total"],
        "checking_if_all_pending_paid": data["balance_if_all_pending_paid"],
        "pending_approvals": data["pending_approvals"],
    }


@app.post("/api/reset")
async def reset():
    """Copy the original campus_customs.db over the working copy for a fresh run."""
    if busy := running():
        raise HTTPException(409, f"Can't reset while the team is working {scope(busy)}.")
    await asyncio.to_thread(reset_db)
    await audit_human(None, "human_reset", "board", note="working copy reset to the original database")
    return {"ok": True, "message": "campus_customs_new.db reset to the original campus_customs.db."}

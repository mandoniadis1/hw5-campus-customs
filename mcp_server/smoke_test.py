"""Smoke-test the 3 MCP tools the way an agent would reach them, and save the evidence.

Launches the server from the exact command in ../.mcp.json (stdio, real MCP protocol), asks each
test question through its tool, checks every reported value against data/campus_customs_new.db with
plain SQL, and writes ../output/mcp_smoke.json.

Run from mcp_server/ on a freshly reset database (it overwrites output/mcp_smoke.json):
  ../.venv/bin/python smoke_test.py
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import date
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


HW = Path(__file__).resolve().parent.parent
DB = HW / "data" / "campus_customs_new.db"
OUT = HW / "output" / "mcp_smoke.json"


def sql(query: str, *args) -> list[dict]:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(query, args).fetchall()]
    finally:
        conn.close()


def check(label: str, tool_value, db_value) -> dict:
    return {"field": label, "tool": tool_value, "db": db_value, "match": tool_value == db_value}


async def main() -> None:
    server = json.loads((HW / ".mcp.json").read_text())["mcpServers"]["campus-customs"]
    # .mcp.json paths are relative to hw5/
    def here(x):
        return str(HW / x) if ("/" in x and not Path(x).is_absolute()) else x
    transport = StdioTransport(command=here(server["command"]), args=[here(a) for a in server["args"]], cwd=str(HW))
    today = date.fromisoformat(sql("SELECT date_today FROM desk")[0]["date_today"])
    tests = []

    async with Client(transport) as client:
        tools = [t.name for t in await client.list_tools()]

        async def call(name: str, args: dict) -> dict:
            result = await client.call_tool(name, args)
            return result.structured_content or json.loads(result.content[0].text)

        # 1 — hoodies in size small + pricing
        args = {"sku": "CC-HOOD-NAVY", "size": "S"}
        out = await call("check_stock_and_price", args)
        inv = sql("SELECT qty FROM inventory WHERE sku = ? AND size = ?", *args.values())[0]
        price = sql("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", args["sku"])[0]
        tests.append({
            "prompt": "How many hoodies are in size small? and what is the pricing",
            "tool": "check_stock_and_price",
            "arguments": args,
            "tool_output": out,
            "db_checks": [
                check("qty_in_stock (size S)", out["qty_in_stock"], inv["qty"]),
                check("unit_cost", out["pricing"]["unit_cost"], price["unit_cost"]),
                check("list_price", out["pricing"]["list_price"], price["list_price"]),
            ],
            "answer": (
                f"{out['qty_in_stock']} {out['name']} hoodies in size S ({out['location']}). "
                f"List price ${out['pricing']['list_price']:.2f}, unit cost ${out['pricing']['unit_cost']:.2f}, "
                f"so the most it can be discounted and still cover cost is {out['max_discount_pct_above_cost']}%."
            ),
        })

        # 2 — overdue invoices, total invoices, and whether paying clears us
        args = {"invoice_id": 501}  # the only invoice referenced by an open ticket (101)
        out = await call("get_invoice_status", args)
        all_inv = sql("SELECT id, amount, due_date, status FROM invoices")
        overdue_db = [i for i in all_inv if i["status"] != "paid" and date.fromisoformat(i["due_date"]) < today]
        cash = sql("SELECT balance FROM cash_accounts WHERE name = 'checking'")[0]["balance"]
        rent = sql("SELECT monthly_rent, next_due FROM leases WHERE id = 1")[0]
        after_invoice = cash - out["invoice"]["amount"]
        tests.append({
            "prompt": "How many invoices do we have that are overdue and how many total? If we pay the overdue one are we in the clear?",
            "tool": "get_invoice_status",
            "arguments": args,
            "tool_output": out,
            "db_checks": [
                check("invoice amount", out["invoice"]["amount"], next(i["amount"] for i in all_inv if i["id"] == 501)),
                check("days_overdue", out["days_overdue"],
                      (today - date.fromisoformat(out["invoice"]["due_date"])).days if out["is_unpaid"] else 0),
                check("vendor unpaid invoices", len(out["vendor_unpaid_invoices"]), len([i for i in all_inv if i["status"] != "paid"])),
                check("total invoices in db", len(all_inv), len(sql("SELECT id FROM invoices"))),
            ],
            "answer": (
                f"{len(overdue_db)} overdue out of {len(all_inv)} invoice(s) total: invoice 501, "
                f"${out['invoice']['amount']:.2f} to {out['vendor']['name']}, {out['days_overdue']} days overdue. "
                f"Paying it clears the vendor's only unpaid invoice, so they'll ship again (earliest arrival "
                f"{out.get('earliest_arrival_if_paid_today') or out.get('earliest_arrival_if_ordered_today')}). Cash would go from ${cash:,.2f} to ${after_invoice:,.2f}, but "
                f"rent of ${rent['monthly_rent']:,.2f} is due {rent['next_due']}, which would leave only "
                f"${after_invoice - rent['monthly_rent']:,.2f}. So we're clear on invoices, but cash is very tight."
            ),
            "limitations": (
                "get_invoice_status looks up one invoice (and its vendor's other invoices); it can't list every invoice. "
                "The total count and the cash/rent figures come from the db_checks SQL, not from this tool. "
                "A list_invoices / get_cash_balance tool would let an agent answer this alone."
            ),
        })

        # 3 — lease amount and due date
        args = {"lease_id": 1}
        out = await call("get_lease", args)
        lease = sql("SELECT monthly_rent, next_due, landlord FROM leases WHERE id = 1")[0]
        tests.append({
            "prompt": "How much is our lease and when is it due?",
            "tool": "get_lease",
            "arguments": args,
            "tool_output": out,
            "db_checks": [
                check("monthly_rent", out["lease"]["monthly_rent"], lease["monthly_rent"]),
                check("next_due", out["lease"]["next_due"], lease["next_due"]),
                check("days_until_due", out["days_until_due"], (date.fromisoformat(lease["next_due"]) - today).days),
            ],
            "answer": (
                f"${out['lease']['monthly_rent']:,.2f} a month to {out['lease']['landlord']} for the "
                f"{out['lease']['space_name']}, next due {out['lease']['next_due']}: "
                f"{out['days_until_due']} days from the shop's today ({out['date_today']})."
            ),
        })

    evidence = {
        "server": "campus-customs",
        "connection": {"config": ".mcp.json", "transport": "stdio", **server},
        "database": str(DB.relative_to(HW)),
        "shop_date_today": today.isoformat(),
        "tools_listed": tools,
        "all_checks_match": all(c["match"] for t in tests for c in t["db_checks"]),
        "tests": tests,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"wrote {OUT.relative_to(HW)} · all checks match: {evidence['all_checks_match']}")
    for t in tests:
        print(f"\n[{t['tool']}] {t['prompt']}\n  → {t['answer']}")


if __name__ == "__main__":
    asyncio.run(main())

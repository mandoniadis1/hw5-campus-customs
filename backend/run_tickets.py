"""Full run from the command line: reset the shop, then let the Boss and the team work every open ticket.

Run:  .venv/bin/python run_tickets.py            (resets the database first, per the shop rules)
      .venv/bin/python run_tickets.py --no-reset (continue from the current working copy)
      .venv/bin/python run_tickets.py --ticket 102 --no-reset   (just one ticket)

Prints the Boss's report, saves it to output/boss_report.json, and appends every agent-loop step to
output/audit_trail.json. Payments end up on the approval list; approve them with approve.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from reset_db import reset_db
from team import REPORT, run_team


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-reset", action="store_true")
    p.add_argument("--ticket", type=int)
    a = p.parse_args()
    if not a.no_reset:
        reset_db()
    report, state = await run_team(a.ticket)
    print(json.dumps(report.model_dump(), indent=2))
    print(f"\nrun {state.trail.run_id}: {state.delegations} delegations · report → output/{REPORT.name}")


if __name__ == "__main__":
    asyncio.run(main())

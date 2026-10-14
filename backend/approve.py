"""Human approval desk for queued payments — goes through the MCP server like everything else.

  .venv/bin/python approve.py                       list pending payments
  .venv/bin/python approve.py 2 --by "Madison"      approve (pay) request 2
  .venv/bin/python approve.py 2 --by "Madison" --reject "not yet"

Approving re-checks cash: the pay tool DECLINES anything that would take checking below $0.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from config import mcp_client


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("request_id", nargs="?", type=int)
    p.add_argument("--by", help="your name (required to approve or reject)")
    p.add_argument("--reject", metavar="NOTE", help="reject instead of paying")
    a = p.parse_args()
    async with mcp_client() as client:
        if a.request_id is None:
            result = await client.call_tool("list_approval_queue", {"status": "pending"})
        else:
            if not a.by:
                p.error("--by is required")
            result = await client.call_tool(
                "approve_payment",
                {"request_id": a.request_id, "approved_by": a.by, "approve": a.reject is None, "note": a.reject or ""},
            )
    print(json.dumps(result.structured_content, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

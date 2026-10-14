"""Model + MCP configuration shared by every agent.

- Every agent runs on gpt-6-luna through Portkey (OpenAI-compatible). No other model is allowed.
- PORTKEY_API_KEY is read from the nearest .env in this folder or any parent. Never printed.
- Shop data only comes from the campus-customs MCP server, launched exactly as hw5/.mcp.json says.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

BACKEND = Path(__file__).resolve().parent
HW = BACKEND.parent
for folder in [BACKEND, *BACKEND.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)

MODEL_NAME = "gpt-6-luna"  # the only model this team uses
# A dropped model call should fail fast and retry, not hang. The OpenAI client's default waits up to
# 600 s per attempt; 90 s is well above gpt-6-luna's slowest normal replies here.
MODEL_TIMEOUT = 90.0  # seconds per attempt
MODEL_RETRIES = 2
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")
ORIGINAL_DB = HW / "data" / "campus_customs.db"
WORKING_DB = HW / "data" / "campus_customs_new.db"


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Put it in a .env in hw5 or a parent folder.")
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
        timeout=MODEL_TIMEOUT,
        max_retries=MODEL_RETRIES,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def mcp_client() -> Client:
    """A FastMCP client for the campus-customs server, from the project's .mcp.json."""
    server = json.loads((HW / ".mcp.json").read_text())["mcpServers"]["campus-customs"]
    return Client(StdioTransport(**mcp_launch(server)))


def mcp_launch(server: dict) -> dict:
    """.mcp.json paths are relative to hw5/ (portable for anyone who clones the repo): make them absolute."""
    def here(x: str) -> str:
        return str(HW / x) if ("/" in x and not Path(x).is_absolute()) else x
    return {
        "command": here(server["command"]),
        "args": [here(a) if a.endswith(".py") else a for a in server.get("args", [])],
        "env": server.get("env"),
        "cwd": str(HW),
    }


def build_mcp_toolset(process_tool_call=None) -> MCPToolset:
    return MCPToolset(mcp_client(), id="campus-customs", process_tool_call=process_tool_call)

"""Append-only audit trail: hw5/output/audit_trail.json.

One JSON list that is never wiped or rewritten from scratch. Each write takes an exclusive file lock,
reads the list, appends one entry and atomically replaces the file, so parallel agents can't corrupt
it and a crash mid-write can't truncate it. Entries hold short summaries (≤ 300 chars per field).
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_core import to_jsonable_python

from models import AuditEntry

AUDIT_PATH = Path(os.getenv("AUDIT_TRAIL_PATH", Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"))
LOCK_PATH = AUDIT_PATH.with_suffix(".lock")


def short(value: Any, limit: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(to_jsonable_python(value), ensure_ascii=False, default=str)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class AuditTrail:
    """One per full run. `await trail.log("model_response", agent="Boss", ...)`."""

    def __init__(self) -> None:
        self.run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.started = time.perf_counter()
        self.step = 0

    async def log(self, event: str, **fields: Any) -> None:
        self.step += 1
        entry = AuditEntry(
            run_id=self.run_id,
            step=self.step,
            timestamp=datetime.now(UTC).isoformat(timespec="milliseconds"),
            elapsed_s=round(time.perf_counter() - self.started, 2),
            event=event,
            **fields,
        )
        await asyncio.to_thread(_append, entry)


def _append(entry: AuditEntry) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        entries = json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size else []
        entries.append(entry.model_dump(exclude_none=True))
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, AUDIT_PATH)

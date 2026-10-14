"""Reset the working copy to the original shop data (shop rule: always before a full run).

Run:  .venv/bin/python reset_db.py
"""

from __future__ import annotations

import shutil

from config import ORIGINAL_DB, WORKING_DB


def reset_db() -> None:
    if not ORIGINAL_DB.exists():
        raise FileNotFoundError(f"Original database missing: {ORIGINAL_DB}")
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)


if __name__ == "__main__":
    reset_db()
    print(f"reset {WORKING_DB.name} from {ORIGINAL_DB.name}")

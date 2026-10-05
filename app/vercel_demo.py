from __future__ import annotations

import os

from .config import DB_PATH


DEMO_INVESTIGATION_ID = "INV-DEMO-2026"


def initialize_vercel_demo() -> None:
    """
    Initialize the controlled PRALAYX demonstration dataset.

    This is only used on Vercel.
    Local WSL execution continues to use the normal database
    and normal crawler/OSINT workflow.
    """

    if not os.getenv("VERCEL"):
        return

    if os.getenv("PRALAYX_DEMO_SEEDED") == "1":
        return

    # Configure the database path BEFORE importing seed_demo.
    os.environ["PRALAYX_DB_PATH"] = DB_PATH

    from .seed_demo import seed

    seed()

    os.environ["PRALAYX_DEMO_SEEDED"] = "1"

    print(
        f"PRALAYX hosted demonstration initialized: "
        f"{DEMO_INVESTIGATION_ID}"
    )

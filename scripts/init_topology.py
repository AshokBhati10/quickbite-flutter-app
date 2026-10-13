"""Declare broker topology (init step run before dispatch).

Run:  .venv/bin/python scripts/init_topology.py
"""

from __future__ import annotations

import asyncio
import os
import sys

for _candidate in (
    os.path.join(os.path.dirname(__file__), "..", "backend"),
    "/srv/app",
):
    if os.path.isdir(os.path.join(_candidate, "app")):
        sys.path.insert(0, _candidate)

from app.core.config import get_settings  # noqa: E402
from app.messaging.topology import declare_topology  # noqa: E402


async def main() -> None:
    settings = get_settings()
    await declare_topology(settings.AMQP_URL)
    print("topology declared")


if __name__ == "__main__":
    asyncio.run(main())

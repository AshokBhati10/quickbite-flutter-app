"""Inspect retry jobs, quarantine records, and outbox backlog.

Run:  .venv/bin/python scripts/inspect.py [--order ORDER_ID]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

for _candidate in (
    os.path.join(os.path.dirname(__file__), "..", "backend"),
    "/srv/app",
):
    if os.path.isdir(os.path.join(_candidate, "app")):
        sys.path.insert(0, _candidate)

from sqlalchemy import func, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import init_db, session_factory  # noqa: E402
from app.domain.models import OutboxEvent, QuarantineRecord, RetryJob  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", default=None)
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.DATABASE_URL)
    factory = session_factory()
    async with factory() as session:
        pending = (
            await session.execute(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.sent_at.is_(None))
            )
        ).scalar()
        jobs = (await session.execute(select(RetryJob))).scalars().all()
        quar = (await session.execute(select(QuarantineRecord))).scalars().all()
        print(f"pending outbox: {pending}")
        print(f"retry jobs: {len(jobs)}")
        for job in jobs:
            print(
                f"  {job.consumer_name} {job.event_id} "
                f"attempt={job.attempt} status={job.status} run_at={job.run_at}"
            )
            if args.order and args.order not in job.event_id:
                pass
        print(f"quarantine records: {len(quar)}")
        for record in quar:
            print(
                f"  {record.consumer_name} {record.event_id} "
                f"attempts={record.attempts} code={record.failure_code}"
            )
        if args.order:
            rows = (
                await session.execute(
                    select(OutboxEvent).where(OutboxEvent.event_id.contains(args.order))
                )
            ).scalars().all()
            print(f"outbox rows matching {args.order}: {len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())

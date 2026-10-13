"""Retry scheduler (assignment §11).

Makes due retry_jobs eligible: retry rows are written with a future
available_at by the failing worker; this process marks jobs done once
their targeted outbox publication is confirmed sent, recreates a missing
targeted outbox row for a due job (watchdog, copying the immutable
envelope from the original domain outbox row), and reports backlog.
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.db import init_db, session_factory
from app.core.logging import configure_logging, log_event
from app.domain.models import OutboxEvent, RetryJob, new_id, utcnow
from app.messaging.topology import QUEUE_CONSUMERS

configure_logging()

TICK_S = 5.0
CONSUMER_QUEUES = {v: k for k, v in QUEUE_CONSUMERS.items()}


async def tick(settings: Settings) -> dict:
    factory = session_factory()
    async with factory() as session:
        async with session.begin():
            due_jobs = (
                await session.execute(
                    select(RetryJob).where(
                        RetryJob.status == "scheduled",
                        RetryJob.run_at <= datetime.now(timezone.utc),
                    )
                )
            ).scalars()
            due_jobs = list(due_jobs)
            done = 0
            recreated = 0
            for job in due_jobs:
                queue = CONSUMER_QUEUES.get(job.consumer_name)
                targeted = None
                sent_exists = False
                if queue:
                    targeted = (
                        await session.execute(
                            select(OutboxEvent).where(
                                OutboxEvent.event_id == job.event_id,
                                OutboxEvent.exchange == "",
                                OutboxEvent.routing_key == queue,
                            )
                        )
                    ).scalars().all()
                    sent_exists = any(r.sent_at is not None for r in targeted)
                if sent_exists:
                    job.status = "done"
                    done += 1
                elif not targeted and queue:
                    # Watchdog: the atomic write was lost; rebuild the
                    # targeted row from the immutable domain envelope.
                    domain_row = (
                        await session.execute(
                            select(OutboxEvent).where(
                                OutboxEvent.event_id == job.event_id,
                                OutboxEvent.exchange != "",
                            )
                        )
                    ).scalars().first()
                    if domain_row is not None:
                        session.add(
                            OutboxEvent(
                                id=new_id("obx"),
                                event_id=job.event_id,
                                event_type=domain_row.event_type,
                                exchange="",
                                routing_key=queue,
                                attempt=job.attempt + 1,
                                payload=domain_row.payload,
                                available_at=utcnow(),
                            )
                        )
                        recreated += 1
            pending = (
                await session.execute(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(OutboxEvent.sent_at.is_(None))
                )
            ).scalar() or 0
            scheduled = (
                await session.execute(
                    select(func.count())
                    .select_from(RetryJob)
                    .where(RetryJob.status == "scheduled")
                )
            ).scalar() or 0
    return {
        "due": len(due_jobs),
        "done": done,
        "recreated": recreated,
        "pending_outbox": pending,
        "scheduled_retries": scheduled,
    }


async def main() -> None:
    settings = get_settings()
    init_db(settings.DATABASE_URL)
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except (NotImplementedError, RuntimeError):
            pass
    log_event("scheduler.start", service="retry-scheduler")
    while not stopping.is_set():
        try:
            stats = await tick(settings)
            log_event("scheduler.tick", service="retry-scheduler", **stats)
        except Exception as exc:
            log_event("scheduler.error", service="retry-scheduler", error=str(exc))
        try:
            await asyncio.wait_for(stopping.wait(), timeout=TICK_S)
        except asyncio.TimeoutError:
            pass


if __name__ == "__main__":
    asyncio.run(main())

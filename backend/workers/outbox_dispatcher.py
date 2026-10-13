"""Outbox dispatcher (assignment §10).

Claims eligible rows with FOR UPDATE SKIP LOCKED (safe for multiple
dispatcher instances), publishes with publisher confirms and
mandatory=True, marks rows sent only after confirmation with no
unroutable return. Publication failures leave rows eligible for a
delayed retry. Reconnects with backoff; graceful shutdown.
"""

from __future__ import annotations

import asyncio
import json
import signal
from datetime import datetime, timezone

import aio_pika
from aio_pika import Message
from aiormq.exceptions import PublishError
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.db import init_db, session_factory
from app.core.logging import configure_logging, log_event
from app.domain.models import OutboxEvent
from app.messaging.topology import declare_topology

configure_logging()

BATCH_SIZE = 20
POLL_INTERVAL_S = 1.0


def _attempt_for(row: OutboxEvent) -> int:
    """Delivery attempt metadata travels on the outbox row itself: 1 for
    first domain delivery, N+1 for the retry scheduled after attempt N
    failed. The event identity is unchanged."""
    return row.attempt or 1


async def _publish_one(channel, row: OutboxEvent, attempt: int) -> None:
    body = json.dumps(row.payload).encode()
    message = Message(
        body,
        message_id=row.event_id,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        headers={"attempt": attempt},
    )
    if row.exchange:
        exchange = await channel.get_exchange(row.exchange)
        await exchange.publish(message, routing_key=row.routing_key, mandatory=True)
    else:
        # Targeted retry: default exchange, routing key = failing queue.
        # Never republish retries to the domain exchange (that would fan
        # out to unrelated subscribers again).
        await channel.default_exchange.publish(
            message, routing_key=row.routing_key, mandatory=True
        )


async def dispatch_forever(settings: Settings, stopping: asyncio.Event) -> None:
    backoff = 1.0
    await declare_topology(settings.AMQP_URL)
    while not stopping.is_set():
        try:
            connection = await aio_pika.connect_robust(settings.AMQP_URL)
            try:
                # Publisher confirms are enabled by default; on_return_raises
                # turns unroutable mandatory publishes into PublishError so a
                # bare confirm is never mistaken for successful routing.
                channel = await connection.channel(on_return_raises=True)
                log_event("dispatcher.start", service="dispatcher")
                backoff = 1.0
                while not stopping.is_set():
                    factory = session_factory()
                    async with factory() as session:
                        async with session.begin():
                            rows = (
                                await session.execute(
                                    select(OutboxEvent)
                                    .where(
                                        OutboxEvent.sent_at.is_(None),
                                        OutboxEvent.available_at
                                        <= datetime.now(timezone.utc),
                                    )
                                    .order_by(OutboxEvent.available_at)
                                    .limit(BATCH_SIZE)
                                    .with_for_update(skip_locked=True)
                                )
                            ).scalars()
                            batch = list(rows)
                            for row in batch:
                                attempt = _attempt_for(row)
                                try:
                                    await _publish_one(channel, row, attempt)
                                except PublishError:
                                    # Mandatory publish with no route (or a
                                    # negative confirm): leave the row
                                    # eligible for a delayed retry.
                                    log_event(
                                        "dispatcher.unroutable",
                                        service="dispatcher",
                                        event_id=row.event_id,
                                        exchange=row.exchange,
                                        routing_key=row.routing_key,
                                    )
                                    continue
                                except Exception as exc:
                                    log_event(
                                        "dispatcher.publish_failed",
                                        service="dispatcher",
                                        event_id=row.event_id,
                                        error=str(exc),
                                    )
                                    continue
                                row.sent_at = datetime.now(timezone.utc)
                                log_event(
                                    "dispatcher.sent",
                                    service="dispatcher",
                                    event_id=row.event_id,
                                    routing_key=row.routing_key,
                                    attempt=attempt,
                                )
                    if not batch:
                        try:
                            await asyncio.wait_for(
                                stopping.wait(), timeout=POLL_INTERVAL_S
                            )
                        except asyncio.TimeoutError:
                            pass
            finally:
                await connection.close()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            log_event("dispatcher.reconnect", service="dispatcher", error=str(exc))
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


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
    await dispatch_forever(settings, stopping)


if __name__ == "__main__":
    asyncio.run(main())

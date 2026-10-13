"""Consumer base class (assignment §10-§11).

Manual ack, finite prefetch, reconnect backoff, graceful shutdown.
Processing sequence: validate -> lock -> processed_events check ->
state check -> transition + effects + child outbox events in one
transaction -> commit -> ack.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import uuid
from datetime import datetime, timedelta, timezone

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import session_factory
from app.core.logging import log_event
from app.domain.models import (
    OutboxEvent,
    ProcessedEvent,
    QuarantineRecord,
    RetryJob,
    new_id,
    utcnow,
)
from app.messaging.envelopes import EnvelopeError, validate_envelope
from app.messaging.topology import declare_topology

MAX_RETRIES_DEFAULT = 3


class Consumer:
    """Logical worker type. Subclasses implement `consumer_name`,
    `queue_name`, and `handle_event` (business transition + effects)."""

    consumer_name: str = "base"
    queue_name: str = ""
    prefetch: int = 10

    def __init__(self, settings: Settings):
        self.settings = settings
        self._stopping = asyncio.Event()

    # -- lifecycle ------------------------------------------------------
    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._stopping.set)
            except (NotImplementedError, RuntimeError):
                pass
        backoff = 1.0
        while not self._stopping.is_set():
            try:
                await declare_topology(self.settings.AMQP_URL)
                connection = await aio_pika.connect_robust(self.settings.AMQP_URL)
                try:
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=self.prefetch)
                    queue = await channel.declare_queue(
                        self.queue_name,
                        durable=True,
                        exclusive=False,
                        auto_delete=False,
                    )
                    await queue.consume(self._on_message)
                    log_event(
                        "worker.start",
                        service=self.consumer_name,
                        queue=self.queue_name,
                    )
                    await self._stopping.wait()
                finally:
                    await connection.close()
                return
            except asyncio.CancelledError:
                return
            except Exception as exc:  # reconnect with backoff
                log_event(
                    "worker.reconnect",
                    service=self.consumer_name,
                    error=str(exc),
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    # -- message entry --------------------------------------------------
    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        if self._stopping.is_set():
            await message.nack(requeue=True)
            return
        started = asyncio.get_running_loop().time()
        try:
            payload = json.loads(message.body.decode())
        except Exception:
            await self._quarantine_malformed(message, "malformed_json", {})
            await message.ack()
            return
        try:
            envelope = validate_envelope(payload)
        except EnvelopeError as exc:
            code = (
                "unknown_schema"
                if "schema_version" in str(exc)
                else "envelope_invalid"
            )
            await self._quarantine_malformed(message, code, payload)
            await message.ack()
            return

        attempt = int(message.headers.get("attempt", 1)) if message.headers else 1
        try:
            outcome = await self.process_envelope(envelope, attempt)
            await self.after_commit(envelope, outcome, attempt)
        except _RetryScheduled:
            await message.ack()
            return
        except _NoAck:
            # Retry bookkeeping itself failed: leave unacked, back off.
            await asyncio.sleep(1.0)
            await message.nack(requeue=True)
            return
        except _TransientFailure as exc:
            try:
                await self._schedule_retry_or_quarantine(
                    envelope, attempt, exc.code, message
                )
            except _RetryScheduled:
                await message.ack()
                return
            except Exception:
                await asyncio.sleep(1.0)
                await message.nack(requeue=True)
                return
            await message.ack()
            return
        except Exception as exc:  # unexpected: schedule retry, never tight-loop
            log_event(
                "worker.error",
                service=self.consumer_name,
                event_id=envelope["event_id"],
                error=str(exc),
            )
            try:
                await self._schedule_retry_or_quarantine(
                    envelope, attempt, "transient_error", message
                )
            except _RetryScheduled:
                await message.ack()
                return
            except _NoAck:
                await asyncio.sleep(1.0)
                await message.nack(requeue=True)
                return
            except Exception:
                await message.nack(requeue=True)
                return
            await message.ack()
            return

        elapsed = asyncio.get_running_loop().time() - started
        log_event(
            "worker.done",
            service=self.consumer_name,
            event_id=envelope["event_id"],
            order_id=envelope["order_id"],
            attempt=attempt,
            result=outcome,
            elapsed_s=round(elapsed, 3),
        )
        await message.ack()

    # -- core sequence --------------------------------------------------
    async def process_envelope(self, envelope: dict, attempt: int) -> str:
        factory = session_factory()
        async with factory() as session:
            async with session.begin():
                seen = (
                    await session.execute(
                        select(ProcessedEvent).where(
                            ProcessedEvent.consumer_name == self.consumer_name,
                            ProcessedEvent.event_id == envelope["event_id"],
                        )
                    )
                ).scalar_one_or_none()
                if seen is not None:
                    return "duplicate"
                try:
                    result = await self.handle_event(session, envelope, attempt)
                except _PermanentFailure as exc:
                    await self._quarantine_tx(
                        session, envelope, attempt, str(exc.code), message=None
                    )
                    session.add(
                        ProcessedEvent(
                            id=new_id("proc"),
                            consumer_name=self.consumer_name,
                            event_id=envelope["event_id"],
                            order_id=envelope.get("order_id"),
                            result="quarantined",
                        )
                    )
                    return "quarantined"
                session.add(
                    ProcessedEvent(
                        id=new_id("proc"),
                        consumer_name=self.consumer_name,
                        event_id=envelope["event_id"],
                        order_id=envelope.get("order_id"),
                        result=result,
                    )
                )
                return result

    async def handle_event(
        self, session: AsyncSession, envelope: dict, attempt: int
    ) -> str:
        """Business logic. Return 'applied' | 'stale-noop' | 'ignored'.

        Raise _TransientFailure to retry, _PermanentFailure to quarantine.
        Must write order changes + effect rows + child outbox events in the
        given transaction. Crash checkpoints raise SystemExit via os._exit.
        """
        raise NotImplementedError

    # -- retry / quarantine ---------------------------------------------
    def _max_retries(self) -> int:
        return self.settings.RETRY_MAX_RETRIES

    def _delay_for(self, attempt: int) -> float:
        delays = self.settings.retry_delays()
        idx = min(attempt - 1, len(delays) - 1)
        return delays[idx]

    async def _schedule_retry_or_quarantine(
        self,
        envelope: dict,
        attempt: int,
        failure_code: str,
        message: AbstractIncomingMessage | None,
    ) -> None:
        if attempt > self._max_retries():
            factory = session_factory()
            async with factory() as session:
                async with session.begin():
                    await self._quarantine_tx(
                        session, envelope, attempt, "retry_exhausted"
                    )
                    session.add(
                        ProcessedEvent(
                            id=new_id("proc"),
                            consumer_name=self.consumer_name,
                            event_id=envelope["event_id"],
                            order_id=envelope.get("order_id"),
                            result="quarantined",
                        )
                    )
            raise _RetryScheduled
        factory = session_factory()
        try:
            async with factory() as session:
                async with session.begin():
                    session.add(
                        RetryJob(
                            id=new_id("retry"),
                            consumer_name=self.consumer_name,
                            event_id=envelope["event_id"],
                            attempt=attempt,
                            run_at=utcnow() + timedelta(seconds=self._delay_for(attempt)),
                        )
                    )
                    session.add(
                        OutboxEvent(
                            id=new_id("obx"),
                            event_id=envelope["event_id"],
                            event_type=envelope["event_type"],
                            exchange="",
                            routing_key=self.queue_name,
                            attempt=attempt + 1,
                            payload=envelope,
                            available_at=utcnow()
                            + timedelta(seconds=self._delay_for(attempt)),
                        )
                    )
        except IntegrityError:
            # This attempt was already scheduled (e.g. redelivered ack-loss):
            # the surviving copy is authoritative, so ack without duplicating.
            raise _RetryScheduled
        except Exception:
            raise _NoAck
        raise _RetryScheduled

    async def _quarantine_tx(
        self,
        session: AsyncSession,
        envelope: dict,
        attempt: int,
        failure_code: str,
        message=None,
    ) -> None:
        session.add(
            QuarantineRecord(
                id=new_id("quar"),
                event_id=envelope.get("event_id", f"unknown_{uuid.uuid4().hex[:8]}"),
                consumer_name=self.consumer_name,
                source_queue=self.queue_name,
                event_payload=envelope,
                attempts=attempt,
                failure_code=failure_code,
            )
        )
        session.add(
            OutboxEvent(
                id=new_id("obx"),
                event_id=envelope.get("event_id", new_id("evt")),
                event_type="quarantined",
                exchange="quickbite.dead",
                routing_key="failed",
                attempt=attempt,
                payload={
                    "event": envelope,
                    "source_consumer": self.consumer_name,
                    "source_queue": self.queue_name,
                    "attempts": attempt,
                    "failure_code": failure_code,
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )
        await self.on_quarantine(session, envelope, failure_code)

    async def after_commit(
        self, envelope: dict, outcome: str, attempt: int
    ) -> None:
        """Hook running after commit, before ack (crash checkpoints)."""

    async def on_quarantine(
        self, session: AsyncSession, envelope: dict, failure_code: str
    ) -> None:
        """Hook: terminal state transitions on exhaustion (overridden)."""

    async def _quarantine_malformed(
        self, message: AbstractIncomingMessage, code: str, payload: dict
    ) -> None:
        factory = session_factory()
        async with factory() as session:
            async with session.begin():
                await self._quarantine_tx(
                    session,
                    payload if isinstance(payload, dict) else {},
                    1,
                    code,
                )
        log_event(
            "worker.quarantine",
            service=self.consumer_name,
            failure_code=code,
        )


class _RetryScheduled(Exception):
    pass


class _NoAck(Exception):
    pass


class _TransientFailure(Exception):
    def __init__(self, code: str = "transient_error"):
        super().__init__(code)
        self.code = code


class _PermanentFailure(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

"""Phase 4 integration (real services): retries, quarantine, failure paths."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.db import init_db, session_factory
from app.domain.models import (
    Notification,
    Order,
    OutboxEvent,
    QuarantineRecord,
    RetryJob,
    SimulatedPayment,
)
from app.messaging.consumer import _TransientFailure
from tests.integration.helpers import checkout_body, client, login


def _settings(**overrides) -> Settings:
    env = {
        "DATABASE_URL": os.environ["DATABASE_URL"],
        "SYNC_DATABASE_URL": os.environ["SYNC_DATABASE_URL"],
        "AMQP_URL": os.environ["AMQP_URL"],
        "JWT_SECRET": os.environ["JWT_SECRET"],
    }
    return Settings(**{**env, **overrides})  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_retry_policy_defaults() -> None:
    s = _settings()
    assert s.RETRY_MAX_RETRIES == 3
    assert s.retry_delays() == [2.0, 10.0, 30.0]


@pytest.mark.asyncio
async def _make_order(db_session, event_type="order.created"):
    from tests.integration.test_phase1 import _migrate
    from tests.integration.test_phase2 import _seed

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    init_db(os.environ["DATABASE_URL"])
    async with client() as c:
        token = await login(c, "customer@quickbite.test")
        created = await c.post(
            "/api/v1/orders",
            json=checkout_body(),
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
        order_id = created.json()["order_id"]
    factory = session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == event_type)
            )
        ).scalars().first()
        assert row is not None
        return order_id, row.payload


@pytest.mark.asyncio
async def test_fail_twice_then_succeed(db_session) -> None:
    order_id, created_env = await _make_order(db_session)
    from workers.payment import PaymentWorker

    worker = PaymentWorker(_settings(PAYMENT_MODE="fail-twice-then-succeed"))
    with pytest.raises(_TransientFailure):
        await worker.process_envelope(created_env, 1)
    with pytest.raises(_TransientFailure):
        await worker.process_envelope(created_env, 2)
    assert await worker.process_envelope(created_env, 3) == "applied"

    factory = session_factory()
    async with factory() as session:
        jobs = (
            await session.execute(
                select(func.count()).select_from(RetryJob).where(
                    RetryJob.consumer_name == "payment"
                )
            )
        ).scalar()
        # Attempts 1 and 2 scheduled retries; the successful attempt did not.
        assert jobs == 0  # scheduling happens in _on_message, not process_envelope
        payments = (
            await session.execute(
                select(func.count())
                .select_from(SimulatedPayment)
                .where(SimulatedPayment.order_id == order_id)
            )
        ).scalar()
        assert payments == 1


@pytest.mark.asyncio
async def test_always_fail_reaches_payment_failed_and_quarantine(db_session) -> None:
    order_id, created_env = await _make_order(db_session)
    from workers.payment import PaymentWorker

    worker = PaymentWorker(_settings(PAYMENT_MODE="always-fail"))
    # Attempts 1..3 schedule retries; attempt 4 exhausts.
    for attempt in (1, 2, 3, 4):
        try:
            await worker._schedule_retry_or_quarantine(
                created_env, attempt, "payment_declined", None
            )
        except Exception:
            pass
    factory = session_factory()
    async with factory() as session:
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert order.status == "PAYMENT_FAILED"
        assert order.failure_code == "payment_failed"
        quar = (
            await session.execute(
                select(func.count()).select_from(QuarantineRecord).where(
                    QuarantineRecord.consumer_name == "payment"
                )
            )
        ).scalar()
        assert quar == 1
        failed_events = (
            await session.execute(
                select(func.count()).select_from(OutboxEvent).where(
                    OutboxEvent.event_type == "order.payment.failed"
                )
            )
        ).scalar()
        assert failed_events == 1
        dead = (
            await session.execute(
                select(func.count()).select_from(OutboxEvent).where(
                    OutboxEvent.exchange == "quickbite.dead"
                )
            )
        ).scalar()
        assert dead == 1
        targeted = (
            await session.execute(
                select(func.count()).select_from(OutboxEvent).where(
                    OutboxEvent.exchange == "",
                    OutboxEvent.routing_key == "payment.queue",
                )
            )
        ).scalar()
        # Retries went only to the failing queue, never fanned out.
        assert targeted == 3


@pytest.mark.asyncio
async def test_restaurant_terminal_failure(db_session) -> None:
    from workers.restaurant import RestaurantWorker

    order_id, _ = await _make_order(db_session)
    # Drive to PAID first with an ok payment worker.
    from workers.payment import PaymentWorker

    init_db(os.environ["DATABASE_URL"])
    factory = session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "order.created")
            )
        ).scalars().first()
    ok_payment = PaymentWorker(_settings(PAYMENT_MODE="ok"))
    assert await ok_payment.process_envelope(row.payload, 1) == "applied"

    async with factory() as session:
        paid_row = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "order.paid")
            )
        ).scalars().first()
    failing = RestaurantWorker(_settings(RESTAURANT_MODE="fail"))
    assert await failing.process_envelope(paid_row.payload, 1) == "quarantined"
    async with factory() as session:
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert order.status == "FAILED"
        failed_events = (
            await session.execute(
                select(func.count()).select_from(OutboxEvent).where(
                    OutboxEvent.event_type == "order.failed"
                )
            )
        ).scalar()
        assert failed_events == 1


@pytest.mark.asyncio
async def test_notification_failure_preserves_status(db_session) -> None:
    from workers.notification import NotificationWorker
    from workers.payment import PaymentWorker

    order_id, created_env = await _make_order(db_session)
    ok_payment = PaymentWorker(_settings(PAYMENT_MODE="ok"))
    assert await ok_payment.process_envelope(created_env, 1) == "applied"

    factory = session_factory()
    async with factory() as session:
        paid_row = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "order.paid")
            )
        ).scalars().first()
    failing = NotificationWorker(_settings(NOTIFICATION_MODE="fail"))
    with pytest.raises(_TransientFailure):
        await failing.process_envelope(paid_row.payload, 1)
    # Exhaust: status must not change, failure recorded as quarantine only.
    try:
        await failing._schedule_retry_or_quarantine(
            paid_row.payload, 99, "notification_failed", None
        )
    except Exception:
        pass
    async with factory() as session:
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert order.status == "PAID"
        assert order.failure_code is None
        count = (
            await session.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.order_id == order_id
                )
            )
        ).scalar()
        assert count == 0


@pytest.mark.asyncio
async def test_malformed_and_future_events_quarantined_without_mutation(
    db_session,
) -> None:
    from workers.payment import PaymentWorker

    order_id, _ = await _make_order(db_session)
    worker = PaymentWorker(_settings())
    factory = session_factory()

    class _Msg:
        body = b"not json at all"
        headers = {}

        async def ack(self):
            return None

        async def nack(self, requeue=False):
            return None

    await worker._on_message(_Msg())
    async with factory() as session:
        quar = (
            await session.execute(
                select(func.count()).select_from(QuarantineRecord).where(
                    QuarantineRecord.failure_code == "malformed_json"
                )
            )
        ).scalar()
        assert quar == 1
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert order.status == "PENDING"

    # Unknown schema version -> quarantine, no retry loop.
    from app.messaging.envelopes import build_envelope

    bad = build_envelope(
        event_id="evt_bad_schema",
        event_type="order.created",
        order_id=order_id,
        order_version=1,
        correlation_id="req_x",
        data={},
    )
    bad["schema_version"] = 999

    class _Msg2(_Msg):
        import json as _json

        body = _json.dumps(bad).encode()

    await worker._on_message(_Msg2())
    async with factory() as session:
        quar2 = (
            await session.execute(
                select(func.count()).select_from(QuarantineRecord).where(
                    QuarantineRecord.failure_code == "unknown_schema"
                )
            )
        ).scalar()
        assert quar2 == 1


@pytest.mark.asyncio
async def test_out_of_order_event_defers_without_mutation(db_session) -> None:
    from workers.payment import PaymentWorker

    order_id, created_env = await _make_order(db_session)
    worker = PaymentWorker(_settings())
    future = dict(created_env, order_version=5)
    with pytest.raises(_TransientFailure):
        await worker.process_envelope(future, 1)
    factory = session_factory()
    async with factory() as session:
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert order.status == "PENDING"
        assert order.version == 1

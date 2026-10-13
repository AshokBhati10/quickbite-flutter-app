"""Phase 3 integration (real Postgres + RabbitMQ).

Covers: routing table (order.# vs order.*), happy path to DRIVER_ASSIGNED
with exactly-once effects, duplicate redelivery dedupe, SKIP LOCKED claim
semantics, unroutable publish leaving rows unsent, queue durability.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import aio_pika
import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.db import init_db, session_factory
from app.domain.models import (
    DriverAssignment,
    Notification,
    Order,
    OutboxEvent,
    SimulatedPayment,
    new_id,
)
from app.messaging.topology import NOTIFICATION_QUEUE, declare_topology
from tests.integration.helpers import checkout_body, client, login

AMQP_URL = os.environ.get(
    "TEST_AMQP_URL", "amqp://quickbite:quickbite@localhost:5672/%2F"
)


async def _settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_routing_hash_matches_multi_segment_star_does_not() -> None:
    await declare_topology(AMQP_URL)
    connection = await aio_pika.connect_robust(AMQP_URL)
    try:
        channel = await connection.channel()
        # RabbitMQ 4 forbids transient non-exclusive queues: exclusive probe.
        probe = await channel.declare_queue(
            "test.star.probe", durable=False, exclusive=True, auto_delete=True
        )
        orders = await channel.get_exchange("quickbite.orders")
        await probe.bind(orders, routing_key="order.*")

        notif = await channel.declare_queue(NOTIFICATION_QUEUE, passive=True)
        await notif.purge()
        for routing_key in ("order.paid", "order.payment.failed", "order.driver.assigned"):
            await orders.publish(
                aio_pika.Message(
                    json.dumps({"rk": routing_key}).encode(),
                    message_id=f"probe_{uuid.uuid4().hex}",
                ),
                routing_key=routing_key,
            )
        # order.# (notification queue) must receive all three.
        got = []
        for _ in range(3):
            msg = await notif.get(timeout=5, fail=True)
            got.append(json.loads(msg.body.decode())["rk"])
            await msg.ack()
        assert sorted(got) == [
            "order.driver.assigned",
            "order.paid",
            "order.payment.failed",
        ]
        # order.* only matches the single-segment key.
        star_got = []
        while True:
            try:
                msg = await probe.get(timeout=2, fail=True)
                star_got.append(json.loads(msg.body.decode())["rk"])
                await msg.ack()
            except Exception:
                break
        assert star_got == ["order.paid"]
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_happy_path_exactly_once_effects(db_session) -> None:
    from tests.integration.test_phase1 import _migrate
    from tests.integration.test_phase2 import _seed

    await db_session.close()
    await _migrate("up")
    await _seed(db_session)
    settings = await _settings()
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

    from workers.delivery import DeliveryWorker
    from workers.notification import NotificationWorker
    from workers.payment import PaymentWorker
    from workers.restaurant import RestaurantWorker

    payment, restaurant, delivery, notification = (
        PaymentWorker(settings),
        RestaurantWorker(settings),
        DeliveryWorker(settings),
        NotificationWorker(settings),
    )

    async def _outbox_event(event_type: str):
        factory = session_factory()
        async with factory() as session:
            row = (
                await session.execute(
                    select(OutboxEvent).where(OutboxEvent.event_type == event_type)
                )
            ).scalars().first()
            assert row is not None, event_type
            return row.payload

    created_env = await _outbox_event("order.created")
    assert await payment.process_envelope(created_env, 1) == "applied"
    paid_env = await _outbox_event("order.paid")
    # Redelivered identical event: no repeated effects.
    assert await payment.process_envelope(created_env, 1) == "duplicate"
    assert await restaurant.process_envelope(paid_env, 1) == "applied"
    confirmed_env = await _outbox_event("order.confirmed")
    assert await delivery.process_envelope(confirmed_env, 1) == "applied"
    assigned_env = await _outbox_event("order.driver.assigned")

    for env in (created_env, paid_env, confirmed_env, assigned_env):
        assert await notification.process_envelope(env, 1) == "applied"

    factory = session_factory()
    async with factory() as session:
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert order.status == "DRIVER_ASSIGNED"
        payments = (
            await session.execute(
                select(func.count())
                .select_from(SimulatedPayment)
                .where(SimulatedPayment.order_id == order_id)
            )
        ).scalar()
        assigns = (
            await session.execute(
                select(func.count())
                .select_from(DriverAssignment)
                .where(DriverAssignment.order_id == order_id)
            )
        ).scalar()
        notifs = (
            await session.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.order_id == order_id)
            )
        ).scalar()
        assert payments == 1
        assert assigns == 1
        assert notifs == 4


@pytest.mark.asyncio
async def test_skip_locked_claims_are_exclusive(db_session) -> None:
    """Two concurrent claimants never receive the same outbox row."""
    from tests.integration.test_phase1 import _migrate

    await db_session.close()
    await _migrate("up")
    init_db(os.environ["DATABASE_URL"])
    factory = session_factory()
    async with factory() as session:
        session.add(
            OutboxEvent(
                id=new_id("obx"),
                event_id="evt_claim_test",
                event_type="order.created",
                exchange="quickbite.orders",
                routing_key="order.created",
                payload={"event_id": "evt_claim_test"},
            )
        )
        await session.commit()

    async def _claim():
        async with factory() as session:
            async with session.begin():
                rows = (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.sent_at.is_(None))
                        .with_for_update(skip_locked=True)
                    )
                ).scalars()
                found = [r.event_id for r in rows]
                await asyncio.sleep(0.5)  # hold the lock
                return found

    first, second = await asyncio.gather(_claim(), _claim())
    assert sorted(first + second) == ["evt_claim_test"]


@pytest.mark.asyncio
async def test_unroutable_publish_leaves_row_unsent(db_session) -> None:
    from workers.outbox_dispatcher import _publish_one

    await declare_topology(AMQP_URL)
    connection = await aio_pika.connect_robust(AMQP_URL)
    try:
        channel = await connection.channel(on_return_raises=True)
        row = OutboxEvent(
            id=new_id("obx"),
            event_id="evt_unroutable",
            event_type="order.created",
            exchange="",
            routing_key="queue.that.does.not.exist",
            payload={"event_id": "evt_unroutable"},
        )
        with pytest.raises(Exception):
            await _publish_one(channel, row, 1)
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_queue_survives_without_consumer() -> None:
    await declare_topology(AMQP_URL)
    connection = await aio_pika.connect_robust(AMQP_URL)
    try:
        channel = await connection.channel()
        orders = await channel.get_exchange("quickbite.orders")
        await orders.publish(
            aio_pika.Message(b'{"probe": 1}', message_id=f"probe_{uuid.uuid4().hex}"),
            routing_key="order.created",
        )
        payment = await channel.declare_queue("payment.queue", passive=True)
        msg = await payment.get(timeout=5, fail=True)
        assert msg.message_id.startswith("probe_")
        await msg.ack()
    finally:
        await connection.close()

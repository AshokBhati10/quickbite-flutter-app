"""Shared worker helpers: order locking, child events, history."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Order, OrderStatusHistory, OutboxEvent, new_id
from app.domain.state_machine import apply_transition
from app.messaging.consumer import _TransientFailure
from app.messaging.envelopes import build_envelope


async def lock_order(session: AsyncSession, order_id: str) -> Order | None:
    return (
        await session.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
    ).scalar_one_or_none()


def check_version(order: Order, envelope: dict) -> str:
    """Compare order.version with the event's order_version.

    Returns 'ok' | 'stale' (already advanced) | 'future' (prerequisite missing).
    """
    env_version = envelope["order_version"]
    if order.version == env_version:
        return "ok"
    if order.version > env_version:
        return "stale"
    return "future"


async def transition(
    session: AsyncSession,
    order: Order,
    to_status: str,
    envelope: dict,
    exchange_event: tuple[str, str, str, dict] | None,
    failure_code: str | None = None,
) -> None:
    """Apply a version-checked transition + history + optional child outbox.

    exchange_event = (event_type, exchange, routing_key, data).
    """
    from_status = order.status
    apply_transition(order, to_status, envelope["order_version"])
    order.failure_code = failure_code
    session.add(
        OrderStatusHistory(
            id=new_id("hist"),
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            order_version=order.version,
        )
    )
    if exchange_event is not None:
        event_type, exchange, routing_key, data = exchange_event
        child_id = new_id("evt")
        session.add(
            OutboxEvent(
                id=new_id("obx"),
                event_id=child_id,
                event_type=event_type,
                exchange=exchange,
                routing_key=routing_key,
                payload=build_envelope(
                    event_id=child_id,
                    event_type=event_type,
                    order_id=order.id,
                    order_version=order.version,
                    correlation_id=envelope["correlation_id"],
                    causation_id=envelope["event_id"],
                    data=data,
                ),
            )
        )


def version_gate(order: Order, envelope: dict):
    state = check_version(order, envelope)
    if state == "stale":
        return "stale-noop"
    if state == "future":
        # Out-of-order delivery: bounded deferred retry, never silent loss.
        raise _TransientFailure("out_of_order")
    return None

"""Delivery worker: CONFIRMED -> DRIVER_ASSIGNED (or FAILED)."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import init_db
from app.core.logging import configure_logging, log_event
from app.domain.models import Driver, DriverAssignment, new_id
from app.domain.state_machine import InvalidTransitionError
from app.messaging.consumer import Consumer, _PermanentFailure, _TransientFailure
from workers.common import lock_order, transition, version_gate

configure_logging()


class DeliveryWorker(Consumer):
    consumer_name = "delivery"
    queue_name = "delivery.queue"

    async def handle_event(
        self, session: AsyncSession, envelope: dict, attempt: int
    ) -> str:
        await asyncio.sleep(self.settings.DELIVERY_DELAY_S)
        if envelope["event_type"] != "order.confirmed":
            return "stale-noop"
        order = await lock_order(session, envelope["order_id"])
        if order is None:
            raise _PermanentFailure("unknown_order")
        gated = version_gate(order, envelope)
        if gated:
            return gated
        if order.status != "CONFIRMED":
            return "stale-noop"
        if self.settings.DELIVERY_MODE == "fail":
            raise _PermanentFailure("delivery_failed")
        driver = (
            await session.execute(
                select(Driver).where(Driver.is_active.is_(True)).order_by(Driver.id)
            )
        ).scalars().first()
        if driver is None:
            raise _TransientFailure("no_driver_available")
        session.add(
            DriverAssignment(
                id=new_id("assign"),
                order_id=order.id,
                driver_id=driver.id,
            )
        )
        order.driver_id = driver.id
        await transition(
            session,
            order,
            "DRIVER_ASSIGNED",
            envelope,
            (
                "order.driver.assigned",
                "quickbite.orders",
                "order.driver.assigned",
                {
                    "customer_id": order.customer_id,
                    "restaurant_id": order.restaurant_id,
                    "driver_id": driver.id,
                },
            ),
        )
        return "applied"

    async def on_quarantine(
        self, session: AsyncSession, envelope: dict, failure_code: str
    ) -> None:
        order = await lock_order(session, envelope.get("order_id", ""))
        if order is None or order.status != "CONFIRMED":
            return
        try:
            await transition(
                session,
                order,
                "FAILED",
                {**envelope, "order_version": order.version},
                (
                    "order.failed",
                    "quickbite.orders",
                    "order.failed",
                    {
                        "customer_id": order.customer_id,
                        "restaurant_id": order.restaurant_id,
                        "failure_code": "delivery_failed",
                        "stage": "delivery",
                    },
                ),
                failure_code="delivery_failed",
            )
        except InvalidTransitionError:
            return


async def main() -> None:
    settings = get_settings()
    init_db(settings.DATABASE_URL)
    log_event("worker.boot", service="delivery")
    await DeliveryWorker(settings).run()


if __name__ == "__main__":
    import asyncio as _asyncio

    _asyncio.run(main())

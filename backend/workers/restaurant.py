"""Restaurant worker: PAID -> CONFIRMED (or FAILED on terminal decline)."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import init_db
from app.core.logging import configure_logging, log_event
from app.domain.state_machine import InvalidTransitionError
from app.messaging.consumer import Consumer, _PermanentFailure
from workers.common import lock_order, transition, version_gate

configure_logging()


class RestaurantWorker(Consumer):
    consumer_name = "restaurant"
    queue_name = "restaurant.queue"

    async def handle_event(
        self, session: AsyncSession, envelope: dict, attempt: int
    ) -> str:
        await asyncio.sleep(self.settings.RESTAURANT_DELAY_S)
        if envelope["event_type"] != "order.paid":
            return "stale-noop"
        order = await lock_order(session, envelope["order_id"])
        if order is None:
            raise _PermanentFailure("unknown_order")
        gated = version_gate(order, envelope)
        if gated:
            return gated
        if order.status != "PAID":
            return "stale-noop"
        if self.settings.RESTAURANT_MODE == "fail":
            # Permanent business decline: skip retries, go to quarantine which
            # transitions the order to FAILED.
            raise _PermanentFailure("restaurant_declined")
        await transition(
            session,
            order,
            "CONFIRMED",
            envelope,
            (
                "order.confirmed",
                "quickbite.orders",
                "order.confirmed",
                {
                    "customer_id": order.customer_id,
                    "restaurant_id": order.restaurant_id,
                },
            ),
        )
        return "applied"

    async def on_quarantine(
        self, session: AsyncSession, envelope: dict, failure_code: str
    ) -> None:
        order = await lock_order(session, envelope.get("order_id", ""))
        if order is None or order.status != "PAID":
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
                        "failure_code": "restaurant_declined",
                        "stage": "restaurant",
                    },
                ),
                failure_code="restaurant_declined",
            )
        except InvalidTransitionError:
            return


async def main() -> None:
    settings = get_settings()
    init_db(settings.DATABASE_URL)
    log_event("worker.boot", service="restaurant")
    await RestaurantWorker(settings).run()


if __name__ == "__main__":
    import asyncio as _asyncio

    _asyncio.run(main())

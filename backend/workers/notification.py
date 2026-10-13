"""Notification worker: persist customer notifications, never touches status."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import init_db
from app.core.logging import configure_logging, log_event
from app.domain.models import Notification, Order, new_id
from app.messaging.consumer import Consumer, _PermanentFailure, _TransientFailure

configure_logging()

# Events worth a customer-facing notification. Valid future types outside
# this set are acknowledged with a structured log and no effects.
SUPPORTED_TYPES = {
    "order.created": ("Order received", "We accepted your order and started processing it."),
    "order.paid": ("Payment confirmed", "Your payment was confirmed."),
    "order.payment.failed": ("Payment failed", "Your payment could not be completed."),
    "order.confirmed": ("Restaurant confirmed", "The restaurant confirmed your order."),
    "order.driver.assigned": ("Driver assigned", "A driver was assigned to your order."),
    "order.failed": ("Order failed", "Your order could not be completed. See details."),
}


class NotificationWorker(Consumer):
    consumer_name = "notification"
    queue_name = "notification.queue"

    async def handle_event(
        self, session: AsyncSession, envelope: dict, attempt: int
    ) -> str:
        await asyncio.sleep(self.settings.NOTIFICATION_DELAY_S)
        if envelope["event_type"] not in SUPPORTED_TYPES:
            log_event(
                "notification.ignored_future_type",
                service="notification",
                event_type=envelope["event_type"],
                event_id=envelope["event_id"],
            )
            return "ignored"
        if self.settings.NOTIFICATION_MODE == "fail":
            raise _TransientFailure("notification_failed")
        order = (
            await session.execute(select(Order).where(Order.id == envelope["order_id"]))
        ).scalar_one_or_none()
        if order is None:
            raise _PermanentFailure("unknown_order")
        title, body = SUPPORTED_TYPES[envelope["event_type"]]
        session.add(
            Notification(
                id=new_id("notif"),
                customer_id=order.customer_id,
                event_id=envelope["event_id"],
                event_type=envelope["event_type"],
                order_id=order.id,
                title=title,
                body=f"{body} (order {order.id}, status {order.status})",
            )
        )
        return "applied"

    async def on_quarantine(
        self, session: AsyncSession, envelope: dict, failure_code: str
    ) -> None:
        # Notification quarantine preserves the order's business status and
        # only records the notification failure (via the quarantine record).
        log_event(
            "notification.quarantined",
            service="notification",
            event_id=envelope.get("event_id"),
            failure_code=failure_code,
        )


async def main() -> None:
    settings = get_settings()
    init_db(settings.DATABASE_URL)
    log_event("worker.boot", service="notification")
    await NotificationWorker(settings).run()


if __name__ == "__main__":
    import asyncio as _asyncio

    _asyncio.run(main())

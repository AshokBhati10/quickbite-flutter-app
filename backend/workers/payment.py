"""Payment worker: PENDING -> PAID (or PAYMENT_FAILED).

Failure injection via PAYMENT_MODE (env/scripts only):
ok | fail-twice-then-succeed | always-fail | crash-before-commit |
crash-after-commit-before-ack
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import init_db
from app.core.logging import configure_logging, log_event
from app.domain.models import SimulatedPayment, new_id
from app.domain.state_machine import InvalidTransitionError
from app.messaging.consumer import (
    Consumer,
    _PermanentFailure,
    _TransientFailure,
)
from workers.common import check_version, lock_order, transition

configure_logging()


class PaymentWorker(Consumer):
    consumer_name = "payment"
    queue_name = "payment.queue"

    async def handle_event(
        self, session: AsyncSession, envelope: dict, attempt: int
    ) -> str:
        await asyncio.sleep(self.settings.PAYMENT_DELAY_S)
        if envelope["event_type"] != "order.created":
            return "stale-noop"
        order = await lock_order(session, envelope["order_id"])
        if order is None:
            raise _PermanentFailure("unknown_order")
        gate = check_version(order, envelope)
        if gate == "stale":
            return "stale-noop"
        if gate == "future":
            raise _TransientFailure("out_of_order")
        if order.status != "PENDING":
            return "stale-noop"

        mode = self.settings.PAYMENT_MODE
        if mode == "fail-twice-then-succeed" and attempt <= 2:
            raise _TransientFailure("payment_declined")
        if mode == "always-fail":
            raise _TransientFailure("payment_declined")

        if mode == "crash-before-commit":
            # Simulate a crash after writes would flush: exit without commit.
            # The message stays unacked and is redelivered.
            os._exit(1)

        session.add(
            SimulatedPayment(
                id=new_id("pay"),
                order_id=order.id,
                idempotency_id=f"pay_{order.id}",
                status="succeeded",
                attempt=attempt,
            )
        )
        await transition(
            session,
            order,
            "PAID",
            envelope,
            (
                "order.paid",
                "quickbite.orders",
                "order.paid",
                {
                    "customer_id": order.customer_id,
                    "restaurant_id": order.restaurant_id,
                    "payment_id": f"pay_{order.id}",
                },
            ),
        )
        return "applied"

    async def on_quarantine(
        self, session: AsyncSession, envelope: dict, failure_code: str
    ) -> None:
        order = await lock_order(session, envelope.get("order_id", ""))
        if order is None or order.status != "PENDING":
            return
        try:
            await transition(
                session,
                order,
                "PAYMENT_FAILED",
                {**envelope, "order_version": order.version},
                (
                    "order.payment.failed",
                    "quickbite.orders",
                    "order.payment.failed",
                    {
                        "customer_id": order.customer_id,
                        "restaurant_id": order.restaurant_id,
                        "failure_code": "payment_failed",
                    },
                ),
                failure_code="payment_failed",
            )
        except InvalidTransitionError:
            return

    async def after_commit(self, envelope: dict, outcome: str, attempt: int) -> None:
        # Crash checkpoint: commit already happened, but the ack below never
        # runs, so the duplicate is redelivered and deduplicated via
        # processed_events. Only the first application crashes; the
        # redelivery observes outcome 'duplicate' and acks normally.
        if (
            self.settings.PAYMENT_MODE == "crash-after-commit-before-ack"
            and outcome == "applied"
        ):
            os._exit(1)


async def main() -> None:
    settings = get_settings()
    init_db(settings.DATABASE_URL)
    worker = PaymentWorker(settings)
    log_event("worker.boot", service="payment")
    await worker.run()


if __name__ == "__main__":
    import asyncio as _asyncio

    _asyncio.run(main())

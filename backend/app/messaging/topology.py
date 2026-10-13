"""Broker topology (assignment §9).

Exchange quickbite.orders (durable topic) + four queues/bindings,
quickbite.dead (durable direct) + orders.dead-letter.queue.
Idempotent declare; an init step runs it before dispatch.
"""

from __future__ import annotations

import aio_pika
from aio_pika import ExchangeType

ORDERS_EXCHANGE = "quickbite.orders"
DEAD_EXCHANGE = "quickbite.dead"
DEAD_QUEUE = "orders.dead-letter.queue"
DEAD_ROUTING_KEY = "failed"

PAYMENT_QUEUE = "payment.queue"
RESTAURANT_QUEUE = "restaurant.queue"
DELIVERY_QUEUE = "delivery.queue"
NOTIFICATION_QUEUE = "notification.queue"

BINDINGS: tuple[tuple[str, str], ...] = (
    (PAYMENT_QUEUE, "order.created"),
    (RESTAURANT_QUEUE, "order.paid"),
    (DELIVERY_QUEUE, "order.confirmed"),
    (NOTIFICATION_QUEUE, "order.#"),
)

# Routing key -> logical consumer for targeted retries (default exchange).
QUEUE_CONSUMERS: dict[str, str] = {
    PAYMENT_QUEUE: "payment",
    RESTAURANT_QUEUE: "restaurant",
    DELIVERY_QUEUE: "delivery",
    NOTIFICATION_QUEUE: "notification",
}


async def declare_topology(amqp_url: str) -> None:
    connection = await aio_pika.connect_robust(amqp_url)
    try:
        channel = await connection.channel()
        orders = await channel.declare_exchange(
            ORDERS_EXCHANGE, ExchangeType.TOPIC, durable=True
        )
        for queue_name, routing_key in BINDINGS:
            queue = await channel.declare_queue(
                queue_name, durable=True, exclusive=False, auto_delete=False
            )
            await queue.bind(orders, routing_key=routing_key)
        dead = await channel.declare_exchange(
            DEAD_EXCHANGE, ExchangeType.DIRECT, durable=True
        )
        dead_queue = await channel.declare_queue(
            DEAD_QUEUE, durable=True, exclusive=False, auto_delete=False
        )
        await dead_queue.bind(dead, routing_key=DEAD_ROUTING_KEY)
    finally:
        await connection.close()

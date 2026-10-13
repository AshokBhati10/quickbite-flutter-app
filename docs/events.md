# QuickBite event schema

Exchange `quickbite.orders` (durable topic). Dead exchange `quickbite.dead`
(durable direct) with queue `orders.dead-letter.queue` bound by `failed`.

| Queue | Binding | Consumer |
| --- | --- | --- |
| `payment.queue` | `order.created` | payment worker |
| `restaurant.queue` | `order.paid` | restaurant worker |
| `delivery.queue` | `order.confirmed` | delivery worker |
| `notification.queue` | `order.#` | notification worker |

`order.#` (hash = zero or more segments) is required: `order.*` (exactly
one segment) matches `order.paid` but misses `order.payment.failed` and
`order.driver.assigned`.

Event types: `order.created`, `order.paid`, `order.payment.failed`,
`order.confirmed`, `order.driver.assigned`, `order.failed`.

Envelope (JSON, persistent delivery, AMQP `message_id == event_id`):

```json
{
  "event_id": "evt_created_abc123",
  "schema_version": 1,
  "event_type": "order.created",
  "order_id": "order_abc123",
  "order_version": 1,
  "occurred_at": "2026-10-12T09:00:00Z",
  "correlation_id": "req_checkout_123",
  "causation_id": null,
  "data": {"customer_id": "user_1", "restaurant_id": "rest_123"}
}
```

Child events set `causation_id` to the incoming `event_id` and retain
`correlation_id`. Retry attempts travel in AMQP headers (`attempt`), never
as new event identities. Unknown schema versions and malformed messages go
to quarantine, never into infinite retry. A notification worker acks valid
future types it intentionally ignores, with a structured log.

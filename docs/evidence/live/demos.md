# Live demo evidence (2026-10-13, Compose stack)

## Happy path
- 202 accepted, PENDING -> PAID -> CONFIRMED -> DRIVER_ASSIGNED in ~4s.
- history versions 1..4, 4 notifications (one per event).

## Fail-twice-then-succeed (PAYMENT_MODE=fail-twice-then-succeed)
- Order reached DRIVER_ASSIGNED after ~18s (≈2s + ≈10s retry delays).
- retry_jobs: attempts 1 and 2, both done; exactly one simulated payment.

## Always-fail (PAYMENT_MODE=always-fail)
- Order stayed PENDING through retries, then PAYMENT_FAILED/payment_failed at ~46s (≈2+10+30s).
- quarantine_records: payment, attempts=4, retry_exhausted.
- 0 simulated_payments for the order; targeted retries only to payment.queue.

## Worker kill (SIGKILL payment-worker, restart)
- Container restarted healthy; subsequent orders processed normally.

## Broker stop (rabbitmq stopped, order accepted, restarted)
- Checkout during outage: 202 with order ID; 1 pending outbox row.
- /health/ready reported broker down while still accepting (outbox semantic).
- After restart: order reached DRIVER_ASSIGNED (dispatcher/workers reconnected).

## Notification backlog (worker stopped, 2 orders, restart)
- Both orders reached DRIVER_ASSIGNED with 0 notifications while stopped.
- After restart: 4 notifications each; no duplicate (customer_id, event_id).

# Engineering report

## Retry safety

Default policy: 1 initial attempt + 3 delayed retries at ~2 s, 10 s, 30 s
(`RETRY_MAX_RETRIES`, `RETRY_DELAYS_S`), then quarantine. On transient
failure the worker rolls back the business transaction, then in one
transaction inserts a `retry_jobs` row (unique per consumer/event/attempt)
and a scheduled targeted outbox row, and only then acks. If that
transaction fails, the message stays unacked with reconnect/backoff. The
retry scheduler marks jobs done once their targeted publication is sent
and rebuilds a lost targeted row from the immutable domain envelope as a
watchdog. Retries publish via the default exchange with the failing queue
as routing key, so only the failing consumer sees them again.

## Deduplication

`processed_events` keyed by logical `(consumer_name, event_id)` plus unique
constraints on payments, assignments, notifications, history versions, and
idempotency keys. Duplicates ack with no effects; stale versions are marked
processed; out-of-order prerequisites get bounded deferred retries.
Payment uses an order-based idempotency identifier; a real external charge
would still need provider-side idempotency and reconciliation.

## Outbox recovery

Dispatcher claims with `FOR UPDATE SKIP LOCKED` (multiple instances safe),
publishes with confirms + `mandatory=True`, marks sent only after confirm
without unroutable return. Broker outage after acceptance leaves rows
pending; recovery drains them with no missing events. A crash between
publish and mark-sent yields a duplicate that is deduplicated downstream.

## Security choices

Passwords hashed with bcrypt; short-lived signed JWTs with validated
claims; admin enforced server-side; other customers' orders return 404.
CORS uses explicit origins (no wildcard with credentials); `Location` is
exposed for the web client. Tokens live in memory on web and in secure
storage on mobile via conditional imports. Structured logs never include
tokens, passwords, or full addresses. `.env.example` carries placeholders
only; no secrets, broker/DB credentials, or signing keys are committed.

## Measured scaling

See `docs/evidence/`: load runs with ≥100 orders compare 1 vs 3 payment
workers (each repeated ≥2×) with payment as the documented bottleneck.
API acceptance ends at the DB commit, so create-order p50/p95 is
independent of simulated payment delay; misses are reported honestly.

## Limitations

At-least-once delivery, not exactly-once. Payment/restaurant/driver are
simulated. Single-node broker with a persistent volume (recovery covers
restarts, not disk loss or clustering). iOS validation is pending without
macOS access (see README).
